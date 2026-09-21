from __future__ import annotations

import time
from typing import Dict, Optional

from astrbot.api import logger

DEFAULT_PENALTY_SECONDS = 60.0
_MAX_PENALTY_SECONDS = 600.0


class KeyedCircuitBreaker:
    """按账号(API Key)聚合的熔断。只做一件事：收到 429 后暂停一段时间。

    这里刻意不做任何本地频率预算（"每分钟最多 N 次"、最小请求间隔之类）。
    原因：配额是账号维度的，插件身处单个进程，无从得知同一账号下其他 Bot、其他进程
    此刻已经用了多少。任何本地写死的数字都是在没有依据的情况下替服务端做决定 ——
    配额还剩一大截时，它会静默掐掉本来能成功的语音（用户只看到"偶尔没声音"，
    比 429 更难排查）；而它想避免的过量，服务端其实已经通过 429 明确告知了。

    所以策略是响应式退让：不预测，只在服务端真的拒绝后让路，并尊重 Retry-After。
    """

    def __init__(self) -> None:
        self._until: Dict[str, float] = {}

    def trip(self, key: str, seconds: float) -> None:
        seconds = min(max(float(seconds), 0.0), _MAX_PENALTY_SECONDS)
        if seconds <= 0:
            return
        until = time.monotonic() + seconds
        if self._until.get(key, 0.0) < until:
            self._until[key] = until
            logger.warning(
                f"[TTS+] 收到服务端限流，{seconds:.0f}s 内不再向该账号发起语音合成请求"
            )

    def is_open(self, key: str) -> bool:
        return time.monotonic() < self._until.get(key, 0.0)

    def remaining(self, key: str) -> float:
        return max(self._until.get(key, 0.0) - time.monotonic(), 0.0)


_breaker: Optional[KeyedCircuitBreaker] = None


def get_breaker() -> KeyedCircuitBreaker:
    global _breaker
    if _breaker is None:
        _breaker = KeyedCircuitBreaker()
    return _breaker
