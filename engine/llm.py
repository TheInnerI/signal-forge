"""LLM client for Signal Forge v2 — supports streaming and multi-model routing."""

import os
from typing import Generator, Optional

from openai import OpenAI

from .config import OPENROUTER_API_KEY, MODEL_DEFAULT, MODEL_FAST, MODEL_QUALITY


def get_client() -> OpenAI:
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )


def call_llm(
    system_prompt: str,
    user_input: str,
    model: str = MODEL_DEFAULT,
    temperature: float = 0.8,
    max_tokens: int = 4096,
) -> str:
    """Synchronous LLM call — returns full response."""
    client = get_client()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Error calling LLM: {e}]"


def stream_llm(
    system_prompt: str,
    user_input: str,
    model: str = MODEL_DEFAULT,
    temperature: float = 0.8,
    max_tokens: int = 4096,
) -> Generator[str, None, None]:
    """Streaming LLM call — yields tokens as they arrive."""
    client = get_client()
    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        yield f"[Error: {e}]"


def select_model(complexity: str = "default") -> str:
    """Route to the appropriate model based on task complexity."""
    if complexity == "fast":
        return MODEL_FAST
    elif complexity == "quality":
        return MODEL_QUALITY
    return MODEL_DEFAULT
