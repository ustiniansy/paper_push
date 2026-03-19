"""
Configuration validation helpers for clearer startup behavior.
"""
from __future__ import annotations

from typing import List

from publishers.targets import feishu_output_enabled, has_output_target, local_output_enabled


class ConfigValidationError(RuntimeError):
    """Raised when the runtime configuration is not sufficient to start."""


def _looks_unset(value: str) -> bool:
    if not value:
        return True
    return str(value).strip().startswith("YOUR_")


def validate_config(config: dict) -> List[str]:
    warnings: List[str] = []

    llm_cfg = config.get("llm", {})
    if _looks_unset(llm_cfg.get("api_key", "")):
        raise ConfigValidationError(
            "Missing required config `llm.api_key`. "
            "Local and Feishu modes both need an LLM key for scoring and summaries."
        )

    profile = config.get("research_profile", {})
    directions = profile.get("directions") or []
    keywords = profile.get("keywords") or {}
    if not directions:
        raise ConfigValidationError(
            "Missing required config `research_profile.directions`. "
            "Add at least one research direction so relevance scoring has a target."
        )
    if not keywords.get("high_priority") and not keywords.get("medium_priority"):
        warnings.append(
            "No research keywords configured. Keyword filtering may be too weak or skip too little."
        )

    if feishu_output_enabled(config):
        feishu_cfg = config.get("feishu", {})
        if _looks_unset(feishu_cfg.get("webhook_url", "")):
            raise ConfigValidationError(
                "Output target `feishu` is enabled but `feishu.webhook_url` is missing."
            )
        if not feishu_cfg.get("chat_id"):
            warnings.append(
                "Feishu chat_id is not configured. Candidate selection will fall back to terminal input."
            )
        docs_missing = [
            field
            for field in ("app_id", "app_secret", "wiki_space_id", "wiki_parent_node")
            if not feishu_cfg.get(field)
        ]
        if docs_missing:
            warnings.append(
                "Feishu docs credentials are incomplete. Group push can still run, but wiki/doc writing will be skipped."
            )

    if has_output_target(config, "telegram"):
        telegram_cfg = config.get("telegram", {})
        if _looks_unset(telegram_cfg.get("bot_token", "")) or _looks_unset(
            telegram_cfg.get("chat_id", "")
        ):
            raise ConfigValidationError(
                "Output target `telegram` is enabled but `telegram.bot_token` or `telegram.chat_id` is missing."
            )

    if has_output_target(config, "slack"):
        slack_cfg = config.get("slack", {})
        if _looks_unset(slack_cfg.get("webhook_url", "")):
            raise ConfigValidationError(
                "Output target `slack` is enabled but `slack.webhook_url` is missing."
            )

    if local_output_enabled(config):
        output_dir = config.get("local_output", {}).get("output_dir", "output")
        warnings.append(f"Local output enabled. Reports will be written under `{output_dir}`.")

    return warnings
