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
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager

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

def setup_selenium_driver():
    """Setup and return a Selenium WebDriver with Chrome in headless mode."""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver
    except Exception as e:
        print(f"  ⚠ Warning: Could not setup Selenium: {e}")
        print(f"  Falling back to basic HTML scraping...")
        return None

def expand_all_content(driver, wait_time=3):
    """Find and click all expandable elements to reveal hidden content."""
    try:
        # Wait for page to load
        time.sleep(2)
        
        # Scroll to load lazy content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1)
        driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
        
        expanded_count = 0
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            found_any = False
            
            # Find all potential expandable elements
            selectors = [
                # Common button patterns
                "button[aria-expanded='false']",
                "button[aria-expanded='true']",  # Sometimes we need to toggle
                "a[aria-expanded='false']",
                "div[aria-expanded='false']",
                
                # Text-based selectors (case-insensitive)
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'read more')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'expand')]",
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'more')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'show more')]",
                "//a[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'read more')]",
                
                # Class-based selectors
                "[class*='expand']",
                "[class*='collapse']",
                "[class*='accordion']",
                "[class*='toggle']",
                "[class*='show-more']",
                "[class*='read-more']",
                "[class*='hidden']",
                "[class*='collapsed']",
                
                # Data attributes
                "[data-toggle='collapse']",
                "[data-bs-toggle='collapse']",
                "[data-target*='collapse']",
                "[data-bs-target*='collapse']",
            ]
            
            for selector in selectors:
                try:
                    if selector.startswith("//"):
                        # XPath selector
                        elements = driver.find_elements(By.XPATH, selector)
                    else:
                        # CSS selector
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    
                    for element in elements:
                        try:
                            # Check if element is visible and clickable
                            if element.is_displayed():
                                # Scroll element into view
                                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
                                time.sleep(0.3)
                                
                                # Try clicking
                                element.click()
                                found_any = True
                                expanded_count += 1
                                time.sleep(0.5)  # Wait for content to expand
                        except (ElementClickInterceptedException, NoSuchElementException):
                            # Try JavaScript click as fallback
                            try:
                                driver.execute_script("arguments[0].click();", element)
                                found_any = True
                                expanded_count += 1
                                time.sleep(0.5)
                            except:
                                pass
                except:
                    continue
            
            # If no more expandable elements found, break
            if not found_any:
                break
            
            # Scroll down to find more elements
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(0.5)
        
        if expanded_count > 0:
            print(f"  ✓ Expanded {expanded_count} hidden sections")
        
        # Final scroll to bottom to load any lazy-loaded content
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(wait_time)
        
    except Exception as e:
        print(f"  ⚠ Warning during expansion: {e}")

def extract_text_from_html(html):
    """Extract clean text from HTML."""
    if not html:
        return ""
    
    try:
        soup = BeautifulSoup(html, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style", "noscript"]):
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

def scrape_with_selenium(url, driver, timeout=30):
    """Scrape a URL using Selenium to get all content including JavaScript-rendered and hidden content."""
    try:
        driver.set_page_load_timeout(timeout)
        driver.get(url)
        
        # Wait for page to be interactive
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        
        # Expand all hidden content
        expand_all_content(driver)
        
        # Get the final HTML after all expansions
        html = driver.page_source
        
        # Extract text
        text = extract_text_from_html(html)
        return text
        
    except TimeoutException:
        print(f"  ⚠ Page load timeout")
        return None
    except Exception as e:
        print(f"  ⚠ Error with Selenium: {e}")
        return None

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
        
        # Setup Selenium driver (will be None if Selenium is not available)
        driver = setup_selenium_driver()
        use_selenium = driver is not None
        
        if use_selenium:
            print("Using Selenium for full content extraction (including hidden elements)...\n")
        else:
            print("Using basic HTML scraping (Selenium not available)...\n")
        
        training_data = {}
        valid_links = []
        
        for i, link in enumerate(links, 1):
            print(f"[{i}/{len(links)}] Processing: {link}")
            valid_links.append(link)
            
            text = None
            
            # Try Selenium first if available
            if use_selenium:
                try:
                    text = scrape_with_selenium(link, driver, timeout=30)
                except Exception as e:
                    print(f"  ⚠ Selenium failed: {e}")
                    text = None
            
            # Fallback to basic HTML scraping if Selenium failed or not available
            if not text:
                html = fetch_with_retry(link)
                if html:
                    text = extract_text_from_html(html)
            
            if text:
                # Limit to 5000 characters (same as in the chatbot)
                training_data[link] = text[:5000]
                print(f"  ✓ Loaded {len(text)} characters")
            else:
                print(f"  ✗ Failed to load")
                training_data[link] = ""  # Store empty string for failed links
        
        # Close Selenium driver if it was opened
        if driver:
            try:
                driver.quit()
            except:
                pass
        
        return {
            "valid_links": valid_links,
            "training_data": training_data,
            "last_updated": time.strftime("%Y-%m-%d %H:%M:%S")
        }
    
    except Exception as e:
        print(f"Error: {e}")
        # Make sure to close driver on error
        try:
            if 'driver' in locals() and driver:
                driver.quit()
        except:
            pass
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

