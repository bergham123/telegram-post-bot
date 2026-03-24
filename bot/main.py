import os
import json
import base64
import tempfile
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests

# Configuration
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO", "yourusername/telegram-post-bot")
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main")

class GitHubAPI:
    """Handle GitHub API operations"""
    
    def __init__(self, token, repo, branch):
        self.token = token
        self.repo = repo
        self.branch = branch
        self.base_url = f"https://api.github.com/repos/{repo}"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def create_or_update_file(self, path, content, message):
        """Create or update a file in GitHub"""
        url = f"{self.base_url}/contents/{path}"
        
        # Encode content to base64
        if isinstance(content, str):
            content = content.encode()
        encoded_content = base64.b64encode(content).decode()
        
        # Check if file exists
        response = requests.get(url, headers=self.headers)
        data = {
            "message": message,
            "content": encoded_content,
            "branch": self.branch
        }
        
        if response.status_code == 200:
            # Update existing file
            existing = response.json()
            data["sha"] = existing["sha"]
        
        # Create or update file
        response = requests.put(url, headers=self.headers, json=data)
        return response.status_code in [200, 201]
    
    def trigger_workflow(self, workflow_id, inputs=None):
        """Trigger a GitHub Actions workflow"""
        url = f"{self.base_url}/actions/workflows/{workflow_id}/dispatches"
        data = {
            "ref": self.branch,
            "inputs": inputs or {}
        }
        response = requests.post(url, headers=self.headers, json=data)
        return response.status_code == 204

# Store user sessions (use Redis in production)
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    welcome_text = """
🎨 **Telegram Post Bot with GitHub Actions**

Create posts that automatically trigger GitHub Actions workflows!

**Features:**
- ✅ Create posts with images and titles
- ✅ Automatic JSON storage
- ✅ GitHub Actions workflow triggers
- ✅ Post processing automation
- ✅ Feed generation

**Commands:**
/newpost - Create a new post
/myposts - View your posts
/trigger - Manually trigger workflow
/status - Check workflow status
/help - Show this message
"""
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def new_post(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start post creation process"""
    user_id = update.effective_user.id
    username = update.effective_user.username or update.effective_user.first_name
    
    user_sessions[user_id] = {
        'username': username,
        'user_id': user_id,
        'step': 'title',
        'title': None,
        'image_data': None,
        'timestamp': datetime.now().isoformat()
    }
    
    await update.message.reply_text("📝 **Step 1/2:** Please enter the title for your post:", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("Please use /newpost to create a post first!")
        return
    
    session = user_sessions[user_id]
    
    if session['step'] == 'title':
        session['title'] = update.message.text
        session['step'] = 'image'
        await update.message.reply_text("🖼️ **Step 2/2:** Now send me the image for your post:", parse_mode='Markdown')

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle image uploads"""
    user_id = update.effective_user.id
    
    if user_id not in user_sessions:
        await update.message.reply_text("Please use /newpost to create a post first!")
        return
    
    session = user_sessions[user_id]
    
    if session['step'] == 'image':
        # Show processing message
        processing_msg = await update.message.reply_text("⏳ Processing your post...")
        
        try:
            # Get photo file
            photo_file = await update.message.photo[-1].get_file()
            
            # Download image
            image_data = await photo_file.download_as_bytearray()
            
            # Generate post ID
            post_id = f"{user_id}_{datetime.now().timestamp()}"
            
            # Prepare post data
            post_data = {
                'id': post_id,
                'title': session['title'],
                'username': session['username'],
                'user_id': user_id,
                'timestamp': session['timestamp'],
                'status': 'pending',
                'image_filename': f"{post_id}.jpg"
            }
            
            # Initialize GitHub API
            github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH)
            
            # Save image to GitHub
            image_path = f"data/images/{post_data['image_filename']}"
            image_saved = github.create_or_update_file(
                image_path,
                image_data,
                f"Upload image for post {post_id}"
            )
            
            if not image_saved:
                await processing_msg.edit_text("❌ Failed to upload image. Please try again.")
                return
            
            # Save post JSON
            json_path = f"data/posts/{post_id}.json"
            json_saved = github.create_or_update_file(
                json_path,
                json.dumps(post_data, indent=2),
                f"Create post {post_id}"
            )
            
            if not json_saved:
                await processing_msg.edit_text("❌ Failed to save post data. Please try again.")
                return
            
            # Trigger GitHub Actions workflow
            workflow_triggered = github.trigger_workflow(
                'process-posts.yml',
                {'post_id': post_id, 'action': 'new_post'}
            )
            
            if workflow_triggered:
                await processing_msg.edit_text(
                    f"✅ **Post created successfully!**\n\n"
                    f"📝 **Title:** {post_data['title']}\n"
                    f"👤 **Author:** @{post_data['username']}\n"
                    f"🆔 **Post ID:** `{post_id}`\n\n"
                    f"⚙️ GitHub Actions workflow has been triggered to process your post.\n"
                    f"Use /status {post_id} to check progress.",
                    parse_mode='Markdown'
                )
            else:
                await processing_msg.edit_text(
                    f"✅ Post saved but workflow trigger failed.\n"
                    f"Post ID: `{post_id}`",
                    parse_mode='Markdown'
                )
            
            # Clean up session
            del user_sessions[user_id]
            
        except Exception as e:
            await processing_msg.edit_text(f"❌ Error: {str(e)}")
            del user_sessions[user_id]

