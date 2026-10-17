import io
import json
import unittest
from unittest.mock import patch, Mock
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

    def test_response_read_is_bounded_and_closes_on_oversize(self):
        body = io.BytesIO(b'{"done":true,"response":"' + b'x' * 100 + b'"}')
        with patch('ollama_client.urllib.request.urlopen', return_value=body):
            with self.assertRaises(ValueError):
                OllamaClient('test', max_response_bytes=64).invoke('prompt')
        self.assertTrue(body.closed)
        # The exact byte limit is accepted, including UTF-8 multibyte content.
        encoded = json.dumps({'done': True, 'response': '你好'}, ensure_ascii=False).encode()
        with patch('ollama_client.urllib.request.urlopen', return_value=io.BytesIO(encoded)):
            self.assertEqual(OllamaClient('test', max_response_bytes=len(encoded)).invoke('prompt'), '你好')

    def test_native_read_never_requests_unbounded_body(self):
        body = Mock(wraps=io.BytesIO(b'{"done":true,"response":"ok"}'))
        body.__enter__ = Mock(return_value=body)
        body.__exit__ = Mock(return_value=False)
        with patch('ollama_client.urllib.request.urlopen', return_value=body), patch('ollama_client.config.OLLAMA_MAX_RESPONSE_BYTES', 64, create=True):
            self.assertEqual(OllamaClient('test').invoke('prompt'), 'ok')
        body.read.assert_called_once_with(65)

    def test_invalid_response_limits_rejected_before_network(self):
        with patch('ollama_client.urllib.request.urlopen') as open_url:
            for limit in [0, -1, True, 1.5]:
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    OllamaClient('test', max_response_bytes=limit)
        open_url.assert_not_called()

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
