"""Typed data structures. Pydantic validates data so bad input fails loudly."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

CATEGORIES = ["billing", "technical", "account", "general"]
Category = Literal["billing", "technical", "account", "general"]


class FewShot(BaseModel):
    """One worked example shown to the LLM inside the prompt."""
    email: str
    category: Category
    summary: str


class PromptConfig(BaseModel):
    """A versioned prompt. This is the 'code' that CI tests."""
    version: str
    timestamp: str
    model: str = "gpt-4o-mini"
    temperature: float = 0.0
    system_prompt: str
    few_shot: list[FewShot] = Field(default_factory=list)
    mock_noise: float = 0.0  # ONLY used by the fake (mock) LLM to simulate a bad prompt


class ClassifierOutput(BaseModel):
    """The contract: what the LLM feature must return."""
    category: Category
    summary: str


class GoldenCase(BaseModel):
    """One human-verified test case."""
    id: str
    email: str
    expected_category: Category
    ideal_summary: str
    expected_difficulty: Literal["easy", "medium", "hard"] = "easy"
    notes: str = ""


class CaseResult(BaseModel):
    """What happened when one test case ran."""
    case_id: str
    expected_category: str
    predicted_category: Optional[str] = None
    predicted_summary: str = ""
    passed: bool = False
    judge_score: Optional[float] = None  # 1-5, from LLM-as-judge
    latency_ms: float = 0.0
    tokens: int = 0
    error: Optional[str] = None


class RunRecord(BaseModel):
    """A full eval run: metadata + every case result."""
    run_id: str
    prompt_version: str
    model: str
    provider: str
    dataset_version: str
    timestamp: str
    results: list[CaseResult]
    status: str = "pass"

    @property
    def pass_rate(self) -> float:
        return sum(r.passed for r in self.results) / len(self.results) if self.results else 0.0

    @property
    def avg_judge(self) -> float:
        s = [r.judge_score for r in self.results if r.judge_score is not None]
        return sum(s) / len(s) if s else 0.0

    @property
    def avg_latency_ms(self) -> float:
        return sum(r.latency_ms for r in self.results) / len(self.results) if self.results else 0.0

    @property
    def total_tokens(self) -> int:
        return sum(r.tokens for r in self.results)
