# Automatic Web Scraper

This project is an automatic web scraper that uses the LLM Ollama gpt-oss:20b to parse the body content of a web page. The application is built using Streamlit for the user interface and various Python libraries for web scraping and parsing.

## Repository and URL safety

The local Python environment is ignored by Git. Create `.venv` during setup; do not commit it. Run isolated checks with `python -m unittest discover -s tests`. The existing `test_scraper.py` is a manual integration check that needs Chrome, a live site, and Ollama.

The scraper accepts only HTTP(S) URLs resolving to public IP addresses and rejects localhost, private addresses, credentials, and unusual ports. DNS can change after validation, and browsers can follow redirects. If you deploy this as a shared web service, also restrict outbound network access and apply request limits at the hosting layer.

## Features
- 🚀 **Advanced Web Scraping**: Scrape the body content of any web page with improved error handling
- 🧹 **Smart Content Cleaning**: Clean the scraped content by removing scripts, styles, and unwanted elements
- 📊 **Intelligent Chunking**: Split large content into manageable chunks for processing
- 🤖 **AI-Powered Parsing**: Parse content using the powerful Ollama gpt-oss:20b model
- 📈 **Real-time Progress**: Track scraping and parsing progress with visual indicators
- 💾 **Export Results**: Download parsed results as text files
- ⚙️ **Configurable Settings**: Adjust chunk sizes and processing parameters

## New in This Version
- ✨ Updated to use Ollama gpt-oss:20b model for better performance
- 🛡️ Enhanced error handling and logging
- 🎨 Improved user interface with better feedback
- 📱 Responsive design with sidebar configuration
- 🔧 Modular code structure with separate config and utility files
- 📊 Content statistics and processing metrics
- 🌐 Better URL validation and domain extraction

## Demo
![Web Scrapper](ScreenRecording.gif)

## Installation
### Prerequisites
- Python 3.8 or higher
- Ollama installed with gpt-oss:20b model
- Chrome browser (ChromeDriver will be downloaded automatically)

### Install Ollama and the model:
```bash
# Install Ollama (macOS)
brew install ollama

# Pull the gpt-oss:20b model
ollama pull gpt-oss:20b
```

### Create a virtual environment:
```bash
python -m venv .venv
```

### Activate the virtual environment:
- On macOS and Linux:
```bash
source .venv/bin/activate
```
- On Windows:
```bash
.\.venv\Scripts\activate
``` 

### Installing dependencies:
```bash
pip install -r requirements.txt
```

### Setup ChromeDriver (automatic):
```bash
# Optional: Run ChromeDriver setup utility to verify compatibility
python setup_chromedriver.py
```

## Running the Application
1. Make sure Ollama is running:
```bash
ollama serve
```

2. Activate the virtual environment (if not already activated):
- On macOS and Linux:
```bash
source .venv/bin/activate
```
- On Windows:
```bash
.\.venv\Scripts\activate
``` 

3. Run the Streamlit application:
```bash
streamlit run main.py
```
## Usage
1. 🌐 **Enter URL**: Input the URL of the website you want to scrape
2. ⚙️ **Configure Settings**: Adjust chunk size in the sidebar (optional)
3. 🤳 **Scrape Website**: Click "Scrape Website" to extract content
4. 👁️ **Review Content**: View the extracted DOM content in the expander
5. 📝 **Describe Parsing**: Describe what specific information you want to extract
6. 🚀 **Parse Content**: Click "Parse Content" to process with AI
7. 📊 **View Results**: Review the extracted information
8. 💾 **Download**: Save results as a text file (optional)

## Examples of Parse Descriptions
- "Extract all email addresses"
- "Find product names and prices"
- "Get all phone numbers and contact information"
- "Extract article titles and publication dates"
- "Find all social media links"

## Configuration
You can modify settings in `config.py`:
- **Model Settings**: Change Ollama model, temperature, and prediction limits
- **Scraping Settings**: Adjust wait times, browser settings, and chunk sizes
- **UI Settings**: Customize page title, icons, and layout

## Project Structure
```
├── main.py                # Main Streamlit application
├── scrape.py             # Web scraping functionality
├── parse.py              # AI parsing with Ollama
├── config.py             # Configuration settings
├── utils.py              # Utility functions
├── setup_chromedriver.py # ChromeDriver setup utility
├── requirements.txt      # Python dependencies
└── README.md            # Documentation
```

## Dependencies
- **streamlit**: Web application framework
- **langchain & langchain_ollama**: LLM integration
- **selenium**: Web browser automation
- **webdriver-manager**: Automatic ChromeDriver management
- **beautifulsoup4**: HTML parsing
- **lxml & html5lib**: XML/HTML processing
- **python-dotenv**: Environment variable management
- **requests & urllib3**: HTTP libraries

## Troubleshooting
### Common Issues:
1. **ChromeDriver version mismatch**: The app now automatically downloads the correct ChromeDriver version
   - If you get ChromeDriver errors, run: `python setup_chromedriver.py`
   - This will download and test the compatible ChromeDriver for your Chrome version
2. **Ollama model not available**: Run `ollama pull gpt-oss:20b`
3. **Connection errors**: Check internet connection and URL validity
4. **Memory issues**: Reduce chunk size in sidebar settings

### ChromeDriver Setup:
The project now includes automatic ChromeDriver management using `webdriver-manager`. If you encounter ChromeDriver compatibility issues:

```bash
# Run the ChromeDriver setup utility
python setup_chromedriver.py
```

This utility will:
- ✅ Detect your Chrome browser version
- 📥 Download the compatible ChromeDriver automatically
- 🧪 Test the ChromeDriver to ensure it works
- 📋 Provide detailed status information

### Performance Tips:
- Use smaller chunk sizes for faster processing
- Enable headless browsing for better performance
- Close unnecessary browser tabs to free memory
- The ChromeDriver is automatically cached for faster subsequent runs

## License
This project is licensed under the MIT License. See the LICENSE file for more details.


## Extraction outcome and recovery

Parsing returns `ParseResult` with `status`, extraction `text`, chunk counts, failed chunk indices and actual models used. Success, no matches, partial extraction and total failure are displayed separately. A failure message is never offered as extracted data. Partial downloads are explicitly labelled. Progress updates after every processed chunk.

Fallback is attempted when an actual request fails, including connection and missing-model errors; creating a model object alone is not treated as proof it is available. Requests have a 60-second timeout, two attempts per model per chunk, and a one-second retry delay. Install both configured models with `ollama pull`, or set `OLLAMA_MODEL`, `OLLAMA_FALLBACK_MODEL` and `OLLAMA_BASE_URL`. The default chunk is 3,000 characters, maximum 4,000, with an 8,192-token model context; character limits are conservative and do not guarantee token fit for all languages.

```bash
python -m unittest discover -s tests -v
```

Parser tests use injected model doubles and cover fallback, all-failed, partial, empty, successful and invalid inputs without Chrome or Ollama. They verify control flow, not extraction accuracy. A real model may hallucinate or follow malicious webpage instructions; verify important output against the source. The application is a local demo; URL checks alone do not make Selenium safe to expose as a public scraping service.
