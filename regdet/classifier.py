"""The LLM feature under test: email in -> {category, summary} out."""
import json

from .models import ClassifierOutput, PromptConfig
from .providers import parse_json


async def classify(provider, cfg: PromptConfig, email: str) -> tuple[ClassifierOutput, int]:
    # Build the chat: system prompt, then few-shot examples as fake past turns, then the real email.
    messages = [{"role": "system", "content": cfg.system_prompt}]
    for ex in cfg.few_shot:
        messages.append({"role": "user", "content": ex.email})
        messages.append({"role": "assistant",
                         "content": json.dumps({"category": ex.category, "summary": ex.summary})})
    messages.append({"role": "user", "content": email})

    resp = await provider.chat(task="classify", model=cfg.model, messages=messages,
                               temperature=cfg.temperature, mock_noise=cfg.mock_noise)
    data = parse_json(resp.text)
    data["category"] = str(data.get("category", "")).strip().lower()
    return ClassifierOutput(**data), resp.tokens  # raises if the output breaks the contract