from __future__ import annotations
from typing import List
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

_client: OpenAI | None = None

def client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI()
    return _client

def chat_completion(messages: List[ChatCompletionMessageParam], model: str = "gpt-4o-mini") -> str:
    resp = client().chat.completions.create(model=model, messages=messages)
    # defensive return
    return (resp.choices[0].message.content or "") if resp.choices else ""
