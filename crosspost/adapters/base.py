from __future__ import annotations

import json
from dataclasses import replace
from importlib.resources import files
from pathlib import Path

from core.interfaces import Uploader
from core.models import VideoPost


class PlatformAdapter:
    """Rewrite a master VideoPost into a platform-specific variant via LLM.

    The LLM is given the master post, the platform's hard constraints
    (max title length, max tags, required extras), and a platform-style
    prompt. It returns a JSON object with rewritten fields. Unspecified
    fields fall back to the master.
    """

    def __init__(self, llm):
        self.llm = llm
        self._prompt_cache: dict[str, str] = {}

    async def adapt(self, master: VideoPost, uploader: Uploader) -> VideoPost:
        platform = uploader.platform
        prompt = self._load_prompt(platform)
        constraints = {
            "max_title_len": uploader.max_title_len,
            "max_desc_len": uploader.max_desc_len,
            "max_tags": uploader.max_tags,
        }
        rewritten = await self.llm.rewrite(
            system_prompt=prompt,
            master=master,
            constraints=constraints,
        )
        # Merge: anything the LLM omitted stays from master
        return replace(
            master,
            title=rewritten.get("title", master.title)[: uploader.max_title_len],
            description=rewritten.get("description", master.description)[
                : uploader.max_desc_len
            ],
            tags=(rewritten.get("tags") or master.tags)[: uploader.max_tags],
        )

    def _load_prompt(self, platform: str) -> str:
        if platform in self._prompt_cache:
            return self._prompt_cache[platform]
        path = Path(__file__).parent / "prompts" / f"{platform}.md"
        if not path.exists():
            raise FileNotFoundError(
                f"No prompt template for platform {platform!r} at {path}"
            )
        text = path.read_text(encoding="utf-8")
        self._prompt_cache[platform] = text
        return text


class NullAdapter:
    """Pass-through adapter for testing or when AI rewriting is disabled."""

    async def adapt(self, master: VideoPost, uploader: Uploader) -> VideoPost:
        return master
