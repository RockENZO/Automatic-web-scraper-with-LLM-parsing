import unittest
from unittest.mock import Mock
import config
from parse import parse_with_ollama

class ParseTests(unittest.TestCase):
    def test_success_empty_and_progress(self):
        model = Mock()
        model.invoke.side_effect = ['value', '']
        progress = Mock()
        result = parse_with_ollama(['one', 'two'], 'price', model_factory=lambda _: model, progress=progress)
        self.assertEqual((result.status, result.text, result.completed_chunks), ('success', 'value', 2))
        progress.assert_called_with(2, 2)
        model.invoke.return_value = ''
        model.invoke.side_effect = None
        self.assertEqual(parse_with_ollama(['one'], 'price', model_factory=lambda _: model).status, 'empty')

    def test_invocation_failure_uses_fallback(self):
        primary, fallback = Mock(), Mock()
        primary.invoke.side_effect = ConnectionError()
        fallback.invoke.return_value = 'recovered'
        result = parse_with_ollama(['one'], 'price', model_factory=lambda name: primary if name == config.OLLAMA_MODEL else fallback, sleep=lambda _: None)
        self.assertEqual(result.models_used, [config.OLLAMA_FALLBACK_MODEL])
        self.assertEqual(result.status, 'success')

    def test_total_failure_has_no_download_text(self):
        model = Mock()
        model.invoke.side_effect = TimeoutError()
        result = parse_with_ollama(['one'], 'price', model_factory=lambda _: model, sleep=lambda _: None)
        self.assertEqual((result.status, result.text, result.failed_chunks), ('failed', '', [1]))
        self.assertEqual(model.invoke.call_count, config.OLLAMA_ATTEMPTS * 2)

    def test_partial_results_are_explicit(self):
        model = Mock()
        model.invoke.side_effect = ['ok'] + [RuntimeError()] * 4
        result = parse_with_ollama(['one', 'two'], 'price', model_factory=lambda _: model, sleep=lambda _: None)
        self.assertEqual((result.status, result.text, result.failed_chunks, result.completed_chunks), ('partial', 'ok', [2], 1))

    def test_invalid_input(self):
        for chunks, description in [([], 'price'), ([''], 'price'), (['one'], ''), (['x' * (config.MAX_CHUNK_SIZE + 1)], 'price')]:
            with self.assertRaises(ValueError):
                parse_with_ollama(chunks, description)

if __name__ == '__main__':
    unittest.main()
