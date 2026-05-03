from __future__ import annotations

import asyncio
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.message_components import Plain, Record
from astrbot.api.provider import LLMResponse
from astrbot.api.star import Context, Star, register

from .config import ConfigManager
from .emotion import (
    build_style_injection_prompt,
    extract_style_tags_from_response,
    strip_all_markers,
    get_default_styles,
    remove_ttsplus_injection,
)
from .text import build_dual_text, strip_all_style_tags
from .providers.base import BaseTTSProvider, get_provider_class
from .providers.siliconflow import SiliconFlowTTS
from .providers.minimax import MiniMaxTTS
from .providers.mimo import MimoTTS
from .utils import clean_temp_dir, compute_cache_key


@register(
    "astrbot_plugin_tts_plus",
    "Inoryu7z",
    "多提供商 TTS 语音合成插件，支持硅基流动、MiniMax、小米 Mimo，多人格风格路由",
    "1.2.1",
)
class TTSPlusPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = ConfigManager(config, self._get_plugin_dir())
        self._providers: Dict[str, BaseTTSProvider] = {}
        self._cooldowns: Dict[str, float] = {}
        self._inflight: Dict[str, float] = {}
        self._current_style_tags: Dict[str, List[str]] = {}
        self._init_providers()

    def _get_plugin_dir(self) -> Path:
        return Path(__file__).parent

    def _init_providers(self):
        provider_configs = self.config.get_provider_configs()
        for pid, pcfg in provider_configs.items():
            provider_type = str(pcfg.get("provider_type", "") or "").strip()
            if not provider_type:
                api_url = str(pcfg.get("api_url", ""))
                if "siliconflow" in api_url:
                    provider_type = "siliconflow"
                elif "minimaxi" in api_url:
                    provider_type = "minimax"
                elif "xiaomimimo" in api_url:
                    provider_type = "mimo"

            cls = get_provider_class(provider_type)
            if cls is None:
                logger.warning(f"[TTS+] 未知的提供商类型: {provider_type} (id={pid})")
                continue

            try:
                provider = cls(pcfg)
                if provider_type == "mimo":
                    b64 = self.config.get_audio_sample_base64(pid)
                    if b64:
                        from .utils import get_audio_mime
                        voice_sample = pcfg.get("voice_sample")
                        mime = "audio/mpeg"
                        if voice_sample:
                            if isinstance(voice_sample, list):
                                voice_sample = voice_sample[0] if voice_sample else None
                            if voice_sample:
                                sample_path = Path(voice_sample)
                                mime = get_audio_mime(sample_path)
                        provider.set_voice_sample(b64, mime)
                        logger.info(f"[TTS+] Mimo 提供商 {pid} 已加载音色样本")
                    else:
                        logger.warning(f"[TTS+] Mimo 提供商 {pid} 未配置音色样本")

                self._providers[pid] = provider
                logger.info(f"[TTS+] 已加载提供商: {pid} ({provider_type})")
            except Exception as e:
                logger.error(f"[TTS+] 加载提供商 {pid} 失败: {e}")

    def _get_provider(self, provider_id: str) -> Optional[BaseTTSProvider]:
        return self._providers.get(provider_id)

    def _get_persona_provider(self, umo: str) -> Optional[tuple[BaseTTSProvider, Dict[str, Any]]]:
        persona = self.config.get_persona_for_umo(umo)
        if not persona:
            return None
        provider_id = str(persona.get("provider_id", "")).strip()
        if not provider_id:
            return None
        provider = self._get_provider(provider_id)
        if not provider:
            logger.warning(f"[TTS+] 人格 {persona.get('persona_id')} 引用的提供商 {provider_id} 不存在")
            return None
        return provider, persona

    def _get_style_injection_for_umo(self, umo: str) -> str:
        result = self._get_persona_provider(umo)
        if not result:
            return ""
        provider, persona = result
        provider_id = str(persona.get("provider_id", ""))
        all_styles = self.config.get_all_styles(provider_id)
        if not all_styles:
            all_styles = provider.get_supported_styles()
        custom_styles = self.config.get_custom_styles(provider_id)
        custom_template = self.config.get_prompt_template(provider_id)
        audio_tags = self.config.get_audio_tags() if provider.provider_name == "mimo" else None
        return build_style_injection_prompt(
            provider.style_tag_format,
            all_styles,
            custom_styles,
            custom_template,
            audio_tags,
        )

    @filter.on_llm_request()
    async def on_llm_request(self, event: AstrMessageEvent, llm_req):
        if not self.config.is_tts_enabled():
            return

        if not self.config.is_inject_style_prompt():
            try:
                if hasattr(llm_req, "system_prompt") and llm_req.system_prompt:
                    llm_req.system_prompt, _ = remove_ttsplus_injection(llm_req.system_prompt)
            except Exception:
                pass
            return

        umo = str(getattr(event, "unified_msg_origin", "") or "global")
        injection = self._get_style_injection_for_umo(umo)
        if not injection:
            return

        try:
            if not hasattr(llm_req, "system_prompt") or llm_req.system_prompt is None:
                llm_req.system_prompt = ""
            llm_req.system_prompt, _ = remove_ttsplus_injection(llm_req.system_prompt)
            llm_req.system_prompt = llm_req.system_prompt.rstrip() + "\n\n" + injection
        except Exception as e:
            logger.debug(f"[TTS+] 注入风格指令失败: {e}")

    @filter.on_llm_response()
    async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
        if not self.config.is_tts_enabled():
            return

        umo = str(getattr(event, "unified_msg_origin", "") or "global")
        result = self._get_persona_provider(umo)
        if not result:
            return

        provider, persona = result
        completion_text = getattr(resp, "completion_text", "") or ""
        if not completion_text:
            return

        cleaned_text, style_tags = extract_style_tags_from_response(
            completion_text, provider.style_tag_format
        )

        if style_tags:
            self._current_style_tags[umo] = style_tags
            if cleaned_text != completion_text:
                try:
                    resp.completion_text = cleaned_text
                except Exception:
                    pass
        else:
            self._current_style_tags.pop(umo, None)

    @filter.on_decorating_result(priority=-1000)
    async def on_decorating_result(self, event: AstrMessageEvent):
        if not self.config.is_tts_enabled():
            return

        try:
            if hasattr(event, "is_stopped") and event.is_stopped():
                return
        except Exception:
            pass

        result = event.get_result()
        if not result or not getattr(result, "chain", None):
            return

        umo = str(getattr(event, "unified_msg_origin", "") or "global")
        persona_result = self._get_persona_provider(umo)
        if not persona_result:
            return

        provider, persona = persona_result

        now = time.time()
        expired_keys = [k for k, v in self._inflight.items() if now - v > 180]
        for k in expired_keys:
            del self._inflight[k]

        temp_dir = self._get_plugin_dir() / "temp"
        clean_temp_dir(temp_dir)

        plain_text = ""
        for comp in result.chain:
            if isinstance(comp, Plain) and comp.text:
                plain_text += comp.text

        if not plain_text.strip():
            return

        text_len = len(plain_text.strip())
        min_limit = self.config.get_text_min_limit()
        if text_len < min_limit:
            return

        text_limit = self.config.get_text_limit()
        if text_limit > 0 and text_len > text_limit:
            return

        cooldown = self.config.get_cooldown()
        if cooldown > 0:
            last_time = self._cooldowns.get(umo, 0)
            if time.time() - last_time < cooldown:
                return
            expired_keys = [k for k, v in self._cooldowns.items() if time.time() - v > cooldown * 10]
            for k in expired_keys:
                del self._cooldowns[k]

        prob = self.config.get_persona_prob(umo)
        if prob < 1.0 and random.random() > prob:
            return

        inflight_key = compute_cache_key(umo, plain_text[:200])
        if inflight_key in self._inflight:
            return
        self._inflight[inflight_key] = time.time()

        try:
            style_tags = self._current_style_tags.pop(umo, None)
            default_style = str(persona.get("default_style", "") or "").strip()
            if not style_tags and default_style:
                style_tags = [default_style]

            voice = str(persona.get("voice", "") or "").strip() or provider.get_default_voice()
            speed_override = float(persona.get("speed", 0) or 0)

            dual = build_dual_text(
                plain_text,
                provider_style_format=provider.style_tag_format,
                keep_minimax_expressions=(provider.provider_name == "minimax"),
                keep_minimax_pauses=(provider.provider_name == "minimax"),
            )

            tts_text = dual.tts_text
            if style_tags:
                tts_text = provider.apply_style_tags(dual.tts_text, style_tags)

            temp_dir.mkdir(exist_ok=True)

            audio_path = await provider.synth(
                text=dual.tts_text if not style_tags else tts_text,
                voice=voice,
                out_dir=temp_dir,
                speed=speed_override if speed_override > 0 else None,
                emotion=style_tags[0] if style_tags and provider.supports_emotion else None,
                style_tags=style_tags,
            )

            if audio_path and audio_path.exists():
                persona_tvo = self.config.get_persona_text_voice_output(umo)
                text_voice = persona_tvo if persona_tvo is not None else self.config.is_text_voice_output()
                if text_voice:
                    display_text = strip_all_style_tags(plain_text)
                    for i, comp in enumerate(result.chain):
                        if isinstance(comp, Plain):
                            result.chain[i] = Plain(display_text)
                    result.chain.append(Record(file=str(audio_path)))
                else:
                    result.chain.clear()
                    result.chain.append(Record(file=str(audio_path)))

                self._cooldowns[umo] = time.time()
                logger.info(f"[TTS+] 语音合成成功: {audio_path.name}, 风格={style_tags}")
            else:
                logger.debug(f"[TTS+] 语音合成未返回音频")

        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error(f"[TTS+] 语音合成流程失败: {e}", exc_info=True)
        finally:
            self._inflight.pop(inflight_key, None)

    async def terminate(self):
        for provider in self._providers.values():
            try:
                await provider.close()
            except Exception:
                pass
        self._providers.clear()
