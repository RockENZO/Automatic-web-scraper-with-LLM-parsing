"""Streamlit scraper with structured, source-verifiable extraction."""
import json
import time
import streamlit as st
from content import extract_body_content, clean_body_content, split_dom_content
from parse import parse_with_ollama
from structured_content import extract_blocks, chunk_blocks
from structured_parse import extract_structured, validate_fields
import config

st.set_page_config(page_title=config.PAGE_TITLE, page_icon=config.PAGE_ICON, layout='wide')
st.title('🤖 Automatic Web Scraper')
st.caption(f'Ollama model: {config.OLLAMA_MODEL}; fallback: {config.OLLAMA_FALLBACK_MODEL}')
with st.sidebar:
    st.header('How to use')
    st.markdown('1. Enter a public webpage URL.\n2. Scrape the page.\n3. Describe the records and fields you need.\n4. Extract and review the source evidence.')
    st.header('Settings')
    chunk_size=st.slider('Source chunk size',config.MIN_CHUNK_SIZE,config.MAX_CHUNK_SIZE,config.DEFAULT_CHUNK_SIZE,500)
    mode=st.radio('Output format',['Structured records','Free text'])

url=st.text_input('Webpage URL',placeholder='https://example.com')
if st.button('Scrape Website',type='primary'):
    for key in ['dom_content','page_html','original_url','extraction_document']:
        st.session_state.pop(key,None)
    if not url:
        st.error('Enter a webpage URL')
    else:
        with st.spinner('Loading webpage...'):
            try:
                from scrape import scrape_website
                start=time.perf_counter()
                html=scrape_website(url)
                blocks=extract_blocks(html)
                if not blocks:
                    raise ValueError('The page has no readable content')
                text='\n\n'.join(block.text for block in blocks)
                st.session_state.update(page_html=html,dom_content=text,original_url=url)
                st.success(f'Loaded webpage in {time.perf_counter()-start:.2f} seconds')
                st.metric('Readable source characters',f'{len(text):,}')
            except Exception as error:
                st.error(f'Unable to load webpage: {error}')

if 'page_html' in st.session_state:
    blocks=extract_blocks(st.session_state.page_html)
    with st.expander('View source blocks'):
        for block in blocks:
            st.text(f'[{block.id}] {block.text}')
    st.subheader('Extract content')
    description=st.text_area('What records should be extracted?',placeholder='Extract product names and prices, using null when a price is missing.')
    field_text=st.text_input('Fields (comma-separated)',value='name,price',help='Use unique field names with letters, numbers or underscores.') if mode=='Structured records' else None
    st.caption('Source: '+st.session_state.original_url)
    if st.button('Extract records' if mode=='Structured records' else 'Parse Content',type='primary'):
        try:
            if not description.strip():
                raise ValueError('Describe the information to extract')
            fields=validate_fields([field.strip() for field in field_text.split(',')]) if field_text is not None else None
            chunks=chunk_blocks(blocks,chunk_size) if fields else split_dom_content(clean_body_content(extract_body_content(st.session_state.page_html)),chunk_size)
            progress_bar=st.progress(0)
            def update_progress(done,total):
                progress_bar.progress(done/total)
            start=time.perf_counter()
            with st.spinner('Extracting content...'):
                result=extract_structured(chunks,description,fields,progress=update_progress) if fields else parse_with_ollama(chunks,description,progress=update_progress)
            elapsed=time.perf_counter()-start
            if fields:
                document={'source_url':st.session_state.original_url,'fields':fields,'description':description,'elapsed_seconds':elapsed,**result.as_dict(),
                          'source_blocks':{block.id:block.text for block in blocks}}
            else:
                document={'source_url':st.session_state.original_url,'fields':None,'description':description,'elapsed_seconds':elapsed,'status':result.status,'text':result.text,'models_used':result.models_used,'failed_chunks':result.failed_chunks}
            st.session_state.extraction_document=document
        except Exception as error:
            st.error(f'Extraction error: {error}')
    if 'extraction_document' in st.session_state:
        document=st.session_state.extraction_document
        status=document['status']
        if status=='failed':
            st.error('No usable extraction. Check the configured models and review rejected records or failed chunks below.')
        elif status=='partial':
            st.warning('Incomplete extraction: some chunks failed or records could not be verified. Review details before using these results.')
        elif status=='empty':
            st.info('Extraction completed; no matching records were returned.')
        else:
            st.success(f"Extraction completed in {document['elapsed_seconds']:.2f} seconds")
        st.caption('Request: '+document['description'])
        if document['models_used']:
            st.caption('Models used: '+', '.join(document['models_used']))
        if document['fields']:
            records=document['records']
            st.caption(f"{len(records)} records; {document['duplicate_records']} duplicates merged; {len(document['rejected_records'])} unsupported records removed.")
            if records:
                st.dataframe([record['values'] for record in records],hide_index=True)
                st.caption('Evidence confirms that text appears in the source. Review whether each value belongs to the correct record and field.')
                st.download_button('Download partial JSON' if status=='partial' else 'Download JSON',json.dumps(document,ensure_ascii=False,indent=2),file_name='partial_records.json' if status=='partial' else 'records.json',mime='application/json')
            with st.expander('Evidence and extraction details'):
                st.json(document)
        elif document['text']:
            st.text(document['text'])
            st.download_button('Download partial results' if status=='partial' else 'Download results',document['text'],file_name='partial_results.txt' if status=='partial' else 'results.txt',mime='text/plain')
else:
    st.info('Scrape a webpage to start extracting records.')
