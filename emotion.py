from __future__ import annotations

import re
from typing import Dict, List, Optional

from astrbot.api import logger


PAREN_STYLE_RE = re.compile(r"(\([^)]*[\u4e00-\u9fff\a-zA-Z_]+[^)]*\))")
ANGLE_STYLE_RE = re.compile(r"(<\|[A-Z_]+\|>)")
EMO_MARKER_RE = re.compile(r"\[EMO:\s*(\w+)\]")
MIMO_PAREN_RE = re.compile(r"(\([\u4e00-\u9fff\a-zA-Z_\s，、,]+\))")

INJECTION_HEADER = "<TTSPlus-Style>"
INJECTION_FOOTER = "</TTSPlus-Style>"
_INJECTION_PATTERN = re.compile(
    re.escape(INJECTION_HEADER) + r".*?" + re.escape(INJECTION_FOOTER),
    flags=re.DOTALL,
)

KNOWN_STYLES: set = {
    "HAPPY", "SAD", "ANGRY", "FEARFUL", "SURPRISED",
    "DISGUSTED", "NEUTRAL", "EXCITED", "SHY", "WHISPER", "GENTLE",
    "neutral", "happy", "sad", "angry", "fearful", "disgusted", "surprised",
    "开心", "悲伤", "愤怒", "恐惧", "惊讶", "兴奋",
    "委屈", "平静", "冷漠", "怅然", "欣慰", "无奈",
    "愧疚", "释然", "嫉妒", "厌倦", "忐忑", "动情",
    "温柔", "高冷", "活泼", "严肃", "慵懒", "俏皮",
    "深沉", "干练", "凌厉", "磁性", "清亮", "甜美",
    "沙哑", "东北话", "四川话", "粤语", "唱歌",
    "空灵", "稚嫩", "苍老", "醇厚", "悄悄话", "撒娇",
    "醇雅", "夹子音", "御姐音", "正太音", "大叔音", "台湾腔",
    "河南话", "孙悟空", "林黛玉",
    "吸气", "深呼吸", "叹气", "长叹一口气", "喘息", "屏息",
    "紧张", "害怕", "激动", "疲惫", "心虚", "震惊", "不耐烦",
    "颤抖", "声音颤抖", "气声", "鼻音", "变调", "破音",
    "笑", "轻笑", "大笑", "冷笑", "抽泣", "呜咽", "哽咽", "嚎啕大哭",
}

STYLE_INJECTION_TEMPLATE = (
    "你的回复会被语音播报。如需控制语气，在句首加风格标签："
    "{tag_example}接文本。大部分时候自然写就行，标签只在情绪突变时用。"
    "可用：{style_list}"
)


def remove_ttsplus_injection(system_prompt: Optional[str]) -> tuple[str, bool]:
    if not system_prompt:
        return system_prompt or "", False
    cleaned = _INJECTION_PATTERN.sub("", system_prompt)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, cleaned != system_prompt


def build_style_injection_prompt(
    provider_style_format: str,
    available_styles: List[str],
    custom_styles: Optional[List[str]] = None,
    custom_template: Optional[str] = None,
    audio_tags: Optional[List[str]] = None,
) -> str:
    all_styles = list(available_styles)
    if custom_styles:
        for s in custom_styles:
            if s and s not in all_styles:
                all_styles.append(s)

    if provider_style_format == "parentheses_merged":
        tag_example = f"({all_styles[0]})" if len(all_styles) == 1 else f"({all_styles[0]} {all_styles[1] if len(all_styles) > 1 else all_styles[0]})"
    elif provider_style_format == "parentheses":
        tag_example = f"({all_styles[0]})" if all_styles else ""
    elif provider_style_format == "angle_brackets":
        tag_example = f"<|{all_styles[0]}|>" if all_styles else ""
    else:
        return ""

    style_list_str = "、".join(all_styles[:20])

    audio_tags_str = ""
    if audio_tags:
        audio_tags_str = "、".join(audio_tags)

    template = custom_template or STYLE_INJECTION_TEMPLATE
    try:
        body = template.format(
            tag_example=tag_example,
            style_list=style_list_str,
            audio_tags=audio_tags_str,
        )
    except KeyError:
        body = template.format(
            tag_example=tag_example,
            style_list=style_list_str,
        )

    return f"{INJECTION_HEADER}\n{body}\n{INJECTION_FOOTER}"


