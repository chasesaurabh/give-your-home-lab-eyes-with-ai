"""A deterministic lexical retrieval baseline with source-bearing results."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from .document import DocumentChunk


TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.IGNORECASE)


def tokenize(text: str) -> tuple[str, ...]:
    return tuple(match.group(0).lower() for match in TOKEN_PATTERN.finditer(text))


@dataclass(frozen=True, slots=True)
class RetrievalHit:
    score: float
    chunk: DocumentChunk


class LexicalIndex:
    """Small-corpus BM25 baseline; no embeddings or opaque service required."""

    def __init__(self, chunks: tuple[DocumentChunk, ...], *, k1: float = 1.2, b: float = 0.75):
        if not chunks:
            raise ValueError("at least one document chunk is required")
        self._chunks = chunks
        self._k1 = k1
        self._b = b
        self._terms = tuple(Counter(tokenize(chunk.text)) for chunk in chunks)
        self._lengths = tuple(sum(counter.values()) for counter in self._terms)
        self._average_length = sum(self._lengths) / len(self._lengths)
        self._document_frequency = Counter()
        for terms in self._terms:
            self._document_frequency.update(terms.keys())

    def search(self, query: str, *, top_k: int = 5) -> tuple[RetrievalHit, ...]:
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_terms = set(tokenize(query))
        if not query_terms:
            return ()

        document_count = len(self._chunks)
        hits: list[RetrievalHit] = []
        for chunk, terms, length in zip(self._chunks, self._terms, self._lengths):
            score = 0.0
            for term in query_terms:
                frequency = terms.get(term, 0)
                if not frequency:
                    continue
                document_frequency = self._document_frequency[term]
                inverse_frequency = math.log(
                    1 + (document_count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                length_factor = frequency + self._k1 * (
                    1 - self._b + self._b * length / self._average_length
                )
                score += inverse_frequency * frequency * (self._k1 + 1) / length_factor
            if score > 0:
                hits.append(RetrievalHit(score=score, chunk=chunk))

        hits.sort(key=lambda hit: (-hit.score, hit.chunk.chunk_id))
        return tuple(hits[:top_k])
