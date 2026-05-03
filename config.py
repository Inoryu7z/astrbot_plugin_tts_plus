from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import AstrBotConfig, logger


class ConfigManager:
    def __init__(self, config: AstrBotConfig, plugin_dir: Path):
        self._config = config
        self._plugin_dir = plugin_dir
        self._audio_cache: Dict[str, str] = {}

    def _cfg(self, key: str, default=None):
        return self._config.get(key, default)

    def is_inject_style_prompt(self) -> bool:
        return bool(self._cfg("inject_style_prompt", True))

    def get_provider_configs(self) -> Dict[str, Dict[str, Any]]:
        providers = self._cfg("providers", [])
        if not isinstance(providers, list):
            return {}
        result = {}
        for p in providers:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("id", "")).strip()
            if not pid:
                continue
            result[pid] = p
        return result

    def get_provider_config(self, provider_id: str) -> Optional[Dict[str, Any]]:
        return self.get_provider_configs().get(provider_id)

    def get_persona_configs(self) -> Dict[str, Dict[str, Any]]:
        personas = self._cfg("personas", [])
        if not isinstance(personas, list):
            return {}
        result = {}
        for p in personas:
            if not isinstance(p, dict):
                continue
            pid = str(p.get("select_persona", "") or p.get("persona_id", "")).strip()
            if not pid:
                continue
            result[pid] = p
        return result

    def get_persona_config(self, persona_id: str) -> Optional[Dict[str, Any]]:
        return self.get_persona_configs().get(persona_id)

    def get_default_persona_id(self) -> str:
        return str(self._cfg("default_persona", "default") or "default").strip()

    def get_persona_for_umo(self, umo: str) -> Optional[Dict[str, Any]]:
        mapping = self._cfg("umo_persona_map", {})
        if isinstance(mapping, dict):
            pid = mapping.get(umo)
            if pid:
                persona = self.get_persona_config(str(pid))
                if persona:
                    return persona
        default_id = self.get_default_persona_id()
        return self.get_persona_config(default_id)

    def get_persona_prob(self, umo: str) -> float:
        persona = self.get_persona_for_umo(umo)
        if persona:
            try:
                return float(persona.get("prob", 1.0) or 1.0)
            except Exception:
                pass
        return 1.0

    def get_persona_text_voice_output(self, umo: str) -> Optional[bool]:
        persona = self.get_persona_for_umo(umo)
        if persona:
            val = persona.get("text_voice_output")
            if val is True or str(val).strip().lower() == "true":
                return True
            if val is False or str(val).strip().lower() == "false":
                return False
        return None

    def is_tts_enabled(self) -> bool:
        return bool(self._cfg("tts_enabled", True))

    def is_text_voice_output(self) -> bool:
        return bool(self._cfg("text_voice_output", True))

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
        if provider_id in self._audio_cache:
            return self._audio_cache[provider_id]
        voice_sample = None
        provider_cfg = self.get_provider_config(provider_id)
        if provider_cfg:
            voice_sample = provider_cfg.get("voice_sample")
            if not voice_sample and provider_cfg.get("provider_type") == "mimo":
                voice_sample = self._config.get("mimo_voice_sample")
        else:
            voice_sample = self._config.get("mimo_voice_sample")
        if not voice_sample:
            return None
        if isinstance(voice_sample, list):
            voice_sample = voice_sample[0] if voice_sample else None
        if not voice_sample:
            return None
        from .utils import load_audio_as_base64
        path = Path(voice_sample)
        if not path.is_absolute():
            voice_sample_str = str(voice_sample).replace("\\", "/")
            if voice_sample_str.startswith("files/"):
                plugin_data_dir = self._plugin_dir.parent.parent / "plugin_data" / self._plugin_dir.name
                path = plugin_data_dir / voice_sample
            else:
                path = self._plugin_dir / voice_sample
        b64 = load_audio_as_base64(path)
        if b64:
            self._audio_cache[provider_id] = b64
        return b64

    def clear_audio_cache(self, provider_id: Optional[str] = None):
        if provider_id:
            self._audio_cache.pop(provider_id, None)
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
