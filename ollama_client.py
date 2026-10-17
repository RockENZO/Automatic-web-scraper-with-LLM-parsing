"""Small native Ollama client shared by structured extraction and benchmarks."""
import json
import urllib.request
import config


class OllamaClient:
    def __init__(self, model, *, base_url=None, timeout=None, max_response_bytes=None):
        self.max_response_bytes = (config.OLLAMA_MAX_RESPONSE_BYTES
                                   if max_response_bytes is None else max_response_bytes)
        if type(self.max_response_bytes) is not int or self.max_response_bytes <= 0:
            raise ValueError('Response byte limit must be a positive integer')
        self.model = model
        self.base_url = (base_url or config.OLLAMA_BASE_URL).rstrip('/')
        self.timeout = timeout or config.OLLAMA_TIMEOUT

    def invoke(self, prompt, schema=None):
        payload = {'model': self.model, 'prompt': prompt, 'stream': False,
                   'options': {'temperature': 0, 'seed': 42,
                               'num_ctx': config.OLLAMA_NUM_CTX,
                               'num_predict': 2048}}
        if schema is not None:
            payload['format'] = schema
        request = urllib.request.Request(self.base_url + '/api/generate',
                                         data=json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json'})
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            body = response.read(self.max_response_bytes + 1)
            if len(body) > self.max_response_bytes:
                raise ValueError('Ollama response exceeds configured byte limit')
            result = json.loads(body)
        if not isinstance(result, dict):
            raise ValueError('Ollama returned an invalid response object')
        if result.get('error'):
            raise ValueError('Ollama reported a model error')
        if result.get('done') is not True or result.get('done_reason') == 'length':
            raise ValueError('Model response was truncated')
        text = result.get('response')
        if not isinstance(text, str):
            raise ValueError('Ollama did not return text')
        return text
