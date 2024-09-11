# Automatic Web Scraper

This project is an automatic web scraper that uses the LLM Ollama 3.1 to parse the body content of a web page. The application is built using Streamlit for the user interface and various Python libraries for web scraping and parsing.

## Features
- Scrape the body content of a web page.
- Clean the scraped content by removing scripts and styles.
- Split the content into manageable chunks.
- Parse the content using the LLM Ollama 3.1 based on user-provided descriptions.

## Installation
### Prerequisites
- Python 3.7 or higher

### Create a virtual environment:
```bash
python -m venv ai
```

### Activate the virtual environment:
- On macOS and Linux:
```bash
source ai/bin/activate
```
- On Windows:
```bash
.\venv\Scripts\activate
``` 

### Installing dependencies:
```bash
pip install -r requirements.txt
```
## Running the Application
1. Activate the virtual environment (if not already activated):
- On macOS and Linux:
```bash
source ai/bin/activate
```
- On Windows:
```bash
.\venv\Scripts\activate
``` 
2. Run the Streamlit application:
```python
streamlit run main.py
```
## Usage
1. Enter the URL of the website you want to scrape in the input field.
2. Click the "Scrape" button to scrape the website.
3. View the DOM content in the expander section.
3. Describe what you want to parse in the text area.
5. Click the "Parse Content" button to parse the content based on your description.
6. View the parsed results on the Streamlit app.

## Dependencies
- streamlit
- langchain
- langchain_ollama
- selenium
- beautifulsoup4
- lxml
- html5lib
- python-dotenv

## License
This project is licensed under the MIT License. See the LICENSE file for more details.

