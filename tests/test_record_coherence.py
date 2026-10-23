"""Evidence from separate semantic records must not be joined implicitly."""
import json
import unittest
from unittest.mock import Mock
from structured_content import Block, extract_blocks
from structured_parse import validate_response, extract_structured


class RecordCoherenceTests(unittest.TestCase):
    def record(self, ids=('a', 'b')):
        return {'values': {'name': 'Ada', 'price': '20'}, 'evidence': {
            'name': {'block_id': ids[0], 'quote': 'name: Ada'},
            'price': {'block_id': ids[1], 'quote': 'price: 20'}}}

    def test_separately_supported_fields_cannot_fabricate_a_join(self):
        blocks = [Block('a', 'name: Ada\nprice: 10'), Block('b', 'name: Bob\nprice: 20')]
        good, bad = validate_response(json.dumps({'records': [self.record()]}), blocks, ['name', 'price'])
        self.assertEqual(good, [])
        self.assertEqual(bad, [{'record_index': 0, 'reason': 'cross_record_evidence'}])

    def test_same_record_windows_and_missing_fields_remain_valid(self):
        record = self.record(('a', 'a'))
        source = [Block('a', 'name: Ada'), Block('a', 'price: 20')]
        self.assertEqual(validate_response(json.dumps({'records': [record]}), source, ['name', 'price']), ([record], []))
        record['values']['price'] = record['evidence']['price'] = None
        self.assertEqual(validate_response(json.dumps({'records': [record]}), source, ['name', 'price']), ([record], []))

    def test_rejection_is_visible_without_losing_independent_valid_records(self):
        source = [Block('a', 'name: Ada\nprice: 10'), Block('b', 'name: Bob\nprice: 20')]
        valid = self.record(('b', 'b')); valid['values']['name'] = 'Bob'; valid['evidence']['name']['quote'] = 'name: Bob'
        model = Mock(); model.invoke.return_value = json.dumps({'records': [self.record(), valid]})
        result = extract_structured([source], 'products', ['name', 'price'], model_factory=lambda _: model)
        self.assertEqual(result.status, 'partial')
        self.assertEqual([r['values'] for r in result.records], [{'name': 'Bob', 'price': '20'}])
        self.assertEqual(result.rejected_records[0]['reason'], 'cross_record_evidence')


class NestedRecordBoundaryTests(unittest.TestCase):
    def test_nested_record_cards_do_not_share_parent_evidence(self):
        for parent, child in [('article', 'article'), ('article', 'li'), ('li', 'li'),
                              ('section data-record', 'div data-record'),
                              ('div itemscope', 'div itemscope')]:
            with self.subTest(parent=parent, child=child):
                close_parent, close_child = parent.split()[0], child.split()[0]
                html = (f'<{parent}><h1>Products</h1>'
                        f'<{child}><p>name: Ada</p><p>price: 10</p></{close_child}>'
                        f'<{child}><p>name: Bob</p><p>price: 20</p></{close_child}>'
                        f'</{close_parent}>')
                blocks = extract_blocks(html)
                ada = next(b for b in blocks if 'name: Ada' in b.text)
                bob = next(b for b in blocks if 'name: Bob' in b.text)
                self.assertNotEqual(ada.id, bob.id)
                self.assertNotIn('price: 20', ada.text)
                record = {'values': {'name': 'Ada', 'price': '20'}, 'evidence': {
                    'name': {'block_id': ada.id, 'quote': 'name: Ada'},
                    'price': {'block_id': bob.id, 'quote': 'price: 20'}}}
                good, bad = validate_response(json.dumps({'records': [record]}), blocks, ['name', 'price'])
                self.assertEqual(good, [])
                self.assertEqual(bad[0]['reason'], 'cross_record_evidence')

    def test_one_card_keeps_its_field_paragraphs_together(self):
        blocks = extract_blocks('<article><h2>Ada</h2><p>price: 10</p><p>stock: 2</p></article>')
        self.assertEqual([b.text for b in blocks], ['Ada\nprice: 10\nstock: 2'])

    def test_hidden_nested_records_do_not_split_visible_card(self):
        blocks = extract_blocks('<article><p>name: Ada</p><div data-record hidden>secret</div><p>price: 10</p></article>')
        self.assertEqual([b.text for b in blocks], ['name: Ada\nprice: 10'])
