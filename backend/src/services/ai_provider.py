"""Replaceable, deterministic AI provider boundaries."""

import base64
import hashlib
import re
import unicodedata
from dataclasses import dataclass

from src.services.ai_governance import (
    DataClassification,
    normalize_classification,
)


@dataclass(frozen=True)
class Evidence:
    chunk_id: str
    text: str
    source_label: str
    page_number: int | None
    chunk_index: int
    classification: DataClassification | str = DataClassification.PRIVATE

    def __post_init__(self) -> None:
        object.__setattr__(self, "classification", normalize_classification(self.classification))


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

    injection_patterns = (
        r"ignore\s+(?:all\s+)?(?:previous| prior| earlier)\s+instructions?",
        r"(?:system|developer)\s*(?:message|prompt|instruction)",
        r"(?:reveal|show| disclose)\s+(?:the\s+)?(?:secret|api\s*key|password|token)",
        r"(?:change|switch|use)\s+(?:the\s+)?(?:provider|model)",
        r"follow\s+these\s+instructions",
        r"you\s+are\s+now\s+(?:the\s+)?(?:system|developer)",
    )
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "does",
        "explain",
        "is",
        "of",
        "the",
        "that",
        "to",
        "what",
        "which",
    }

    @classmethod
    def normalize_untrusted_text(cls, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text)
        normalized = re.sub(r"[\u200b-\u200f\u2060\ufeff]", "", normalized)
        return re.sub(r"\s+", " ", normalized).strip().lower()

    @classmethod
    def contains_prompt_injection(cls, text: str) -> bool:
        candidates = [cls.normalize_untrusted_text(text)]
        compact = re.sub(r"[^a-z0-9]", "", candidates[0])
        candidates.append(compact)
        try:
            decoded = base64.b64decode(re.sub(r"\s+", "", text), validate=True).decode(
                "utf-8", errors="ignore"
            )
        except (ValueError, UnicodeDecodeError):
            decoded = ""
        if decoded:
            candidates.append(cls.normalize_untrusted_text(decoded))
        return any(
            re.search(pattern, candidate, flags=re.IGNORECASE)
            for candidate in candidates
            for pattern in cls.injection_patterns
        )

    @classmethod
    def safe_evidence(cls, evidence: list[Evidence]) -> list[Evidence]:
        return [item for item in evidence if not cls.contains_prompt_injection(item.text)]

    def answer(self, question: str, evidence: list[Evidence]) -> ProviderAnswer:
        if not evidence:
            return ProviderAnswer(
                "I couldn't find enough evidence in your documents to answer that.", False, 0
            )
        safe = self.safe_evidence(evidence)
        if not safe:
            return ProviderAnswer(
                "I couldn't use the retrieved content safely to answer that.", False, 0
            )
        question_terms = set(re.findall(r"[a-z0-9]+", question.lower())) - self.stopwords
        relevant = [
            item
            for item in safe
            if question_terms & set(re.findall(r"[a-z0-9]+", item.text.lower()))
        ]
        if not relevant:
            return ProviderAnswer(
                "I couldn't find enough evidence in your documents to answer that.", False, 0
            )
        excerpts = [item.text.strip().replace("\n", " ")[:500] for item in relevant[:3]]
        answer = "Based on your documents: " + " ".join(excerpts)
        return ProviderAnswer(
            answer, True, len(answer.split()), tuple(item.chunk_id for item in relevant[:3])
        )
