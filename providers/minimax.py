from __future__ import annotations

import base64
import copy
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import logger

from .base import BaseTTSProvider, register_provider
from ..utils import compute_cache_key, validate_audio_file, retry_with_backoff


@register_provider("minimax")
class MiniMaxTTS(BaseTTSProvider):
    provider_name = "minimax"
    supports_emotion = True
    supports_style_tags = True
    style_tag_format = "parentheses"

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = str(config.get("api_url", "https://api.minimaxi.com/v1/t2a_v2"))
        self.api_key = str(config.get("api_key", ""))
        self.model = str(config.get("model", "speech-2.8-turbo"))
        self.voice_id = str(config.get("voice_id", "male-qn-qingse"))
        self.speed = float(config.get("speed", 1.0) or 1.0)
        self.vol = float(config.get("vol", 1.0) or 1.0)
        self.pitch = int(config.get("pitch", 0) or 0)
        self.default_emotion = str(config.get("emotion", "neutral") or "neutral")
        self.fmt = str(config.get("format", "mp3"))
        self.sample_rate = int(config.get("sample_rate", 32000) or 32000)
        self.bitrate = int(config.get("bitrate", 128000) or 128000)
        self.channel = int(config.get("channel", 1) or 1)
        self.output_format = str(config.get("output_format", "hex") or "hex")
        self.language_boost = str(config.get("language_boost", "") or "")
        self.proxy = str(config.get("proxy", "") or "")
        self.voice_modify = config.get("voice_modify", {})
        self.timber_weights = config.get("timber_weights", {})
        self.pronunciation_dict = config.get("pronunciation_dict", {})
        self.subtitle_enable = bool(config.get("subtitle_enable", False))
        self.aigc_watermark = bool(config.get("aigc_watermark", False))
        self.max_retries = int(config.get("max_retries", 2) or 2)
        self.timeout = float(config.get("timeout", 30.0) or 30.0)

    def _build_payload(self, text: str, *, voice: str, speed: float, emotion: Optional[str] = None) -> Dict[str, Any]:
        eff_emotion = emotion or self.default_emotion
        payload = {
            "model": self.model,
            "text": text,
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": speed,
                "vol": self.vol,
                "pitch": self.pitch,
                "emotion": eff_emotion,
            },
            "audio_setting": {
                "sample_rate": self.sample_rate,
                "bitrate": self.bitrate,
                "format": self.fmt,
                "channel": self.channel,
            },
            "output_format": self.output_format,
            "subtitle_enable": self.subtitle_enable,
            "aigc_watermark": self.aigc_watermark,
        }
        if self.language_boost:
            payload["language_boost"] = self.language_boost
        if self.voice_modify:
            payload["voice_modify"] = copy.deepcopy(self.voice_modify)
        if self.timber_weights:
            payload["timber_weights"] = copy.deepcopy(self.timber_weights)
        if self.pronunciation_dict:
            payload["pronunciation_dict"] = copy.deepcopy(self.pronunciation_dict)
        return payload

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
        eff_voice = voice or self.voice_id
        eff_speed = speed if speed and speed > 0 else self.speed
        eff_emotion = emotion

        tts_text = self.apply_style_tags(text, style_tags)

        cache_key = compute_cache_key(tts_text, eff_voice, self.model, str(eff_speed), str(eff_emotion), self.fmt)
        out_path = out_dir / f"{cache_key}.{self.fmt}"
        if out_path.exists() and validate_audio_file(out_path):
            return out_path

        payload = self._build_payload(tts_text, voice=eff_voice, speed=eff_speed, emotion=eff_emotion)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async def _do_request():
            session = self._get_session()
            kwargs = {"json": payload, "headers": headers, "timeout": self.timeout}
            async with session.post(self.api_url, **kwargs) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    exc = Exception(f"MiniMax API error {resp.status}: {error_text[:500]}")
                    exc.status = resp.status
                    raise exc
                content_type = resp.headers.get("Content-Type", "")
                if "audio" in content_type or "octet-stream" in content_type:
                    data = await resp.read()
                    out_path.write_bytes(data)
                    if validate_audio_file(out_path):
                        return out_path
                    return None
                resp_json = await resp.json()
                return await self._handle_json_response(resp_json, out_path)

        try:
            result = await retry_with_backoff(_do_request, max_retries=self.max_retries, label="MiniMax")
            return result
        except Exception as e:
            logger.error(f"[TTS+] MiniMax 合成失败: {e}")
            return None

    async def _handle_json_response(self, resp_json: Dict[str, Any], out_path: Path) -> Optional[Path]:
        data = resp_json.get("data", resp_json)
        audio_hex = data.get("audio")
        if audio_hex and isinstance(audio_hex, str):
            try:
                audio_bytes = bytes.fromhex(audio_hex)
                out_path.write_bytes(audio_bytes)
                if validate_audio_file(out_path):
                    return out_path
            except ValueError:
                pass
            try:
                audio_bytes = base64.b64decode(audio_hex)
                out_path.write_bytes(audio_bytes)
                if validate_audio_file(out_path):
                    return out_path
            except Exception:
                pass

        audio_b64 = data.get("audio_data") or data.get("audio_base64")
        if audio_b64 and isinstance(audio_b64, str):
            try:
                audio_bytes = base64.b64decode(audio_b64)
                out_path.write_bytes(audio_bytes)
                if validate_audio_file(out_path):
                    return out_path
            except Exception:
                pass

        download_url = data.get("audio_url") or data.get("download_url")
        if download_url:
            try:
                session = self._get_session()
                async with session.get(download_url, timeout=self.timeout) as dl_resp:
                    if dl_resp.status == 200:
                        audio_bytes = await dl_resp.read()
                        out_path.write_bytes(audio_bytes)
                        if validate_audio_file(out_path):
                            return out_path
            except Exception as e:
                logger.debug(f"[TTS+] MiniMax 音频下载失败: {e}")

        logger.warning(f"[TTS+] MiniMax 无法从响应中提取音频数据")
        return None

    def get_default_voice(self) -> str:
        return self.voice_id

    def get_supported_styles(self) -> List[str]:
        from ..emotion import get_default_styles
        return get_default_styles("minimax")

    def get_style_prompt_hint(self) -> str:
        styles = self.get_supported_styles()
        if not styles:
            return ""
        return f"可用情绪: {', '.join(styles)}"
