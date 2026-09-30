#!/usr/bin/env python3
"""
Quick test script for the Automatic Web Scraper
Tests the main functionality to ensure everything works correctly.
"""

import sys
import logging
from scrape import scrape_website, extract_body_content, clean_body_content
from parse import parse_with_ollama

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_scraper():
    """Test the web scraper functionality."""
    print("🧪 Testing Automatic Web Scraper")
    print("=" * 40)
    
    test_url = "https://example.com"
    print(f"📡 Testing with URL: {test_url}")
    
    try:
        # Test scraping
        print("1️⃣ Testing web scraping...")
        html_content = scrape_website(test_url, wait_time=2)
        print(f"   ✅ Scraped {len(html_content):,} characters")
        
        # Test content extraction
        print("2️⃣ Testing content extraction...")
        body_content = extract_body_content(html_content)
        print(f"   ✅ Extracted {len(body_content):,} characters from body")
        
        # Test content cleaning
        print("3️⃣ Testing content cleaning...")
        cleaned_content = clean_body_content(body_content)
        print(f"   ✅ Cleaned content: {len(cleaned_content):,} characters")
        
        # Test AI parsing
        print("4️⃣ Testing AI parsing...")
        test_description = "Extract the main heading or title of the page"
        try:
            parsed_result = parse_with_ollama([cleaned_content[:2000]], test_description)
            if parsed_result.status in ('failed', 'partial'):
                print(f"   AI extraction incomplete: {parsed_result.status}; failed chunks {parsed_result.failed_chunks}")
                return False
            print(f"   AI extraction outcome: {parsed_result.status}")
            print(f"   Result: {parsed_result.text[:100]}...")
        except Exception as e:
            print(f"   ⚠️ AI parsing failed (Ollama might not be running): {e}")
            return False
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        return False

def main():
    """Main function."""
    success = test_scraper()
    if not success:
        print("\n💡 Troubleshooting tips:")
        print("   - Make sure Chrome browser is installed")
        print("   - Run 'python setup_chromedriver.py' to fix ChromeDriver issues")
        print("   - Make sure Ollama is running: 'ollama serve'")
        print("   - Check that gpt-oss:20b model is available: 'ollama list'")
        sys.exit(1)
    
    print("\n✨ Your web scraper is ready to use!")
    print("   Run 'streamlit run main.py' to start the web interface")

if __name__ == "__main__":
    main()
