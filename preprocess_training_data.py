#!/usr/bin/env python3
"""
Pre-processing script to fetch training data from links and save to a JSON file.
Run this script whenever you update training_links.txt to regenerate the pre-processed data.

Usage: python preprocess_training_data.py
"""

import json
import requests
from bs4 import BeautifulSoup
import time
import sys
import os
from urllib.parse import urlparse

# Configuration
LINKS_URL = "https://raw.githubusercontent.com/RaresC24/chatbot/refs/heads/main/training_links.txt"
OUTPUT_FILE = "training_data.json"
# Auto-upload is disabled in GitHub Actions (handled by workflow)
AUTO_UPLOAD = os.environ.get("GITHUB_ACTIONS") != "true"  # True unless running in GitHub Actions

def fetch_with_retry(url, max_retries=3, timeout=10):
    """Fetch URL with retry logic and CORS proxy fallback."""
    proxies = [
        f"https://api.allorigins.win/raw?url={url}",
        f"https://corsproxy.io/?{url}",
        url  # Try direct last
    ]
    
    for attempt in range(max_retries):
        for proxy_url in proxies:
            try:
                response = requests.get(proxy_url, timeout=timeout)
                if response.status_code == 200:
                    return response.text
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"  Failed after {max_retries} attempts: {e}")
                continue
        time.sleep(0.5)  # Small delay between retries
    
    return None

def extract_text_from_html(html):
    """Extract clean text from HTML."""
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        # Get text and clean it up
        text = soup.get_text()
        # Replace multiple whitespace with single space
        text = ' '.join(text.split())
        return text.strip()
    except Exception as e:
        print(f"  Error parsing HTML: {e}")
        # Fallback: simple regex-based extraction
        import re
        text = re.sub(r'<[^>]+>', ' ', html)
        text = ' '.join(text.split())
        return text.strip()

def load_training_data():
    """Load training data from all links."""
    print("Fetching links list...")
    try:
        response = requests.get(LINKS_URL, timeout=10)
        if response.status_code != 200:
            print(f"Error: Failed to fetch links list (status {response.status_code})")
            return None
        
        links = [line.strip() for line in response.text.split('\n') if line.strip()]
        print(f"Found {len(links)} links to process\n")
        
        training_data = {}
        valid_links = []
        
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] Processing: {link}")
            valid_links.append(link)
            
            html = fetch_with_retry(link)
            if html:
                text = extract_text_from_html(html)
                # Limit to 5000 characters (same as in the chatbot)
                training_data[link] = text[:5000]
                print(f"  ✓ Loaded {len(text)} characters")
            else:
                print(f"  ✗ Failed to load")
                training_data[link] = ""  # Store empty string for failed links
        
        return {
            "valid_links": valid_links,
            "training_data": training_data,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    except Exception as e:
        print(f"Error: {e}")
        return None

def main():
    print("=" * 60)
    print("Training Data Pre-processor")
    print("=" * 60)
    print()
    
    data = load_training_data()
    
    if data:
        print(f"\nSaving to {OUTPUT_FILE}...")
        with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        loaded_count = sum(1 for v in data["training_data"].values() if v)
        print(f"✓ Successfully processed {loaded_count}/{len(data['valid_links'])} links")
        print(f"✓ Data saved to {OUTPUT_FILE}")
        
        # Auto-upload to GitHub if enabled
        if AUTO_UPLOAD:
            print(f"\n{'='*60}")
            print("Auto-uploading to GitHub...")
            print(f"{'='*60}")
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, "upload_to_github.py"],
                    capture_output=False
                )
                if result.returncode == 0:
                    print("\n✓ All done! The chatbot will now load instantly!")
                else:
                    print("\n⚠ Upload failed. You can manually run: python upload_to_github.py")
            except Exception as e:
                print(f"\n⚠ Auto-upload failed: {e}")
                print("   You can manually run: python upload_to_github.py")
        else:
            print(f"\nNext steps:")
            print(f"1. Upload {OUTPUT_FILE} to your GitHub repository")
            print(f"2. Or run: python upload_to_github.py")
            print(f"3. The chatbot will now load instantly!")
    else:
        print("\n✗ Failed to process training data")

if __name__ == "__main__":
    main()

