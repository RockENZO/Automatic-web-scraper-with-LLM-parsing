"""
Configuration file for the Automatic Web Scraper
"""

# Ollama Model Configuration
OLLAMA_MODEL = "gpt-oss:20b"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_NUM_PREDICT = 1000

# Scraping Configuration
DEFAULT_WAIT_TIME = 5
HEADLESS_BROWSER = True
DEFAULT_CHUNK_SIZE = 3000
MAX_CHUNK_SIZE = 4000
MIN_CHUNK_SIZE = 500

# Streamlit Configuration
PAGE_TITLE = "Automatic Web Scraper"
PAGE_ICON = "🤖"

# Selenium Configuration
CHROME_DRIVER_PATH = "./chromedriver"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# Logging Configuration
LOG_LEVEL = "INFO"

# Applied by parse.py; a chunk limit is a conservative character budget, not a token guarantee.
import os
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", OLLAMA_MODEL)
OLLAMA_FALLBACK_MODEL = os.getenv("OLLAMA_FALLBACK_MODEL", "llama3.1:8b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_NUM_CTX = 8192
OLLAMA_TIMEOUT = 60
OLLAMA_ATTEMPTS = 2
OLLAMA_RETRY_DELAY = 1