def extract_style_tags_from_response(
    text: str,
    provider_style_format: str = "parentheses",
) -> tuple[str, List[str]]:
    tags: List[str] = []

    text, emo_tags = _extract_emo_markers(text)
    tags.extend(emo_tags)

    if provider_style_format == "parentheses_merged":
        text, paren_tags = _extract_mimo_styles(text)
        tags.extend(paren_tags)
    elif provider_style_format == "parentheses":
        text, paren_tags = _extract_paren_styles(text)
        tags.extend(paren_tags)
    elif provider_style_format == "angle_brackets":
        text, angle_tags = _extract_angle_styles(text)
        tags.extend(angle_tags)

    return text.strip(), tags


def _extract_paren_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        tag = m.group(1)[1:-1].strip()
        if tag in KNOWN_STYLES:
            tags.append(tag)
            return ""
        return m.group(1)
    cleaned = PAREN_STYLE_RE.sub(replacer, text)
    return cleaned, tags


def _extract_mimo_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        content = m.group(1)[1:-1].strip()
        parts = re.split(r"[\s，、,]+", content)
        extracted = [p.strip() for p in parts if p.strip()]
        if extracted:
            tags.extend(extracted)
            return ""
        return m.group(1)
    cleaned = MIMO_PAREN_RE.sub(replacer, text)
    return cleaned, tags


def _extract_angle_styles(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        raw = m.group(1)
        tag = raw.strip("<|>")
        tags.append(tag)
        return ""
    cleaned = ANGLE_STYLE_RE.sub(replacer, text)
    return cleaned, tags


def _extract_emo_markers(text: str) -> tuple[str, List[str]]:
    tags = []
    def replacer(m):
        tag = m.group(1).strip()
        tags.append(tag)
        return ""
    cleaned = EMO_MARKER_RE.sub(replacer, text)
    return cleaned, tags


def strip_all_markers(text: str) -> str:
    text = MIMO_PAREN_RE.sub("", text)
    text = PAREN_STYLE_RE.sub("", text)
    text = ANGLE_STYLE_RE.sub("", text)
    text = EMO_MARKER_RE.sub("", text)
    return text.strip()


DEFAULT_STYLE_MAPS: Dict[str, List[str]] = {
    "siliconflow": [
        "HAPPY", "SAD", "ANGRY", "FEARFUL", "SURPRISED",
        "DISGUSTED", "NEUTRAL", "EXCITED",
    ],
    "minimax": [
        "neutral", "happy", "sad", "angry", "fearful",
        "disgusted", "surprised",
    ],
    "mimo": [
        "开心", "悲伤", "愤怒", "恐惧", "惊讶", "兴奋",
        "委屈", "平静", "冷漠", "怅然", "欣慰", "无奈",
        "愧疚", "释然", "嫉妒", "厌倦", "忐忑", "动情",
        "温柔", "高冷", "活泼", "严肃", "慵懒", "俏皮",
        "深沉", "干练", "凌厉", "磁性", "清亮", "甜美",
        "沙哑", "空灵", "稚嫩", "苍老", "醇厚", "醇雅",
        "夹子音", "御姐音", "正太音", "大叔音", "台湾腔",
        "东北话", "四川话", "河南话", "粤语",
        "孙悟空", "林黛玉",
        "唱歌",
    ],
}


def get_default_styles(provider_name: str) -> List[str]:
    return list(DEFAULT_STYLE_MAPS.get(provider_name, []))
