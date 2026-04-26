from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from .base import BaseTTSProvider, register_provider
from ..utils import compute_cache_key, validate_audio_file, retry_with_backoff, get_audio_mime


@register_provider("mimo")
class MimoTTS(BaseTTSProvider):
    provider_name = "mimo"
    supports_emotion = True
    supports_style_tags = True
    style_tag_format = "parentheses_merged"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = str(config.get("api_url", "https://api.xiaomimimo.com/v1")).rstrip("/")
        self.api_key = str(config.get("api_key", ""))
        self.model = str(config.get("model", "mimo-v2.5-tts-voiceclone"))
        self.fmt = str(config.get("format", "wav"))
        self.max_retries = int(config.get("max_retries", 2) or 2)
        self.timeout = float(config.get("timeout", 30.0) or 30.0)
        self._voice_sample_b64: Optional[str] = None
        self._voice_sample_mime: Optional[str] = None

    def set_voice_sample(self, b64_data: str, mime_type: str = "audio/mpeg"):
        self._voice_sample_b64 = b64_data
        self._voice_sample_mime = mime_type

    def _build_messages(self, text: str, style_tags: Optional[List[str]] = None) -> List[Dict[str, str]]:
        assistant_content = text
        if style_tags:
            assistant_content = self.apply_style_tags(text, style_tags)
        return [
            {"role": "user", "content": ""},
            {"role": "assistant", "content": assistant_content},
        ]

    def _build_audio_config(self) -> Dict[str, Any]:
        audio_cfg: Dict[str, Any] = {
            "format": self.fmt,
        }
        if self._voice_sample_b64:
            voice_value = f"data:{self._voice_sample_mime};base64,{self._voice_sample_b64}"
            audio_cfg["voice"] = voice_value
        return audio_cfg

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
        tts_text = text

        cache_key = compute_cache_key(tts_text, self.model, self.fmt, str(style_tags))
        out_path = out_dir / f"{cache_key}.{self.fmt}"
        if out_path.exists() and validate_audio_file(out_path):
            return out_path

        messages = self._build_messages(tts_text, style_tags)
        audio_cfg = self._build_audio_config()

        payload = {
            "model": self.model,
            "messages": messages,
            "audio": audio_cfg,
        }

        url = f"{self.api_url}/chat/completions"
        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        async def _do_request():
            session = self._get_session()
            async with session.post(url, json=payload, headers=headers, timeout=self.timeout) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    exc = Exception(f"Mimo API error {resp.status}: {error_text[:500]}")
                    exc.status = resp.status
                    raise exc
                resp_json = await resp.json()
                return self._handle_response(resp_json, out_path)

        try:
            result = await retry_with_backoff(_do_request, max_retries=self.max_retries, label="Mimo")
            return result
        except Exception as e:
            logger.error(f"[TTS+] Mimo 合成失败: {e}")
            return None

    def _handle_response(self, resp_json: Dict[str, Any], out_path: Path) -> Optional[Path]:
        choices = resp_json.get("choices", [])
        if not choices:
            logger.warning(f"[TTS+] Mimo 响应无 choices")
            return None

        message = choices[0].get("message", {})
        audio_data = message.get("audio", {})
        audio_b64 = audio_data.get("data") if isinstance(audio_data, dict) else None

        if not audio_b64:
            logger.warning(f"[TTS+] Mimo 响应无音频数据")
            return None

        try:
            audio_bytes = base64.b64decode(audio_b64)
            out_path.write_bytes(audio_bytes)
            if validate_audio_file(out_path):
                logger.info(f"[TTS+] Mimo 合成成功: {out_path.name} ({len(audio_bytes)} bytes)")
                return out_path
            logger.warning(f"[TTS+] Mimo 音频验证失败: {out_path.name}")
            return None
        except Exception as e:
            logger.error(f"[TTS+] Mimo 音频解码失败: {e}")
            return None

    def get_default_voice(self) -> str:
        return "voiceclone"

    def get_supported_styles(self) -> List[str]:
        from ..emotion import get_default_styles
        return get_default_styles("mimo")

    def get_style_prompt_hint(self) -> str:
        styles = self.get_supported_styles()
        if not styles:
            return ""
        return f"可用风格标签: {', '.join(f'({s})' for s in styles[:15])}"