async def my_posts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List user's posts"""
    username = update.effective_user.username or update.effective_user.first_name
    
    await update.message.reply_text("🔍 Fetching your posts...")
    
    try:
        # Use GitHub API to fetch user's posts
        github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH)
        url = f"{github.base_url}/contents/data/posts"
        response = requests.get(url, headers=github.headers)
        
        if response.status_code == 200:
            posts = []
            for item in response.json():
                if item['name'].endswith('.json'):
                    # Get post content
                    content_response = requests.get(item['download_url'])
                    if content_response.status_code == 200:
                        post = content_response.json()
                        if post.get('username') == username:
                            posts.append(post)
            
            if posts:
                text = f"📚 **Your Posts ({len(posts)}):**\n\n"
                for idx, post in enumerate(posts[:10], 1):
                    text += f"{idx}. **{post['title']}**\n"
                    text += f"   🆔 `{post['id']}`\n"
                    text += f"   📅 {post['timestamp'][:10]}\n"
                    text += f"   ⚡ Status: {post.get('status', 'unknown')}\n\n"
                
                await update.message.reply_text(text, parse_mode='Markdown')
            else:
                await update.message.reply_text("📭 You haven't created any posts yet.")
        else:
            await update.message.reply_text("❌ Failed to fetch posts.")
            
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def trigger_workflow(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Manually trigger a workflow"""
    github = GitHubAPI(GITHUB_TOKEN, GITHUB_REPO, GITHUB_BRANCH)
    
    # Get workflow ID from arguments or use default
    workflow = context.args[0] if context.args else 'process-posts.yml'
    
    await update.message.reply_text(f"⏳ Triggering workflow: {workflow}...")
    
    triggered = github.trigger_workflow(workflow, {'triggered_by': str(update.effective_user.id)})
    
    if triggered:
        await update.message.reply_text(f"✅ Workflow `{workflow}` triggered successfully!", parse_mode='Markdown')
    else:
        await update.message.reply_text(f"❌ Failed to trigger workflow `{workflow}`", parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_text = """
🤖 **Bot Commands:**

/newpost - Create a new post
/myposts - View your posts
/trigger <workflow> - Trigger a workflow manually
/status <post_id> - Check post processing status
/help - Show this help

**Workflows Available:**
- process-posts.yml - Process new posts
- generate-feed.yml - Generate RSS/JSON feed

**Post Processing:**
Posts are automatically processed by GitHub Actions:
1. Image optimization
2. Metadata extraction
3. Feed generation
4. Notifications
"""
    await update.message.reply_text(help_text, parse_mode='Markdown')

def main():
    """Start the bot"""
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("newpost", new_post))
    application.add_handler(CommandHandler("myposts", my_posts))
    application.add_handler(CommandHandler("trigger", trigger_workflow))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(MessageHandler(filters.PHOTO, handle_image))
    
    print("🤖 Bot is running...")
    application.run_polling()

if __name__ == '__main__':
    main()
