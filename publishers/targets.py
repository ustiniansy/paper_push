"""
Helpers for resolving configured output targets.
"""
from __future__ import annotations

from typing import List


def resolve_output_targets(config: dict) -> List[str]:
    runtime = config.get("runtime", {})
    outputs = runtime.get("outputs")
    if isinstance(outputs, list):
        normalized = [str(item).strip().lower() for item in outputs if str(item).strip()]
        return normalized or ["feishu"]
    if isinstance(outputs, str) and outputs.strip():
        return [outputs.strip().lower()]
    return ["feishu"]


def has_output_target(config: dict, *targets: str) -> bool:
    configured = set(resolve_output_targets(config))
    return any(target in configured for target in targets)


def local_output_enabled(config: dict) -> bool:
    return has_output_target(config, "markdown", "md", "html")


def feishu_output_enabled(config: dict) -> bool:
    return has_output_target(config, "feishu")
