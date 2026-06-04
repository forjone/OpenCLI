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

    async def generate_master(self, topic: str, style_hint: str = "") -> dict[str, Any]:
        """Generate a master VideoPost shell from a one-line topic.

        Returns {title, description, tags} — the user then tweaks and the
        per-platform adapter rewrites again at publish time.
        """
        system = (
            "你是短视频文案策划。用户会给你一个主题，你需要为他生成一份"
            '"母版"文案（这份文案后续还会被各平台 adapter 改写成抖音/B站'
            "/小红书/视频号风格，所以这里你只需要写得通用、信息密度高、"
            "突出价值点即可）。\n\n"
            "返回严格 JSON：{\"title\": \"≤30字\", "
            "\"description\": \"≤200字，1-3 句话讲清视频内容和价值\", "
            "\"tags\": [\"≤6 个核心关键词，不要 # 号\"]}\n"
            "JSON 之外不要输出任何文字。"
        )
        user = f"主题：{topic}\n风格倾向：{style_hint or '通用'}"
        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=800,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text if resp.content else "{}"
        return _extract_json(text)

    async def generate_master_from_subtitle(
        self, subtitle_text: str, style_hint: str = ""
    ) -> dict[str, Any]:
        """Generate a master from the actual video content (subtitle / transcript).

        Far more accurate than `generate_master(topic)` because the model
        sees what's actually in the video.
        """
        MAX = 40_000  # ~13k tokens of Chinese — covers ~30 min of speech
        truncated = False
        if len(subtitle_text) > MAX:
            subtitle_text = subtitle_text[:MAX]
            truncated = True

        system = (
            "你是短视频文案策划。用户提供一条视频的完整字幕/逐字稿，"
            '你帮他提炼一份"母版"文案。后续各平台 adapter 会再按平台风格'
            "改写，所以这里你只需要写得通用、信息密度高、突出核心价值即可。\n\n"
            "返回严格 JSON：\n"
            '{"title": "≤30字，点出核心钩子或价值",\n'
            ' "description": "≤200字，2-4 句话总结视频在讲什么、观众能收获什么",\n'
            ' "tags": ["≤6 个核心关键词，不要 # 号"]}\n'
            "JSON 之外不要输出任何文字。"
        )
        user = "字幕：\n" + subtitle_text
        if truncated:
            user += "\n…（字幕过长已截断，请基于前 40000 字概括）"
        if style_hint:
            user += f"\n\n风格倾向：{style_hint}"

        resp = await self._client.messages.create(
            model=self.model,
            max_tokens=800,
            system=[
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user}],
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
