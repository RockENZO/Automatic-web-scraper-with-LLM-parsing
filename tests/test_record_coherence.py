"""Evidence from separate semantic records must not be joined implicitly."""
import json
import unittest
from unittest.mock import Mock
from structured_content import Block
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
