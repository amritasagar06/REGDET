"""LLM providers. 'openai' makes real calls; 'mock' is a free fake for learning/CI.

Both expose the same method, so the rest of the code never cares which is used.
"""
import asyncio
import hashlib
import json
import os
import re
import time
from dataclasses import dataclass

from .models import CATEGORIES


@dataclass
class LLMResponse:
    text: str
    tokens: int


def parse_json(text: str) -> dict:
    """Parse model output as JSON, tolerating ```json fences and extra text around the object."""
    t = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", t, re.S)
        if m:
            return json.loads(m.group(0))
        raise


class OpenAIProvider:
    """Talks to OpenAI OR any OpenAI-compatible service (Groq, Gemini, OpenRouter...) via OPENAI_BASE_URL."""
    name = "openai"

    def __init__(self):
        if not os.getenv("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY is not set. Put it in .env or use --provider mock.")
        from openai import AsyncOpenAI
        base = os.getenv("OPENAI_BASE_URL") or None  # empty = official OpenAI
        self.client = AsyncOpenAI(base_url=base, max_retries=0)  # we do our own retrying below
        self.json_mode = True  # switched off automatically if the service rejects it
        self.rpm = float(os.getenv("REQUESTS_PER_MINUTE") or 0)  # 0 = no throttling
        self._lock = asyncio.Lock()
        self._next = 0.0

    async def _throttle(self):
        """Free tiers allow only N requests per minute; space calls out so we never exceed that."""
        if self.rpm <= 0:
            return
        async with self._lock:
            wait = self._next - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._next = time.monotonic() + 60.0 / self.rpm

    async def chat(self, *, task, model, messages, temperature=0.0, mock_noise=0.0) -> LLMResponse:
        last = None
        for attempt in range(6):
            await self._throttle()
            kwargs = dict(model=model, messages=messages, temperature=temperature)
            used_json = self.json_mode  # remember what THIS request used (other requests may flip the flag)
            if used_json:
                kwargs["response_format"] = {"type": "json_object"}  # asks for valid JSON
            try:
                r = await self.client.chat.completions.create(**kwargs)
                text = r.choices[0].message.content or ""
                return LLMResponse(text, r.usage.total_tokens if r.usage else 0)
            except Exception as e:  # noqa: BLE001
                last = e
                status = getattr(e, "status_code", None)
                if status == 400 and used_json:  # service may not support JSON mode: retry without it
                    self.json_mode = False
                    continue
                if status in (400, 401, 403, 404):  # wrong key/model: retrying cannot help
                    raise
                await asyncio.sleep(min(2 * 2 ** attempt, 30))  # rate limit / network: back off and retry
        raise last


# ---- Mock provider: a keyword-based fake "LLM" -------------------------------------------
KEYWORDS = {
    "billing": ["charge", "invoice", "refund", "payment", "bill", "price", "receipt",
                "credit card", "subscription", "cost"],
    "technical": ["crash", "error", "bug", "slow", "load", "freez", "not working",
                  "doesn't work", "api", "spin"],
    "account": ["password", "username", "profile", "locked", "delete my account",
                "two-factor", "2fa", "email address", "login", "user"],
}


def _words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", s.lower()))


class MockProvider:
    name = "mock"

    async def chat(self, *, task, model, messages, temperature=0.0, mock_noise=0.0) -> LLMResponse:
        await asyncio.sleep(0.005)  # pretend network latency
        content = messages[-1]["content"]
        if task == "judge":
            d = json.loads(content)
            a, b = _words(d["ideal"]), _words(d["candidate"])
            jac = len(a & b) / len(a | b) if a | b else 0
            score = round(1 + 4 * min(1.0, 2 * jac))
            text = json.dumps({"score": score, "reason": "word overlap (mock)"})
        else:
            text = json.dumps(self._classify(content, mock_noise))
        return LLMResponse(text, len(content) // 4 + len(text) // 4)

    @staticmethod
    def _classify(email: str, noise: float) -> dict:
        low = email.lower()
        scores = {c: sum(k in low for k in kws) for c, kws in KEYWORDS.items()}
        best = max(scores, key=scores.get)
        cat = best if scores[best] > 0 else "general"
        # Simulate a degraded prompt: deterministically corrupt `noise` fraction of answers.
        h = int(hashlib.md5((str(noise) + email).encode()).hexdigest(), 16) % 1000
        if h < noise * 1000:
            cat = CATEGORIES[(CATEGORIES.index(cat) + 1) % len(CATEGORIES)]
        first = re.split(r"(?<=[.!?])\s+", email.strip())[0]
        return {"category": cat, "summary": " ".join(first.split()[:20])}


def get_provider(name: str):
    if name == "openai":
        return OpenAIProvider()
    if name == "mock":
        return MockProvider()
    raise ValueError(f"Unknown provider: {name}")