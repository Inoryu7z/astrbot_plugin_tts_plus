from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from .base import BaseTTSProvider, register_provider
from ..utils import compute_cache_key, validate_audio_file, retry_with_backoff


@register_provider("siliconflow")
class SiliconFlowTTS(BaseTTSProvider):
    provider_name = "siliconflow"
    supports_emotion = True
    supports_style_tags = True
    style_tag_format = "angle_brackets"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = str(config.get("api_url", "https://api.siliconflow.cn/v1")).rstrip("/")
        self.api_key = str(config.get("api_key", ""))
        self.model = str(config.get("model", "FunAudioLLM/CosyVoice2-0.5B"))
        self.voice = str(config.get("voice", "alex"))
        self.fmt = str(config.get("format", "mp3"))
        self.speed = float(config.get("speed", 1.0) or 1.0)
        self.gain = float(config.get("gain", 0.0) or 0.0)
        self.sample_rate = int(config.get("sample_rate", 44100) or 44100)
        self.max_retries = int(config.get("max_retries", 2) or 2)
        self.timeout = float(config.get("timeout", 30.0) or 30.0)

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
        eff_voice = voice or self.voice
        eff_speed = speed if speed and speed > 0 else self.speed

        tts_text = self.apply_style_tags(text, style_tags)

        cache_key = compute_cache_key(tts_text, eff_voice, self.model, str(eff_speed), self.fmt, str(self.gain), str(self.sample_rate))
        out_path = out_dir / f"{cache_key}.{self.fmt}"
        if out_path.exists() and validate_audio_file(out_path):
            return out_path

        url = f"{self.api_url}/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "voice": eff_voice,
            "input": tts_text,
            "response_format": self.fmt,
            "speed": eff_speed,
            "gain": self.gain,
        }
        if self.sample_rate:
            payload["sample_rate"] = int(self.sample_rate)

        async def _do_request():
            session = self._get_session()
            async with session.post(url, json=payload, headers=headers, timeout=self.timeout) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    exc = Exception(f"SiliconFlow API error {resp.status}: {error_text[:500]}")
                    exc.status = resp.status
                    raise exc
                content_type = resp.headers.get("Content-Type", "")
                if "audio" in content_type or "octet-stream" in content_type:
                    data = await resp.read()
                    out_path.write_bytes(data)
                    if validate_audio_file(out_path):
                        return out_path
                    logger.warning(f"[TTS+] SiliconFlow 音频验证失败: {out_path.name}")
                    return None
                else:
                    error_text = await resp.text()
                    raise Exception(f"SiliconFlow 返回非音频响应: {error_text[:500]}")

        try:
            result = await retry_with_backoff(_do_request, max_retries=self.max_retries, label="SiliconFlow")
            return result
        except Exception as e:
            logger.error(f"[TTS+] SiliconFlow 合成失败: {e}")
            return None

    def get_default_voice(self) -> str:
        return self.voice

    def get_supported_styles(self) -> List[str]:
        from ..emotion import get_default_styles
        return get_default_styles("siliconflow")

    def get_style_prompt_hint(self) -> str:
        styles = self.get_supported_styles()
        if not styles:
            return ""
        return f"可用情绪标签: {', '.join(f'<|{s}|>' for s in styles[:10])}"
