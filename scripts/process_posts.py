import os
import json
import base64
from datetime import datetime
from pathlib import Path
from PIL import Image
import requests

def process_post(post_file):
    """Process a single post"""
    with open(post_file, 'r') as f:
        post = json.load(f)
    
    print(f"Processing post: {post['id']}")
    
    # Update status
    post['status'] = 'processing'
    post['processed_at'] = datetime.now().isoformat()
    
    # Save processed status
    processed_dir = Path('data/processed')
    processed_dir.mkdir(exist_ok=True)
    
    with open(processed_dir / f"{post['id']}.json", 'w') as f:
        json.dump(post, f, indent=2)
    
    # Optimize image if exists
    image_path = Path(f"data/images/{post['image_filename']}")
    if image_path.exists():
        try:
            img = Image.open(image_path)
            
            # Create thumbnail
            thumbnail = img.copy()
            thumbnail.thumbnail((200, 200))
            thumbnail.save(f"data/images/thumb_{post['image_filename']}")
            
            # Optimize image
            img.save(f"data/images/opt_{post['image_filename']}", 
                    optimize=True, quality=85)
            
            print(f"Image optimized for post {post['id']}")
        except Exception as e:
            print(f"Error optimizing image: {e}")
    
    # Send notification (optional)
    if os.getenv('TELEGRAM_TOKEN'):
        send_notification(post)
    
    print(f"Post {post['id']} processed successfully")
    
    # Update final status
    post['status'] = 'completed'
    with open(processed_dir / f"{post['id']}.json", 'w') as f:
        json.dump(post, f, indent=2)
    
    return post

def send_notification(post):
    """Send notification via Telegram"""
    token = os.getenv('TELEGRAM_TOKEN')
    channel = os.getenv('TELEGRAM_CHANNEL_ID')
    
    if not token or not channel:
        return
    
    message = f"""
🎉 **New Post Published!**

**Title:** {post['title']}
**Author:** @{post['username']}
**Time:** {post['timestamp']}
**Status:** ✅ Processed

Check it out in the feed!
"""
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {
        'chat_id': channel,
        'text': message,
        'parse_mode': 'Markdown'
    }
    
    try:
        requests.post(url, json=data)
    except Exception as e:
        print(f"Error sending notification: {e}")

def main():
    """Main processing function"""
    posts_dir = Path('data/posts')
    processed_dir = Path('data/processed')
    processed_dir.mkdir(exist_ok=True)
    
    # Get unprocessed posts
    unprocessed = []
    for json_file in posts_dir.glob('*.json'):
        post_id = json_file.stem
        processed_file = processed_dir / f"{post_id}.json"
        
        if not processed_file.exists():
            unprocessed.append(json_file)
    
    print(f"Found {len(unprocessed)} unprocessed posts")
    
    for post_file in unprocessed:
        try:
            process_post(post_file)
        except Exception as e:
            print(f"Error processing {post_file}: {e}")

if __name__ == '__main__':
    main()
