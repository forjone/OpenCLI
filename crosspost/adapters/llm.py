from __future__ import annotations

import json
import os
from typing import Any

from core.models import VideoPost


class ClaudeClient:
    """Thin wrapper around the Anthropic SDK for platform-style rewriting.

    Uses prompt caching on the system prompt so each platform's template
    is only billed once per session.
    """

    def __init__(self, model: str = "claude-sonnet-4-6", api_key: str | None = None):
        try:
            from anthropic import AsyncAnthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic SDK not installed. Run `pip install anthropic`."
            ) from exc
        self._client = AsyncAnthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model

    async def rewrite(
        self,
        system_prompt: str,
        master: VideoPost,
        constraints: dict[str, int],
    ) -> dict[str, Any]:
        user_msg = (
            '请基于以下"母版"按平台风格改写，并以严格 JSON 返回 {title, description, tags}。\n'
            f"约束: 标题≤{constraints['max_title_len']}字，"
            f"简介≤{constraints['max_desc_len']}字，"
            f"标签≤{constraints['max_tags']}个。\n\n"
            f"母版标题: {master.title}\n"
            f"母版简介: {master.description}\n"
            f"母版标签: {', '.join(master.tags)}\n"
        )
        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=2000,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text if resp.content else "{}"
        return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the first JSON object out of an LLM reply, tolerant of code fences."""
    text = text.strip()
    if text.startswith("```"):
        # strip ```json ... ``` wrappers
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
        if text.endswith("```"):
            text = text[:-3].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: find first { ... } pair
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        return {}
