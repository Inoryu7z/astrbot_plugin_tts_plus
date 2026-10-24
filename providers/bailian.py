from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from astrbot.api import logger

from .base import BaseTTSProvider, register_provider
from ..utils import compute_cache_key, validate_audio_file, retry_with_backoff


@register_provider("bailian")
class BailianTTS(BaseTTSProvider):
    """阿里云百炼 CosyVoice 非实时语音合成。

    音色由用户在百炼控制台「声音复刻」里自行创建，插件只负责拿 voice_id 合成。
    复刻音色与创建时指定的 target_model 绑定，所以 model 必须与建音色时的目标模型一致，
    否则服务端直接拒绝（这不是插件能兜底的，配置填错就报错）。

    CosyVoice 没有 Qwen-Audio-TTS 那套 [excited] / (叹气) 文本标签，
    情感、方言只能通过 input.instruction 的自然语言指令控制，因此本 provider 不参与风格标签体系。
    """

    provider_name = "bailian"
    supports_emotion = False
    supports_style_tags = False
    style_tag_format = ""

    DEFAULT_API_URL = "https://dashscope.aliyuncs.com"
    SYNTH_PATH = "/api/v1/services/audio/tts/SpeechSynthesizer"
    # 官方给的音频链接 24 小时有效，留 5 分钟余量再判过期
    _URL_TTL_SECONDS = 24 * 3600 - 300

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.api_url = str(config.get("api_url") or self.DEFAULT_API_URL).rstrip("/")
        self.api_key = str(config.get("api_key", "") or "").strip()
        self.model = str(config.get("model") or "cosyvoice-v3.5-plus").strip()
        self.voice = str(config.get("voice", "") or "").strip()
        self.fmt = str(config.get("format") or "mp3").strip()
        self.sample_rate = int(config.get("sample_rate", 24000) or 24000)
        volume = config.get("volume")
        self.volume = int(50 if volume is None or volume == "" else volume)
        self.rate = float(config.get("rate", 1.0) or 1.0)
        self.pitch = float(config.get("pitch", 1.0) or 1.0)
        self.instruction = str(config.get("instruction", "") or "").strip()
        self.language_hints = str(config.get("language_hints", "") or "").strip()
        self.max_retries = int(config.get("max_retries", 2) or 2)
        # 非实时合成是整段文本一次请求，30s 对长文本偏紧，这里单独给 60s 起
        self.timeout = float(config.get("timeout", 60.0) or 60.0)
        # 429 默认不重试：重试只会把同一窗口内的请求数放大，与 mimo 侧的处理保持一致
        self.retry_on_429 = bool(config.get("retry_on_429", False))
        # cache_key -> (audio_url, 拿到 url 的时间)。下载失败时靠它复用已计费的合成结果
        self._url_cache: Dict[str, Tuple[str, float]] = {}

    def _retryable_status(self) -> set:
        retryable = {500, 502, 503, 504}
        if self.retry_on_429:
            retryable.add(429)
        return retryable

    def _build_input(
        self, text: str, eff_voice: str, eff_rate: float, eff_volume: int, eff_pitch: float
    ) -> Dict[str, Any]:
        payload_input: Dict[str, Any] = {
            "text": text,
            "voice": eff_voice,
            "format": self.fmt,
            "sample_rate": self.sample_rate,
            "volume": eff_volume,
            "rate": eff_rate,
            "pitch": eff_pitch,
        }
        if self.instruction:
            payload_input["instruction"] = self.instruction
        if self.language_hints:
            payload_input["language_hints"] = [self.language_hints]
        return payload_input

    @staticmethod
    def _clamp_rate(value: float) -> float:
        return max(0.5, min(2.0, float(value)))

    @staticmethod
    def _parse_audio_url(raw: str) -> Optional[str]:
        try:
            data = json.loads(raw)
        except Exception:
            return None
        if not isinstance(data, dict):
            return None
        audio = (data.get("output") or {}).get("audio") or {}
        url = audio.get("url")
        return str(url).strip() if url else None

    @staticmethod
    def _describe_failure(raw: str) -> str:
        """把响应体压成一句可读的失败原因，优先取 DashScope 的 code/message。"""
        try:
            data = json.loads(raw)
        except Exception:
            return raw[:500]
        if isinstance(data, dict) and data.get("code"):
            return f"{data.get('code')}: {data.get('message')}"
        return raw[:500]

    def _remembered_url(self, cache_key: str) -> Optional[str]:
        entry = self._url_cache.get(cache_key)
        if not entry:
            return None
        audio_url, ts = entry
        if time.time() - ts > self._URL_TTL_SECONDS:
            self._url_cache.pop(cache_key, None)
            return None
        return audio_url

    async def _download_to(self, audio_url: str, out_path: Path) -> Optional[Path]:
        async def _do_download() -> bytes:
            session = self._get_session()
            async with session.get(audio_url, timeout=self.timeout) as dl_resp:
                if dl_resp.status != 200:
                    exc = Exception(f"Bailian 音频下载失败 {dl_resp.status}: {audio_url[:120]}")
                    exc.status = dl_resp.status
                    raise exc
                return await dl_resp.read()

        try:
            audio_bytes = await retry_with_backoff(
                _do_download,
                max_retries=self.max_retries,
                label="Bailian 下载",
                retryable_status=self._retryable_status(),
            )
        except Exception as e:
            logger.error(f"[TTS+] 百炼音频下载失败: {e}")
            return None

        out_path.write_bytes(audio_bytes)
        if validate_audio_file(out_path):
            logger.info(
                f"[TTS+] 百炼合成成功: {out_path.name} "
                f"({len(audio_bytes)} bytes, model={self.model})"
            )
            return out_path

        logger.warning(f"[TTS+] 百炼音频验证失败: {out_path.name}")
        try:
            out_path.unlink()
        except Exception:
            pass
        return None

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
        eff_voice = (voice or self.voice).strip()
        eff_rate = self._clamp_rate(speed if speed and speed > 0 else self.rate)
        eff_volume = max(0, min(100, self.volume))
        eff_pitch = max(0.5, min(2.0, self.pitch))

        if not self.api_key:
            logger.warning(f"[TTS+] 百炼未配置 API Key，跳过合成（provider={self.model}）")
            return None
        if not eff_voice:
            logger.warning(
                "[TTS+] 百炼未配置音色 ID，跳过合成。"
                "请先在百炼控制台「声音复刻」创建音色，把 voice_id 填到 provider 配置的 voice 字段"
            )
            return None

        # 缓存键必须用「实际下发」的值，否则钳制前后的配置会算出不同的键、拿到同一段音频
        cache_key = compute_cache_key(
            text,
            eff_voice,
            self.model,
            self.fmt,
            str(self.sample_rate),
            str(eff_rate),
            str(eff_pitch),
            str(eff_volume),
            self.instruction,
            self.language_hints,
        )
        out_path = out_dir / f"{cache_key}.{self.fmt}"
        if out_path.exists() and validate_audio_file(out_path):
            return out_path

        # 上次合成成功但下载失败时，直接复用那个还活着的 url，避免重复计费的合成请求
        remembered = self._remembered_url(cache_key)
        if remembered:
            logger.info("[TTS+] 复用上次已合成的音频链接，不重复请求合成接口")
            downloaded = await self._download_to(remembered, out_path)
            if downloaded:
                return downloaded
            self._url_cache.pop(cache_key, None)

        payload_input = self._build_input(text, eff_voice, eff_rate, eff_volume, eff_pitch)
        url = f"{self.api_url}{self.SYNTH_PATH}"
        payload = {"model": self.model, "input": payload_input}
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async def _do_synth() -> str:
            """只负责拿音频 URL，下载另算，避免下载抖动时重发计费的合成请求。"""
            session = self._get_session()
            async with session.post(url, json=payload, headers=headers, timeout=self.timeout) as resp:
                body = await resp.text()
                if resp.status != 200:
                    exc = Exception(f"Bailian API error {resp.status}: {body[:500]}")
                    exc.status = resp.status
                    raise exc

            audio_url = self._parse_audio_url(body)
            if not audio_url:
                # 响应结构不对，重试也只会拿到同样的东西，直接失败
                exc = Exception(f"Bailian 响应未返回音频: {self._describe_failure(body)}")
                exc.status = -1
                raise exc
            return audio_url

        try:
            audio_url = await retry_with_backoff(
                _do_synth,
                max_retries=self.max_retries,
                label="Bailian",
                retryable_status=self._retryable_status(),
            )
        except Exception as e:
            logger.error(f"[TTS+] 百炼合成失败: {e}")
            return None

        downloaded = await self._download_to(audio_url, out_path)
        if downloaded:
            self._url_cache.pop(cache_key, None)
            return downloaded

        self._url_cache[cache_key] = (audio_url, time.time())
        return None

    def get_default_voice(self) -> str:
        return self.voice

    def get_supported_styles(self) -> List[str]:
        return []

    def get_style_prompt_hint(self) -> str:
        return ""
