from __future__ import annotations

import abc
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger


_PROVIDER_REGISTRY: Dict[str, type["BaseTTSProvider"]] = {}


def register_provider(name: str):
    def decorator(cls: type) -> type:
        if name in _PROVIDER_REGISTRY:
            logger.warning(f"[TTS+] 重复注册 provider: {name}")
        _PROVIDER_REGISTRY[name] = cls
        return cls
    return decorator


def get_provider_class(name: str) -> Optional[type["BaseTTSProvider"]]:
    return _PROVIDER_REGISTRY.get(name)


def list_provider_names() -> List[str]:
    return list(_PROVIDER_REGISTRY.keys())


class BaseTTSProvider(abc.ABC):
    provider_name: str = ""
    supports_emotion: bool = False
    supports_style_tags: bool = False
    style_tag_format: str = ""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._session = None

    @abc.abstractmethod
    async def synth(
        self,
        text: str,
        voice: str,
        out_dir: Path,
        *,
        speed: Optional[float] = None,
        emotion: Optional[str] = None,
        style_tags: Optional[List[str]] = None,
    ) -> Optional[Path]:
        ...

    @abc.abstractmethod
    def get_default_voice(self) -> str:
        ...

    @abc.abstractmethod
    def get_supported_styles(self) -> List[str]:
        ...

    @abc.abstractmethod
    def get_style_prompt_hint(self) -> str:
        ...

    def apply_style_tags(self, text: str, style_tags: Optional[List[str]]) -> str:
        if not style_tags or not self.supports_style_tags:
            return text
        if self.style_tag_format == "parentheses":
            prefix = "".join(f"({tag})" for tag in style_tags)
            return f"{prefix}{text}"
        if self.style_tag_format == "parentheses_merged":
            styles_str = " ".join(style_tags)
            return f"({styles_str}){text}"
        if self.style_tag_format == "angle_brackets":
            prefix = "".join(f"<|{tag}|>" for tag in style_tags)
            return f"{prefix}{text}"
        return text

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    def _get_session(self):
        import aiohttp
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
