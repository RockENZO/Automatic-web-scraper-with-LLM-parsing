# Automatic Web Scraper

This project is an automatic web scraper that uses the LLM Ollama gpt-oss:20b to parse the body content of a web page. The application is built using Streamlit for the user interface and various Python libraries for web scraping and parsing.

## Repository and URL safety

The local Python environment is ignored by Git. Create `.venv` during setup; do not commit it. Run isolated checks with `python -m unittest discover -s tests`. The existing `test_scraper.py` is a manual integration check that needs Chrome, a live site, and Ollama.

The scraper accepts only HTTP(S) URLs resolving to public IP addresses and rejects localhost, private addresses, credentials, and unusual ports. DNS can change after validation, and browsers can follow redirects. If you deploy this as a shared web service, also restrict outbound network access and apply request limits at the hosting layer.

## Features
- 🚀 **Advanced Web Scraping**: Capture readable content from public HTTP(S) pages with configurable content waits, bounded retries and diagnostic artifacts
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
- Python 3.10 or higher
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
4. 👁️ **Review Content**: View the numbered source blocks in the expander
5. 📝 **Describe Parsing**: Describe what specific information you want to extract
6. 🚀 **Extract Records**: Choose structured output, specify fields (for example `name,price`), and click "Extract records"; free-text mode remains available
7. 📊 **View Results**: Review the extracted information
8. 💾 **Download**: Save structured JSON with source evidence, or text in free-text mode

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

## Structured records and source evidence

Structured mode is the default. Provide a task description and 1–12 comma-separated field names such as `name,price` or `name,email`. The model returns a schema-constrained JSON records array. Each non-null value must include a block ID and an exact source quote containing that value. Unknown values and their evidence must be `null`. Malformed output follows the existing bounded retry/fallback policy; unverifiable records are removed and reported explicitly.

`structured_content.py` preserves short values, article/list record boundaries, table row/header associations and visible contact details in headers or footers. Scripts, navigation and explicitly hidden markup are omitted. Ordinary records are packed whole within a character budget. Oversized individual blocks use overlapping windows; this cannot guarantee reconstruction of arbitrarily long records. Cross-chunk exact duplicate value objects are merged while retaining alternate evidence sets. Distinct entities with identical requested fields may also merge, so include an identity field when distinguishing them matters.

The UI displays values in a table and includes source blocks, field evidence, model names, rejected records, failed chunks and status in the JSON export. It retains the last extraction across reruns/downloads and clears it when another scrape starts. Failed extraction is not offered as successful data, and partial results are labelled.

Evidence checks prove that strings occur in visible canonical source text. They do not prove correct field semantics, correct association between entities, or immunity to prompt injection. This is still a local extraction tool, not a verified general-purpose web automation service.

### Reproduce the paired quality benchmark

The repository includes 16 manually specified **synthetic HTML regression fixtures**, covering products, tables, one-character values, contacts, missing fields, duplicate listings, multilingual text, hidden/script content, no matches, boundary-spanning input and instruction-like webpage text. Expected records are defined before model execution. These fixtures are not a representative sample of real websites.

```bash
python -m pip install -r requirements-benchmark.txt
# Install/start an Ollama model, then choose its exact name from ollama list.
python evaluation/benchmark.py --model YOUR_INSTALLED_MODEL
```

The benchmark alternates old/new execution order and uses the same model, temperature 0, seed 42, 8,192-token context, 2,048-token output limit and 1,400-character source budget. The baseline is the former cleaning/character-splitting/free-text pipeline, explicitly asked for JSON so it receives the same target field definitions. It permits Markdown fences and concatenated JSON but does not repair values or remove duplicates. The improved pipeline adds semantic blocks, native structured output, evidence validation and deduplication together; this is a combined configuration comparison, not a single-component ablation.

Reports record input/code hashes, installed model digest, each prediction, chunk failures, rejected records, exact-match quality and whole-extraction latency. The output directory cannot be overwritten. A rerun on another model or device is a separate experiment. No live browser fetch, OCR, pagination or CAPTCHA handling is measured by this benchmark.

For structured extraction with the benchmark's installed model, configure both primary and fallback deliberately (the measured run uses the same model for both):

```bash
export OLLAMA_MODEL='qwen3.8:27b-mlx'
export OLLAMA_FALLBACK_MODEL='qwen3.8:27b-mlx'
streamlit run main.py
```

Use a model actually available on your machine; the default `gpt-oss:20b` and `llama3.1:8b` are supported configuration choices, not models validated by this benchmark.

### Measured paired result (2026-09-30)

