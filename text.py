from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional


PAREN_STYLE_RE = re.compile(r"(\([^)]*[\u4e00-\u9fff\a-zA-Z_]+[^)]*\))")
ANGLE_STYLE_RE = re.compile(r"(<\|[A-Z_]+\|>)")
MINIMAX_EXPR_RE = re.compile(r"\((?:laughs?|sighs?|gasps?|groans?|moans?|screams?|whispers?|shouts?|cries?|giggles?|chuckles?|sniffles?|coughs?|yawns?|humphs?|hmm|ah|oh|uh|um|wow|hey|ouch|oops|phew|shh|huh|eek|ooh|yay|boo|brr|grr|mm|mhm|nuh|huh|pff|psh|tsk|whew)\)", re.IGNORECASE)
MINIMAX_PAUSE_RE = re.compile(r"<#\d+#>")
EMO_MARKER_RE = re.compile(r"\[EMO:\s*\w+\]")
MIMO_PAREN_RE = re.compile(r"(\([\u4e00-\u9fff\a-zA-Z_\s，、,]+\))")

from .emotion import KNOWN_STYLES


@dataclass
class DualText:
    tts_text: str
    display_text: str
    style_tags: List[str]


def extract_paren_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        tag = m.group(1)[1:-1].strip()
        if tag in KNOWN_STYLES:
            tags.append(tag)
            return ""
        return m.group(1)
    cleaned = PAREN_STYLE_RE.sub(replacer, text)
    return cleaned.strip(), tags


def extract_mimo_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        content = m.group(1)[1:-1].strip()
        parts = re.split(r"[\s，、,]+", content)
        extracted = [p.strip() for p in parts if p.strip() and p.strip() in KNOWN_STYLES]
        if extracted:
            tags.extend(extracted)
            return ""
        return m.group(1)
    cleaned = MIMO_PAREN_RE.sub(replacer, text)
    return cleaned.strip(), tags


def extract_angle_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        raw = m.group(1)
        tag = raw.strip("<|>")
        tags.append(tag)
        return ""
    cleaned = ANGLE_STYLE_RE.sub(replacer, text)
    return cleaned.strip(), tags


def extract_emo_markers(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        raw = m.group(0)
        tag = raw.replace("[EMO:", "").replace("]", "").strip()
        tags.append(tag)
        return ""
    cleaned = EMO_MARKER_RE.sub(replacer, text)
    return cleaned.strip(), tags


def strip_all_style_tags(text: str) -> str:
    text = MIMO_PAREN_RE.sub("", text)
    text = PAREN_STYLE_RE.sub("", text)
    text = ANGLE_STYLE_RE.sub("", text)
    text = MINIMAX_EXPR_RE.sub("", text)
    text = MINIMAX_PAUSE_RE.sub("", text)
    text = EMO_MARKER_RE.sub("", text)
    return text.strip()


def build_dual_text(
    raw_text: str,
    provider_style_format: str = "parentheses",
    keep_minimax_expressions: bool = False,
    keep_minimax_pauses: bool = False,
) -> DualText:
    style_tags: List[str] = []
    text = raw_text

    text, emo_tags = extract_emo_markers(text)
    style_tags.extend(emo_tags)

    if provider_style_format == "parentheses_merged":
        text, paren_tags = extract_mimo_styles(text)
        style_tags.extend(paren_tags)
    elif provider_style_format == "parentheses":
        text, paren_tags = extract_paren_styles(text)
        style_tags.extend(paren_tags)
    elif provider_style_format == "angle_brackets":
        text, angle_tags = extract_angle_styles(text)
        style_tags.extend(angle_tags)

    display_text = strip_all_style_tags(raw_text)

    tts_text = text
    if keep_minimax_expressions:
        pass
    else:
        tts_text = MINIMAX_EXPR_RE.sub("", tts_text)

    if keep_minimax_pauses:
        pass
    else:
        tts_text = MINIMAX_PAUSE_RE.sub("", tts_text)

    tts_text = tts_text.strip()
    display_text = display_text.strip()

    return DualText(
        tts_text=tts_text or display_text,
        display_text=display_text or tts_text,
        style_tags=style_tags,
    )
