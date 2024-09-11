import streamlit as st
from scrape import (
    scrape_website,
    split_dom_content,
    extract_body_content,
    clean_body_content,
)
from parse import parse_with_ollama


st.title("Automatic web scraper")
url = st.text_input("Enter the URL of the website you want to scrape")

if st.button("Scrape"):
    st.write(f"Scraping {url}...🤳")
    result = scrape_website(url)
    body_content = extract_body_content(result)
    cleaned_content = clean_body_content(body_content)
    st.session_state.dom_content = cleaned_content

    with st.expander("View DOM content"):
        st.text_area("DOM content", cleaned_content, height=300)

if "dom_content" in st.session_state:
    parse_description = st.text_area("Describe what you want to parse?")
    if st.button("Parse Content"):
        if parse_description:
            st.write("Parseing content...🔍")
            dom_chunks = split_dom_content(st.session_state.dom_content)
            results = parse_with_ollama(dom_chunks, parse_description)
            st.write(results)
