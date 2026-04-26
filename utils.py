from __future__ import annotations

import asyncio
import hashlib
import time
from pathlib import Path
from typing import Optional

from astrbot.api import logger

AUDIO_SIGNATURES = {
    b"RIFF": "wav",
    b"\xff\xfb": "mp3",
    b"\xff\xf3": "mp3",
    b"\xff\xf2": "mp3",
    b"ID3": "mp3",
    b"OggS": "ogg",
    b"fLaC": "flac",
}


def compute_cache_key(*parts: str) -> str:
    raw = "|".join(str(p) for p in parts if p is not None)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def validate_audio_file(path: Path, min_bytes: int = 100) -> bool:
    if not path.exists():
        return False
    size = path.stat().st_size
    if size < min_bytes:
        logger.warning(f"[TTS+] 音频文件过小: {path.name} ({size} bytes)")
        return False
    try:
        with open(path, "rb") as f:
            header = f.read(12)
        if not header:
            return False
        for sig, fmt in AUDIO_SIGNATURES.items():
            if header[: len(sig)] == sig:
                return True
        if header[:4] == b"RIFF" and header[8:12] == b"WAVE":
            return True
        logger.warning(f"[TTS+] 音频文件头无法识别: {path.name}, header={header[:8].hex()}")
        return False
    except Exception as e:
        logger.warning(f"[TTS+] 音频文件验证失败: {path.name}, error={e}")
        return False


async def retry_with_backoff(
    func,
    max_retries: int = 2,
    base_delay: float = 1.0,
    retryable_status: Optional[set] = None,
    label: str = "TTS",
):
    if retryable_status is None:
        retryable_status = {429, 500, 502, 503, 504}
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            return await func()
        except Exception as e:
            last_error = e
            status = getattr(e, "status", None)
            if status is not None and status not in retryable_status:
                raise
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(
                    f"[TTS+] {label} 请求失败 (attempt {attempt + 1}/{max_retries + 1}), "
                    f"{delay:.1f}s 后重试: {e}"
                )
                await asyncio.sleep(delay)
            else:
                raise
    raise last_error


_last_clean_time: float = 0.0
_CLEAN_INTERVAL_SECONDS: float = 300.0


def clean_temp_dir(temp_dir: Path, max_age_hours: int = 2):
    global _last_clean_time
    now = time.time()
    if now - _last_clean_time < _CLEAN_INTERVAL_SECONDS:
        return
    _last_clean_time = now
    if not temp_dir.exists():
        return
    cutoff = now - max_age_hours * 3600
    removed = 0
    for f in temp_dir.iterdir():
        if f.is_file() and f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"[TTS+] 清理了 {removed} 个过期临时音频文件")


def load_audio_as_base64(path: Path) -> Optional[str]:
    import base64
    if not path.exists():
        logger.warning(f"[TTS+] 音频样本文件不存在: {path}")
        return None
    try:
        data = path.read_bytes()
        if len(data) > 10 * 1024 * 1024:
            logger.warning(f"[TTS+] 音频样本文件过大: {path} ({len(data)} bytes)")
            return None
        return base64.b64encode(data).decode("utf-8")
    except Exception as e:
        logger.warning(f"[TTS+] 读取音频样本失败: {path}, error={e}")
        return None


def get_audio_mime(path: Path) -> str:
    suffix = path.suffix.lower()
    mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav", ".ogg": "audio/ogg", ".flac": "audio/flac"}
    return mime_map.get(suffix, "audio/mpeg")
