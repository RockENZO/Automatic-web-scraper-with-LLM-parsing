import io
import json
import unittest
from unittest.mock import patch
from ollama_client import OllamaClient


class OllamaClientTests(unittest.TestCase):
    def invoke(self, payload):
        with patch('ollama_client.urllib.request.urlopen', return_value=io.BytesIO(json.dumps(payload).encode())):
            return OllamaClient('test').invoke('prompt')

    def test_incomplete_or_malformed_responses_rejected(self):
        for payload in [
            {'response': 'partial'}, {'response': 'partial', 'done': False},
            {'response': 'partial', 'done': 1}, {'response': 'partial', 'done': 'true'},
            {'response': 'partial', 'done': True, 'done_reason': 'length'},
            {'response': 'partial', 'done': True, 'error': 'model error'},
            [], None, {'response': 123, 'done': True},
        ]:
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                self.invoke(payload)

    def test_completed_response_and_empty_text(self):
        self.assertEqual(self.invoke({'done': True, 'response': 'ok'}), 'ok')
        self.assertEqual(self.invoke({'done': True, 'response': ''}), '')

    def test_request_uses_native_nonstreaming_schema_and_timeout(self):
        with patch('ollama_client.urllib.request.urlopen', return_value=io.BytesIO(b'{"done":true,"response":"ok"}')) as open_url:
            client=OllamaClient('test', base_url='http://localhost:11434/', timeout=7)
            client.invoke('prompt', schema={'type':'object'})
        request=open_url.call_args.args[0]
        payload=json.loads(request.data)
        self.assertEqual(request.full_url, 'http://localhost:11434/api/generate')
        self.assertEqual(payload['format'], {'type':'object'})
        self.assertIs(payload['stream'], False)
        self.assertEqual(open_url.call_args.kwargs['timeout'],7)
