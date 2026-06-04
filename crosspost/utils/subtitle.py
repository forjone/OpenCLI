"""Subtitle file parsing — strip timestamps/metadata, return plain text.

Supports .srt, .vtt, .ass/.ssa, .lrc, .txt. Format is inferred from
filename extension; if unknown, falls back to a generic line-based strip.
"""
from __future__ import annotations

import re
from pathlib import Path

_SRT_INDEX = re.compile(r"^\d+$")
_TIMESTAMP = re.compile(r"\d{1,2}:\d{2}:\d{2}[.,]\d{3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[.,]\d{3}")
_ASS_TAG = re.compile(r"\{[^}]*\}")
_LRC_TS = re.compile(r"\[\d{1,2}:\d{2}(?:[.:]\d{1,3})?\]")
_BRACKETED_META = re.compile(r"^\[[^\]]+\]$")


def parse_subtitle(content: str, filename: str = "") -> str:
    """Return clean plain text from a subtitle file's raw contents."""
    ext = Path(filename).suffix.lower()
    if ext in {".ass", ".ssa"}:
        return _parse_ass(content)
    if ext == ".lrc":
        return _parse_lrc(content)
    # SRT/VTT (and generic) — strip indexes, timestamps, headers
    return _parse_srt_like(content)


def _parse_srt_like(content: str) -> str:
    out: list[str] = []
    for raw in content.splitlines():
        line = raw.strip().lstrip("﻿")
        if not line:
            continue
        if line.upper().startswith("WEBVTT"):
            continue
        if line.startswith("NOTE "):
            continue
        if _TIMESTAMP.search(line):
            continue
        if _SRT_INDEX.match(line):
            continue
        if _BRACKETED_META.match(line):
            continue
        out.append(line)
    return "\n".join(out)


def _parse_ass(content: str) -> str:
    out: list[str] = []
    for line in content.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        if len(parts) < 10:
            continue
        text = parts[9]
        text = _ASS_TAG.sub("", text)
        text = text.replace(r"\N", " ").replace(r"\n", " ")
        text = text.strip()
        if text:
            out.append(text)
    return "\n".join(out)


def _parse_lrc(content: str) -> str:
    out: list[str] = []
    for raw in content.splitlines():
        line = _LRC_TS.sub("", raw).strip()
        if line and not _BRACKETED_META.match(line):
            out.append(line)
    return "\n".join(out)
