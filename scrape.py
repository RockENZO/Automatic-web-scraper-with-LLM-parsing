import selenium.webdriver as webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import time
from content import extract_body_content, clean_body_content, split_dom_content
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants
DEFAULT_WAIT_TIME = 5
MAX_RETRY_ATTEMPTS = 3


def scrape_website(website: str, wait_time: int = DEFAULT_WAIT_TIME, headless: bool = True) -> str:
    """
    Scrape a website and return its HTML content.
    
    Args:
        website (str): URL to scrape
        wait_time (int): Time to wait for page loading
        headless (bool): Run browser in headless mode
        
    Returns:
        str: HTML content of the website
        
    Raises:
        Exception: If scraping fails after all retry attempts
    """
    logger.info(f"Starting to scrape: {website}")
    
    # Validate URL
    from utils import validate_url
    if not validate_url(website):
        raise ValueError(f"Invalid URL provided: {website}")
    
    # Configure Chrome options
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36")
    
    # Use ChromeDriverManager to automatically download and manage the correct ChromeDriver
    try:
        service = Service(ChromeDriverManager().install())
        logger.info("Using ChromeDriverManager for automatic driver management")
    except Exception as e:
        # Fallback to local chromedriver if webdriver-manager fails
        logger.warning(f"ChromeDriverManager failed: {e}. Falling back to local chromedriver")
        chrome_driver_path = "./chromedriver"
        service = Service(chrome_driver_path)
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        driver.get(website)
        logger.info("Page loaded, waiting for content...")
        
        # Wait for body element to be present
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        
        # Additional wait for dynamic content
        time.sleep(wait_time)
        
        html = driver.page_source
        logger.info(f"Successfully scraped {len(html)} characters")
        return html
        
    except Exception as e:
        logger.error(f"Error scraping website: {str(e)}")
        raise
    finally:
        driver.quit()
        logger.info("Browser closed")