Actual local model: `qwen3.8:27b-mlx`, digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`. One frozen run on all 16 fixtures, with 24 unique expected records and 51 non-null expected fields:

| Metric | Legacy pipeline | Structured pipeline |
| --- | ---: | ---: |
| Field exact-match precision | 0.89744 | 1.00000 |
| Field exact-match recall | 0.68627 | 0.88235 |
| Field exact-match F1 | 0.77778 | **0.93750** |
| Record exact-match F1 | 0.72727 | **0.93333** |
| Values unsupported by visible canonical source | 4 / 39 | 0 / 45 |
| Whole extraction time across 16 cases | 147.75 s | 248.25 s |
| Model calls including retries | 17 | 20 |
| Cases returning no usable result | 1 | 2 |

Fields are scored as a multiset of `(first requested field, field name, verbatim value)` triples, so mixing attributes from different records is penalized. Records require every requested field (including nulls) to match. Duplicate predictions count as additional false positives. Empty-match cases are checked separately. Free-text output that cannot be decoded into the requested JSON records is counted as an unusable case; no values are inferred from malformed responses.

The improved run recovered table short values, header/footer contacts and the boundary record, and excluded hidden listings. It missed the `script_noise` and `row_headers` cases. Their raw responses and failure/rejection details are preserved. Strict evidence validation can remove useful answers when model citations are incorrect; native structured generation can also fail or return malformed records. The aggregate quality gain comes with **about 68% more extraction wall time** in this run.

Zero unsupported returned values is a lexical source-presence result, not proof of zero hallucinations, semantic correctness or prompt-injection resistance. The fixture set is small and synthetic, and does not establish live-web performance or production readiness.

[Full metrics and per-case predictions](evaluation/reports/structured_benchmark_20260930.json) and [raw model responses / grounded records](evaluation/reports/raw_responses_20260930.jsonl) are included with hashes. Generated runs remain local under `runs/structured-benchmark/`.

**Resume wording:** “Built a source-verifiable local LLM extraction pipeline with semantic HTML blocks, structured JSON and duplicate merging; on 16 fixed synthetic regression fixtures, improved field exact-match F1 from 0.778 to 0.938 and record F1 from 0.727 to 0.933, with published raw responses and latency tradeoffs.”

## Browser reliability and real-page evaluation (2026-10-08)

### Capture behavior

The app now uses `scrape_page()` and a structured `ScrapeResult`. The original `scrape_website()` remains an HTML-returning compatibility wrapper; its optional `wait_time` is now a content deadline, not a fixed sleep.

- Defaults: 12-second navigation timeout, 10-second content timeout, 40-second overall budget, 0.75-second non-empty content stability and at most two attempts. Retry backoff is 0.5 seconds; all attempts share the overall budget.
- Specify a CSS content selector for dynamic pages. Without one, the heuristic watches non-empty visible `main`, `article` or `[role=main]` text and falls back to body text if those candidates are empty or hidden. An explicit selector never falls back to unrelated body content. A stable loading placeholder can still appear ready; stability does not prove that every asynchronous record has arrived.
- Each attempt uses a fresh Chrome session. Selenium Manager provisions the driver by default; `CHROMEDRIVER` and `CHROME_BINARY` can supply known local binaries. A successful `python setup_chromedriver.py` persists its verified driver path and browser version in ignored `runs/chromedriver.json`, which subsequent captures reuse before invoking Selenium Manager. Missing or mismatched saved drivers fall back to Manager; rerun setup after a Chrome upgrade. Chrome's sandbox is enabled by default.
- A supervised child process bounds driver startup, DNS checks, navigation, content polling and artifact capture. POSIX process groups are terminated on completion/timeout; cleanup has a short grace period. Windows tree termination is implemented but not verified by this macOS/Linux test matrix.
- Outcomes distinguish invalid/public-policy-rejected URLs, blocked final redirects, navigation/content/overall timeouts, empty content, invalid selectors, excessive HTML, network/browser failures and worker crashes. Configuration/policy failures are not retried.
- HTML/screenshot diagnostics are retained when capture has time to produce them, together with attempt outcomes, requested/final URL, browser version, elapsed time and an HTML hash. A hard startup/deadline failure may have no screenshot. Generated artifacts live under ignored `runs/browser/`.
- The UI preserves capture diagnostics across reruns, shows the browser screenshot and provides HTML/report downloads. Extraction exports include capture provenance and the final source URL. Failure diagnostics are not extracted records.

Redirect policy is checked after navigation/URL changes, not before every browser network request. It does not prevent an initial redirected/subresource request or DNS rebinding. Shared hosting still requires network egress controls; this remains a local tool.

```bash
python -m pip install -r requirements-browser.txt
python -m unittest discover -s tests -p 'test_*.py'
# Actual browser tests; Selenium Manager may need internet for initial provisioning.
RUN_BROWSER_TESTS=1 python -m unittest discover -s tests/browser -v
```

The eight browser tests use an explicitly injected **exact localhost origin** on a controlled server. The UI and default capture API continue to reject private URLs. These tests measure delayed content, unstable/empty targets, redirects, retries, invalid CSS and navigation/overall deadlines; they are not public-web accuracy evidence. The browser test suite provisions Chrome before timing individual scenarios. CI runs them separately from the 33 isolated unit/UI/reference/driver tests.

### Frozen versus live public-page benchmark

[evaluation/public_pages.json](evaluation/public_pages.json) specifies six permitted public practice pages across three hosts: three book detail pages, static and JavaScript quote pages, and a countries page. The quote views intentionally share content to exercise JavaScript capture. This is a small demo-site sample, not six independent real-world applications.

Reference fields are joined within each record using predefined DOM selectors, then frozen **before LLM inference**. Model inputs are explicitly bounded to the first 1–3 record regions per page (10 records / 20 non-null fields in total). This does not benchmark whole-site extraction, pagination, authentication, CAPTCHA, OCR or unlimited scrolling. Source URLs, hashes and reference rules are retained. Full capture HTML/screenshots remain local; small model-input snapshot regions are committed for reproduction.

```bash
# Freeze a new dated dataset; never overwrite existing evidence.
python evaluation/public_benchmark.py freeze --output runs/public-web/frozen
# Reproduce extraction from committed snapshots without invoking a browser:
python evaluation/public_benchmark.py evaluate \
  --dataset evaluation/public_snapshots/20261008 \
  --output runs/public-web/frozen-only --model YOUR_INSTALLED_MODEL --mode frozen
