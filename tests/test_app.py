"""Verify table/evidence rendering and persistence using Streamlit's real AppTest."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
from structured_parse import StructuredResult


@unittest.skipUnless(importlib.util.find_spec('streamlit'),'Streamlit required for UI checks')
class AppTests(unittest.TestCase):
    def app(self):
        from streamlit.testing.v1 import AppTest
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'main.py'),default_timeout=20)
        app.session_state['page_html']='<body><article>name: Ada\nemail: ada@example.test</article></body>'
        app.session_state['original_url']='https://example.test'
        return app.run()

    def test_structured_table_evidence_and_rerun_persist(self):
        app=self.app()
        self.assertEqual(len(app.exception),0)
        app.text_area[0].set_value('Extract contacts')
        app.text_input[1].set_value('name,email')
        record={'values':{'name':'Ada','email':'ada@example.test'},'evidence':{'name':{'block_id':'b0001','quote':'name: Ada'},'email':{'block_id':'b0001','quote':'email: ada@example.test'}},'evidence_sets':[]}
        with patch('structured_parse.extract_structured',return_value=StructuredResult([record],1,1)) as extract:
            app.button[1].click().run()
            self.assertEqual(extract.call_count,1)
            self.assertEqual(len(app.exception),0)
            self.assertEqual(len(app.dataframe),1)
            self.assertEqual(len(app.json),1)
            document=app.session_state['extraction_document']
            self.assertEqual(document['records'][0]['values']['name'],'Ada')
            self.assertIn('b0001',document['source_blocks'])
            self.assertEqual(len(app.get('download_button')),1)
            app.run()
            self.assertEqual(extract.call_count,1)
            self.assertEqual(len(app.dataframe),1)

    def test_failure_has_no_download(self):
        app=self.app()
        app.text_area[0].set_value('Extract products')
        with patch('structured_parse.extract_structured',return_value=StructuredResult([],1,failed_chunks=[1])):
            app.button[1].click().run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.error),1)
        self.assertEqual(len(app.get('download_button')),0)

if __name__=='__main__':unittest.main()
