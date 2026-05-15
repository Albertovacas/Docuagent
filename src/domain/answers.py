from dataclasses import dataclass

from src.domain.retrieval import Evidence


@dataclass
class Answer:
    content: str
    evidence: list[Evidence]
    model: str
