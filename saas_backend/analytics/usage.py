from __future__ import annotations

MODEL_PRICING_USD_PER_1K = {
    "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
    "gpt-4o": {"input": 0.0025, "output": 0.01},
    "gpt-4-turbo": {"input": 0.01, "output": 0.03},
    "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015},
}


def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pricing = MODEL_PRICING_USD_PER_1K.get(model, MODEL_PRICING_USD_PER_1K["gpt-4o-mini"])
    return round(
        (prompt_tokens / 1000) * pricing["input"] + (completion_tokens / 1000) * pricing["output"],
        6,
    )
