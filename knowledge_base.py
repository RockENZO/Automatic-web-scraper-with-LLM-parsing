"""A LlamaIndex knowledge base over extracted page text.

Each record is a dict with ``url`` and ``text``, typically one extracted block from a scraped
page. ``build_index`` stores them in a vector index, ``retrieve`` returns the closest records
with their source URLs, and ``answer`` runs a query engine over them. The embedding and LLM are
passed in, so the caller chooses the model. Nothing here calls a hosted service by default.
"""

from __future__ import annotations

from typing import Any

from llama_index.core import Document, VectorStoreIndex
from llama_index.core.base.embeddings.base import BaseEmbedding
from llama_index.core.llms import LLM


def records_to_documents(records: list[dict[str, Any]]) -> list[Document]:
    """Turn ``{"url", "text"}`` records into documents that keep their source URL."""
    documents = []
    for record in records:
        if not record.get("text", "").strip():
            continue
        documents.append(Document(text=record["text"], metadata={"url": record["url"]}))
    return documents


def build_index(records: list[dict[str, Any]], embed_model: BaseEmbedding) -> VectorStoreIndex:
    return VectorStoreIndex.from_documents(records_to_documents(records), embed_model=embed_model)


def retrieve(index: VectorStoreIndex, question: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return the top_k records for a question, most similar first, with their source URLs."""
    nodes = index.as_retriever(similarity_top_k=top_k).retrieve(question)
    return [
        {"url": node.node.metadata.get("url"), "score": node.score, "text": node.node.get_content()}
        for node in nodes
    ]


def answer(index: VectorStoreIndex, question: str, llm: LLM, top_k: int = 3) -> dict[str, Any]:
    """Answer a question from the index. Returns the response text and its source URLs."""
    engine = index.as_query_engine(llm=llm, similarity_top_k=top_k)
    response = engine.query(question)
    sources = [node.node.metadata.get("url") for node in response.source_nodes]
    return {"answer": str(response), "sources": sources}
