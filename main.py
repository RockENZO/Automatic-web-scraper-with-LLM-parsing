import streamlit as st
import time
from scrape import (
    scrape_website,
    split_dom_content,
    extract_body_content,
    clean_body_content,
)
from parse import parse_with_ollama
import config

# Configure Streamlit page
st.set_page_config(
    page_title="Automatic Web Scraper",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Automatic Web Scraper")
st.caption(f"Ollama model: {config.OLLAMA_MODEL}; fallback: {config.OLLAMA_FALLBACK_MODEL}")

# Add sidebar with information
with st.sidebar:
    st.header("📋 How to use")
    st.markdown("""
    1. Enter a valid URL
    2. Click 'Scrape' to extract content
    3. Describe what you want to parse
    4. Click 'Parse Content' to get results
    """)
    
    st.header("⚙️ Settings")
    chunk_size = st.slider("Chunk size for processing", config.MIN_CHUNK_SIZE, config.MAX_CHUNK_SIZE, config.DEFAULT_CHUNK_SIZE, 500)

url = st.text_input("🌐 Enter the URL of the website you want to scrape", placeholder="https://example.com")

if st.button("🤳 Scrape Website", type="primary"):
    if not url:
        st.error("Please enter a valid URL")
    elif not url.startswith(('http://', 'https://')):
        st.error("Please enter a valid URL starting with http:// or https://")
    else:
        # Clear stale content before attempting a different URL.
        st.session_state.pop('dom_content', None)
        st.session_state.pop('original_url', None)
        with st.spinner(f"Scraping {url}..."):
            try:
                start_time = time.time()
                result = scrape_website(url)
                body_content = extract_body_content(result)
                cleaned_content = clean_body_content(body_content)
                
                if not cleaned_content.strip():
                    raise ValueError("The page has no readable text to extract")

                # Store in session state
                st.session_state.dom_content = cleaned_content
                st.session_state.original_url = url
                
                scrape_time = time.time() - start_time
                st.success(f"✅ Successfully scraped {url} in {scrape_time:.2f} seconds")
                
                # Show content stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Content Length", f"{len(cleaned_content):,} chars")
                with col2:
                    st.metric("Word Count", f"{len(cleaned_content.split()):,}")
                with col3:
                    estimated_chunks = (len(cleaned_content) + chunk_size - 1) // chunk_size
                    st.metric("Estimated Chunks", estimated_chunks)
                
            except Exception as e:
                st.error(f"❌ Error scraping website: {str(e)}")

# Show DOM content if available
if "dom_content" in st.session_state:
    with st.expander("👁️ View DOM Content", expanded=False):
        st.text_area(
            "Scraped Content", 
            st.session_state.dom_content, 
            height=300,
            help="This is the cleaned content extracted from the website"
        )

    # Parsing section
    st.divider()
    st.subheader("🔍 Parse Content")
    
    parse_description = st.text_area(
        "Describe what you want to extract from the content:",
        placeholder="e.g., Extract all email addresses, phone numbers, product prices, etc.",
        help="Be specific about what information you want to extract"
    )
    
    col1, col2 = st.columns([1, 4])
    with col1:
        parse_button = st.button("🚀 Parse Content", type="primary")
    with col2:
        if "original_url" in st.session_state:
            st.info(f"Parsing content from: {st.session_state.original_url}")
    
    if parse_button:
        if not parse_description:
            st.error("Please describe what you want to parse")
        else:
            with st.spinner("🔍 Parsing content with gpt-oss:20b..."):
                try:
                    start_time = time.time()
                    dom_chunks = split_dom_content(st.session_state.dom_content, chunk_size)
                    
                    # Show progress
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(done, total):
                        progress_bar.progress(done / total)
                        status_text.info(f"Processed {done}/{total} chunks")

                    result = parse_with_ollama(dom_chunks, parse_description, progress=update_progress)
                    parse_time = time.time() - start_time
                    if result.status == "failed":
                        status_text.error("Extraction failed for every chunk. Check Ollama is running and the configured models are installed.")
                    elif result.status == "partial":
                        status_text.warning(f"Incomplete extraction: {result.completed_chunks}/{result.total_chunks} chunks completed. Failed chunks: {result.failed_chunks}")
                    elif result.status == "empty":
                        status_text.info("Extraction completed; no matching information was returned.")
                    else:
                        status_text.success(f"Extraction completed in {parse_time:.2f} seconds")
                    if result.models_used:
                        st.caption("Models used: " + ", ".join(result.models_used))
                    if result.text:
                        st.subheader("Extraction results" if result.status == "success" else "Partial extraction results")
                        st.write(result.text)
                        st.download_button(
                            label="Download partial results" if result.status == "partial" else "Download results",
                            data=result.text,
                            file_name=f"{'partial_' if result.status == 'partial' else ''}parsed_results_{int(time.time())}.txt",
                            mime="text/plain"
                        )

                except Exception as e:
                    st.error(f"❌ Error during parsing: {str(e)}")
else:
    st.info("👆 Please scrape a website first to begin parsing content")
