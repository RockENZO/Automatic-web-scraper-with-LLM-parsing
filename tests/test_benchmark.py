import unittest
from unittest.mock import patch
from evaluation.benchmark import capture_provenance
from evaluation.benchmark import score, rates, decode_legacy


class BenchmarkTests(unittest.TestCase):
    def test_effective_response_limit_is_distinguishable_in_provenance(self):
        with patch('evaluation.benchmark.config.OLLAMA_MAX_RESPONSE_BYTES', 64):
            first = capture_provenance()
        with patch('evaluation.benchmark.config.OLLAMA_MAX_RESPONSE_BYTES', 128):
            second = capture_provenance()
        self.assertEqual(first['response_limit_bytes'], 64)
        self.assertEqual(second['response_limit_bytes'], 128)
        self.assertNotEqual(first, second)
        self.assertEqual(len(first['code_hashes']['config.py']), 64)

    def test_duplicates_penalized_and_missing_fields_reduce_recall(self):
        expected=[{'name':'A','price':'$2'},{'name':'B','price':'$4'}]
        rows=[{'name':'A','price':'$2'},{'name':'A','price':'$2'}]
        result=score(rows,expected,['name','price'],'A $2 B $4')
        self.assertEqual(result['records'],{'tp':1,'predicted':2,'expected':2})
        self.assertEqual(rates(result['fields'])['f1'],.5)

    def test_mixed_records_and_unsupported_values(self):
        expected=[{'name':'A','price':'$2'},{'name':'B','price':'$4'}]
        result=score([{'name':'A','price':'$4'},{'name':'B','price':'$9'}],expected,['name','price'],'A $2 B $4')
        self.assertEqual(result['fields']['tp'],2)
        self.assertEqual(result['unsupported_values'],1)
        self.assertEqual(result['records']['tp'],0)

    def test_legacy_json_fragments_preserve_duplicates(self):
        rows=decode_legacy('```json\n{"records":[{"name":"A"}]}\n```\n{"records":[{"name":"A"}]}',['name'])
        self.assertEqual(len(rows),2)
        with self.assertRaises(ValueError):decode_legacy('not json',['name'])

if __name__=='__main__':unittest.main()
