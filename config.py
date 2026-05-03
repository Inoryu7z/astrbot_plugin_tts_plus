from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import AstrBotConfig, logger


PERSONA_SLOT_COUNT = 3


class ConfigManager:
    def __init__(self, config: AstrBotConfig, plugin_dir: Path):
        self._config = config
        self._plugin_dir = plugin_dir
        self._audio_cache: Dict[str, str] = {}

    def _cfg(self, key: str, default=None):
        return self._config.get(key, default)

    def get_provider_configs(self) -> Dict[str, Dict[str, Any]]:
        result = {}
        providers = self._cfg("providers", [])
        if isinstance(providers, list):
            for p in providers:
                if not isinstance(p, dict):
                    continue
                pid = str(p.get("id", "")).strip()
                if not pid:
                    continue
                result[pid] = p

        for idx in range(1, 4):
            key = f"mimotts_{idx}"
            cfg = self._cfg(key)
            if isinstance(cfg, dict):
                cfg = dict(cfg)
                cfg["provider_type"] = "mimo"
                pid = str(cfg.get("id", key)).strip() or key
                result[pid] = cfg

        return result

    def get_provider_config(self, provider_id: str) -> Optional[Dict[str, Any]]:
        return self.get_provider_configs().get(provider_id)

    def _get_persona_slot_config(self, index: int) -> Optional[Dict[str, Any]]:
        conf = self._cfg(f"persona_{index}")
        return conf if isinstance(conf, dict) else None

    def get_persona_config(self, persona_id: str) -> Optional[Dict[str, Any]]:
        for idx in range(1, PERSONA_SLOT_COUNT + 1):
            conf = self._get_persona_slot_config(idx)
            if not conf:
                continue
            slot_persona = str(conf.get("select_persona", "") or "").strip()
            if slot_persona == persona_id:
                return conf
        return None

    def get_persona_prob(self, persona_id: str) -> float:
        conf = self.get_persona_config(persona_id)
        if conf:
            try:
                return float(conf.get("prob", 1.0) or 1.0)
            except Exception:
                pass
        return 1.0

    def get_persona_text_voice_output(self, persona_id: str) -> Optional[bool]:
        conf = self.get_persona_config(persona_id)
        if conf:
            val = conf.get("text_voice_output")
            if val is True or str(val).strip().lower() == "true":
                return True
            if val is False or str(val).strip().lower() == "false":
                return False
        return None

    def get_persona_inject_prompt(self, persona_id: str) -> bool:
        conf = self.get_persona_config(persona_id)
        if conf:
            return bool(conf.get("inject_prompt", False))
        return False

    def get_timeout(self) -> float:
        try:
            return float(self._cfg("timeout", 30.0) or 30.0)
        except Exception:
            return 30.0

    def get_max_retries(self) -> int:
        try:
            return int(self._cfg("max_retries", 2) or 2)
        except Exception:
            return 2

    def get_cooldown(self) -> float:
        try:
            return float(self._cfg("cooldown", 0.0) or 0.0)
        except Exception:
            return 0.0

    def get_text_min_limit(self) -> int:
        try:
            return int(self._cfg("text_min_limit", 2) or 2)
        except Exception:
            return 2

    def get_text_limit(self) -> int:
        try:
            return int(self._cfg("text_limit", 500) or 500)
        except Exception:
            return 500

    def get_audio_sample_base64(self, provider_id: str) -> Optional[str]:
        cache_key = f"provider_{provider_id}"
        if cache_key in self._audio_cache:
            return self._audio_cache[cache_key]

        provider_cfg = self.get_provider_config(provider_id)
        if not provider_cfg:
            return None

        voice_sample = provider_cfg.get("voice_sample")
        if not voice_sample:
            return None
        if isinstance(voice_sample, list):
            voice_sample = voice_sample[0] if voice_sample else None
        if not voice_sample:
            return None

        from .utils import load_audio_as_base64

        path = Path(str(voice_sample).strip())
        if not path.is_absolute():
            voice_sample_str = str(voice_sample).replace("\\", "/")
            if voice_sample_str.startswith("files/"):
                plugin_data_dir = self._plugin_dir.parent.parent / "plugin_data" / self._plugin_dir.name
                path = plugin_data_dir / voice_sample
            else:
                path = self._plugin_dir.parent.parent / voice_sample

        b64 = load_audio_as_base64(path)
        if b64:
            self._audio_cache[cache_key] = b64
        return b64

    def clear_audio_cache(self, persona_id: Optional[str] = None):
        if persona_id:
            self._audio_cache.pop(f"persona_{persona_id}", None)
        else:
            self._audio_cache.clear()

    def get_pool_styles(self, provider_id: str) -> List[str]:
        provider_cfg = self.get_provider_config(provider_id)
        if not provider_cfg:
            return []
        pool = provider_cfg.get("pool", {})
        if not isinstance(pool, dict):
            pool = {}
        all_styles: List[str] = []
        for key, value in pool.items():
            if key == "custom_styles":
                continue
            if isinstance(value, list):
                all_styles.extend(str(s).strip() for s in value if str(s).strip())
        return all_styles

    def get_custom_styles(self, provider_id: str) -> List[str]:
        provider_cfg = self.get_provider_config(provider_id)
        if not provider_cfg:
            return []
        pool = provider_cfg.get("pool", {})
        if isinstance(pool, dict):
            styles = pool.get("custom_styles", [])
        else:
            styles = provider_cfg.get("custom_styles", [])
        if isinstance(styles, list):
            return [str(s).strip() for s in styles if str(s).strip()]
        return []

    def get_all_styles(self, provider_id: str) -> List[str]:
        pool_styles = self.get_pool_styles(provider_id)
        custom_styles = self.get_custom_styles(provider_id)
        seen = set()
        result = []
        for s in pool_styles + custom_styles:
            if s not in seen:
                seen.add(s)
                result.append(s)
        return result

    def get_prompt_template(self, provider_id: str) -> Optional[str]:
        provider_cfg = self.get_provider_config(provider_id)
        provider_type = ""
        if provider_cfg:
            provider_type = str(provider_cfg.get("provider_type", "") or "").strip()
        type_key_map = {
            "siliconflow": "siliconflow_prompt_template",
            "minimax": "minimax_prompt_template",
            "mimo": "mimo_prompt_template",
        }
        if provider_type in type_key_map:
            template = self._cfg(type_key_map[provider_type])
            if template and isinstance(template, str) and template.strip():
                return template.strip()
        return None

    def get_audio_tags(self) -> List[str]:
        tags = self._cfg("mimo_audio_tags")
        if isinstance(tags, list) and tags:
            return [str(t).strip() for t in tags if str(t).strip()]
        return []
