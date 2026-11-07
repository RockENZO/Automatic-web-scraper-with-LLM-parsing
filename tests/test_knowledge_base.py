import hashlib
import re
import unittest

from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import MockLLM

from knowledge_base import answer, build_index, records_to_documents, retrieve


class HashingEmbedding(BaseEmbedding):
    """Deterministic bag-of-words embedding, so retrieval results are stable across runs."""

    dim: int = 128

    def _embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dim
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            bucket = int(hashlib.md5(token.encode()).hexdigest(), 16) % self.dim
            vector[bucket] += 1.0
        norm = sum(v * v for v in vector) ** 0.5 or 1.0
        return [v / norm for v in vector]

    def _get_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)

    def _get_text_embedding(self, text: str) -> list[float]:
        return self._embed(text)

    async def _aget_query_embedding(self, query: str) -> list[float]:
        return self._embed(query)


RECORDS = [
    {"url": "https://shop.example/kettle", "text": "Blue kettle costs 24 dollars. Stainless steel, 1.5 litre."},
    {"url": "https://shop.example/hours", "text": "Opening hours: Monday to Friday, 9 to 5."},
    {"url": "https://shop.example/returns", "text": "Returns are accepted within 30 days of purchase."},
    {"url": "https://shop.example/empty", "text": "   "},
]


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.index = build_index(RECORDS, HashingEmbedding())

    def test_empty_records_are_dropped_and_urls_are_kept(self):
        documents = records_to_documents(RECORDS)
        self.assertEqual(len(documents), 3)
        self.assertEqual(documents[0].metadata["url"], "https://shop.example/kettle")

    def test_question_retrieves_the_page_that_answers_it(self):
        hits = retrieve(self.index, "How much does the blue kettle cost?", top_k=1)
        self.assertEqual(hits[0]["url"], "https://shop.example/kettle")
        self.assertIn("24 dollars", hits[0]["text"])

    def test_retrieval_is_ordered_by_similarity(self):
        hits = retrieve(self.index, "When are the opening hours?", top_k=3)
        self.assertEqual(hits[0]["url"], "https://shop.example/hours")
        scores = [h["score"] for h in hits]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_answer_reports_the_sources_it_used(self):
        result = answer(self.index, "How much does the blue kettle cost?", MockLLM(max_tokens=16), top_k=1)
        self.assertEqual(result["sources"], ["https://shop.example/kettle"])
        self.assertIsInstance(result["answer"], str)


if __name__ == "__main__":
    unittest.main()
