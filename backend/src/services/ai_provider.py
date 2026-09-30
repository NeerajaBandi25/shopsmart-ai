"""Replaceable, deterministic AI provider boundaries."""

import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    text: str
    source_label: str
    page_number: int | None
    chunk_index: int


@dataclass(frozen=True)
class ProviderAnswer:
    answer: str
    answerable: bool
    token_count: int
    evidence_ids: tuple[str, ...] = ()


class EmbeddingProvider:
    """Protocol-like base for local or external embedding providers."""

    dimensions = 64

    def embed(self, text: str) -> list[float]:
        values = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9]+", text.lower()):
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:2], "big") % self.dimensions
            values[index] += 1.0
        norm = sum(value * value for value in values) ** 0.5 or 1.0
        return [value / norm for value in values]


class GroundedAnswerProvider:
    """Safe local provider: evidence is data, never executable instructions."""

    injection_markers = ("ignore previous", "system prompt", "reveal secret", "follow these instructions")
    stopwords = {"a", "an", "and", "are", "does", "explain", "is", "of", "the", "that", "to", "what", "which"}

    def answer(self, question: str, evidence: list[Evidence]) -> ProviderAnswer:
        if not evidence:
            return ProviderAnswer("I couldn't find enough evidence in your documents to answer that.", False, 0)
        safe = [item for item in evidence if not any(marker in item.text.lower() for marker in self.injection_markers)]
        if not safe:
            return ProviderAnswer("I couldn't use the retrieved content safely to answer that.", False, 0)
        question_terms = set(re.findall(r"[a-z0-9]+", question.lower())) - self.stopwords
        relevant = [item for item in safe if question_terms & set(re.findall(r"[a-z0-9]+", item.text.lower()))]
        if not relevant:
            return ProviderAnswer("I couldn't find enough evidence in your documents to answer that.", False, 0)
        excerpts = [item.text.strip().replace("\n", " ")[:500] for item in relevant[:3]]
        answer = "Based on your documents: " + " ".join(excerpts)
        return ProviderAnswer(answer, True, len(answer.split()), tuple(item.chunk_id for item in relevant[:3]))
