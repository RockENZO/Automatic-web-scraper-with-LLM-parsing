import json
import unittest
from unittest.mock import Mock, patch
from structured_content import Block, extract_blocks, chunk_blocks
from structured_parse import extract_structured, validate_response, validate_fields


class StructuredTests(unittest.TestCase):
    def test_deeply_nested_page_does_not_exhaust_python_stack(self):
        html = '<div>' * 1500 + '<article><p>Ada</p></article>' + '</div>' * 1500
        self.assertEqual([b.text for b in extract_blocks(html)], ['Ada'])

    def test_iterative_walk_keeps_record_and_loose_text_order(self):
        html = '<div>before<article>one</article>between<div><article>two</article></div>after</div>'
        self.assertEqual([b.text for b in extract_blocks(html)], ['before', 'one', 'between', 'two', 'after'])

    def test_table_headers_short_values_and_visible_contacts(self):
        html = '<body><header><address>a@b.test</address></header><div hidden>secret</div><table><tr><th>name</th><th>quantity</th></tr><tr><td>A</td><td>1</td></tr></table></body>'
        blocks = extract_blocks(html)
        self.assertEqual([b.text for b in blocks], ['a@b.test', 'name: A\nquantity: 1'])

    def test_repeated_header_rows_are_not_extraction_records(self):
        html='<table><tr><th>Name</th><th>Price</th></tr><tr><td>Ada</td><td>10</td></tr><tr><th>Name</th><th>Price</th></tr><tr><td>Bob</td><td>20</td></tr></table>'
        self.assertEqual([b.text for b in extract_blocks(html)],
                         ['Name: Ada\nPrice: 10','Name: Bob\nPrice: 20'])

    def test_new_column_header_applies_to_following_records(self):
        html='<table><tr><th>Name</th><th>Price</th></tr><tr><td>Ada</td><td>10</td></tr><tr><th>Name</th><th>Quantity</th></tr><tr><td>Bob</td><td>2</td></tr></table>'
        self.assertEqual([b.text for b in extract_blocks(html)],
                         ['Name: Ada\nPrice: 10','Name: Bob\nQuantity: 2'])

    def test_explicit_row_header_cells_remain_data(self):
        html='<table><tr><th>Name</th><th>Price</th></tr><tr><th scope="row">Ada</th><th scope="row">10</th></tr></table>'
        self.assertEqual([b.text for b in extract_blocks(html)],['Name: Ada\nPrice: 10'])

    def test_spanning_group_header_preserves_columns(self):
        html='<table><tr><th>Name</th><th>Price</th></tr><tr><th colspan="2">Featured</th></tr><tr><td>Ada</td><td>10</td></tr></table>'
        self.assertEqual([b.text for b in extract_blocks(html)],['Name: Ada\nPrice: 10'])

    def test_uppercase_row_scope_remains_data(self):
        html='<table><tr><th>Name</th><th>Price</th></tr><tr><th scope="ROW">Ada</th><th scope="ROW">10</th></tr></table>'
        self.assertEqual([b.text for b in extract_blocks(html)],['Name: Ada\nPrice: 10'])

    def test_nested_headers_do_not_replace_outer_columns(self):
        html='<table><tr><th>Name</th><th>Details</th></tr><tr><td>Ada</td><td><table><tr><th>Key</th><th>Value</th></tr><tr><td>x</td><td>1</td></tr></table></td></tr><tr><td>Bob</td><td>plain</td></tr></table>'
        blocks=[b.text for b in extract_blocks(html)]
        self.assertEqual(blocks[-1],'Name: Bob\nDetails: plain')
        self.assertEqual(len(blocks),2)

    def test_records_stay_whole_and_oversized_windows_overlap(self):
        blocks = [Block('a','A'*80),Block('b','B'*80)]
        chunks = chunk_blocks(blocks,180,20)
        self.assertEqual(len(chunks),2)
        text = 'one two three four '*40
        chunks = chunk_blocks([Block('long',text)],180,20)
        self.assertTrue(all(sum(len(b.text)+len(b.id)+12 for b in c)<=180 for c in chunks))
        self.assertTrue(all(c[0].id=='long' for c in chunks))
        self.assertEqual(chunks[0][0].text[-20:],chunks[1][0].text[:20])

    def record(self,value='Ada'):
        return {'values':{'name':value},'evidence':{'name':{'block_id':'b1','quote':'name: '+value}}}

    def test_unsupported_value_or_foreign_block_rejected(self):
        source = [Block('b1','name: Ada')]
        good,bad = validate_response(json.dumps({'records':[self.record('Ada'),self.record('Fake')]}),source,['name'])
        self.assertEqual(len(good),1)
        self.assertEqual(len(bad),1)
        item=self.record();item['evidence']['name']['block_id']='other'
        self.assertEqual(len(validate_response(json.dumps({'records':[item]}),source,['name'])[1]),1)

    def test_invalid_json_retries_and_uses_fallback(self):
        primary,fallback=Mock(),Mock()
        primary.invoke.return_value='not json'
        fallback.invoke.return_value=json.dumps({'records':[self.record()]})
        with patch('config.OLLAMA_MODEL','primary'),patch('config.OLLAMA_FALLBACK_MODEL','fallback'):
            result=extract_structured([[Block('b1','name: Ada')]],'name',['name'],model_factory=lambda name:primary if name=='primary' else fallback,sleep=lambda _:None)
        self.assertEqual(result.status,'success')
        self.assertEqual(result.models_used,['fallback'])

    def test_duplicate_records_are_merged_and_failure_visible(self):
        model=Mock();model.invoke.side_effect=[json.dumps({'records':[self.record(),self.record()]})]+[TimeoutError()]*4
        with patch('config.OLLAMA_MODEL','primary'),patch('config.OLLAMA_FALLBACK_MODEL','fallback'):
            result=extract_structured([[Block('b1','name: Ada')],[Block('b2','name: Bob')]],'name',['name'],model_factory=lambda _:model,sleep=lambda _:None)
        self.assertEqual((result.status,len(result.records),result.duplicate_records,result.failed_chunks),('partial',1,1,[2]))

    def test_duplicate_json_keys_are_rejected_at_every_depth(self):
        for response in [
            '{"records":[{}],"records":[]}',
            '{"records":[{"values":{"name":"Bob","name":"Ada"},"evidence":{"name":{"block_id":"b1","quote":"name: Ada"}}}]}',
            '{"records":[{"values":{"name":"Ada"},"evidence":{"name":{"block_id":"wrong","block_id":"b1","quote":"name: Ada"}}}]}',
        ]:
            with self.subTest(response=response), self.assertRaisesRegex(ValueError,'Duplicate'):
                validate_response(response,[Block('b1','name: Ada')],['name'])

    def test_duplicate_keys_retry_instead_of_false_empty_success(self):
        model=Mock()
        model.invoke.side_effect=['{"records":[{}],"records":[]}',json.dumps({'records':[self.record()]})]
        result=extract_structured([[Block('b1','name: Ada')]],'name',['name'],model_factory=lambda _:model,sleep=lambda _:None)
        self.assertEqual(result.status,'success')
        self.assertEqual(len(result.records),1)
        self.assertEqual(model.invoke.call_count,2)

    def test_schema_and_empty_response(self):
        for fields in [[],['name','name'],['bad-field']]:
            with self.assertRaises(ValueError):validate_fields(fields)
        model=Mock();model.invoke.return_value='{"records": []}'
        self.assertEqual(extract_structured([[Block('b1','nothing')]],'contacts',['name'],model_factory=lambda _:model).status,'empty')
        with self.assertRaises(ValueError):validate_response('{"records":[{"wrong":1}]}',[Block('b1','x')],['name'])

if __name__=='__main__':unittest.main()