# Both modes: frozen snapshots and a new live browser pass, alternating order.
python evaluation/public_benchmark.py evaluate \
  --dataset evaluation/public_snapshots/20261008 \
  --output runs/public-web/both --model YOUR_INSTALLED_MODEL --mode both
```

Mutation of frozen snapshots is rejected. Live reference drift—including missing record regions, missing fields or empty fields—is reported and excluded from quality scoring, without calling the model. When every reference drifts, quality rates are null rather than a zero-accuracy claim. Actual browser capture failures are included as missed expected records when the reference remains valid. Field scoring uses the first requested field as the record-identity anchor, so a changed anchor also penalizes associated fields. No semantic normalization or post-result reference editing is applied.

Actual model: `qwen3.8:27b-mlx`, digest `5642e97495e1a088883805981563dcdc4a040c2f53388b7a41d1f24d3622cf7e`, local MLX runner. Chrome `154.0.8037.97`, Selenium `4.50.0`, Python `3.12.13` on macOS. The same extractor, model and frozen references were used in both modes:

| Measurement | Frozen regions | Live browser + scoped extraction |
| --- | ---: | ---: |
| Public-page capture success | Not applicable | 6 / 6 |
| Field exact-match precision / recall / F1 | 0.600 / 0.600 / 0.600 | 0.600 / 0.600 / 0.600 |
| Record exact-match F1 | 0.600 | 0.600 |
| Whole-run extraction/capture time, summed over cases | 116.82 s | 133.15 s |
| Returned values absent from canonical source | 0 | 0 |

The book and country records match exactly. In both quote views, the model omits the displayed outer quotation marks. The frozen reference retains them, so the quote identity anchor and associated author field count as mismatches even though authors are correctly named. Raw responses, returned records and scores are preserved in [public_web_20261008.json](evaluation/reports/public_web_20261008.json). This lexical metric is not a semantic judgment, and zero unsupported strings is not proof of zero hallucinations.

These measurements are **not a paired legacy improvement result** and cannot be compared directly with the earlier 16 synthetic fixtures. Successful capture on six scoped demo pages does not establish production readiness. The next extraction-quality study should reserve new evaluation pages before changing prompts or normalization rules in response to these failures.


### Review hardening

Benchmark metadata tolerates absent optional packages (for example Streamlit/Selenium during frozen-only evaluation), recording their versions as null instead of failing after model inference. Provenance is captured before processing: code hashes include the scoring/client module, configuration, URL policy and driver resolver, and effective inference settings include context, generation limits, retries, timeout and an endpoint hash. Existing published reports remain historical evidence from their recorded code version; these fixes do not replace their responses or scores.
