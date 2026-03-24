import json
from pathlib import Path
from datetime import datetime

def generate_json_feed():
    """Generate JSON feed of all posts"""
    processed_dir = Path('data/processed')
    feed = []
    
    for json_file in sorted(processed_dir.glob('*.json'), reverse=True):
        with open(json_file, 'r') as f:
            post = json.load(f)
            feed.append(post)
    
    # Create feeds directory
    feeds_dir = Path('feeds')
    feeds_dir.mkdir(exist_ok=True)
    
    # Save JSON feed
    with open(feeds_dir / 'feed.json', 'w') as f:
        json.dump({
            'version': '1.0',
            'title': 'Telegram Posts Feed',
            'home_page_url': 'https://github.com/yourusername/telegram-post-bot',
            'feed_url': 'https://yourusername.github.io/telegram-post-bot/feed.json',
            'items': feed
        }, f, indent=2)
    
    print(f"Generated feed with {len(feed)} posts")
    
    # Generate markdown summary
    with open(feeds_dir / 'README.md', 'w') as f:
        f.write("# Posts Feed\n\n")
        for post in feed[:20]:  # Last 20 posts
            f.write(f"## {post['title']}\n")
            f.write(f"- **Author:** @{post['username']}\n")
            f.write(f"- **Date:** {post['timestamp'][:10]}\n")
            f.write(f"- **Status:** {post.get('status', 'unknown')}\n\n")

if __name__ == '__main__':
    generate_json_feed()
