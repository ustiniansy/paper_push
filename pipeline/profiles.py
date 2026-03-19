"""
Built-in research profile presets.
"""
from __future__ import annotations

from copy import deepcopy


PROFILE_PRESETS = {
    "multimodal": {
        "directions": [
            "Multimodal large language model reasoning and understanding",
            "Video understanding, video question answering, and video-language models",
            "Long-context multimodal models and long video understanding",
            "LLM agents, tool use, planning, and agentic systems",
            "Temporal grounding, moment retrieval, and video segment localization",
        ],
        "keywords": {
            "high_priority": [
                "multimodal",
                "multi-modal",
                "vision-language",
                "vision language model",
                "video understanding",
                "video question answering",
                "video reasoning",
                "long video",
                "VLM",
                "MLLM",
                "LMM",
                "agent",
                "agentic",
                "tool use",
                "temporal grounding",
                "moment retrieval",
            ],
            "medium_priority": [
                "LLM",
                "reasoning",
                "grounding",
                "instruction tuning",
                "benchmark",
                "visual understanding",
                "image understanding",
            ],
        },
    },
    "vision": {
        "directions": [
            "Computer vision representation learning and recognition",
            "Image understanding, detection, segmentation, and generation",
            "Vision-language learning and multimodal perception",
        ],
        "keywords": {
            "high_priority": [
                "computer vision",
                "image understanding",
                "object detection",
                "segmentation",
                "vision transformer",
                "vision-language",
                "visual grounding",
                "diffusion",
                "multimodal",
            ],
            "medium_priority": [
                "recognition",
                "representation learning",
                "image generation",
                "visual reasoning",
                "benchmark",
            ],
        },
    },
    "nlp": {
        "directions": [
            "Natural language processing and large language models",
            "Reasoning, instruction following, and knowledge-intensive NLP",
            "Retrieval-augmented generation, alignment, and evaluation",
        ],
        "keywords": {
            "high_priority": [
                "natural language processing",
                "large language model",
                "language model",
                "instruction following",
                "alignment",
                "retrieval-augmented generation",
                "RAG",
                "reasoning",
                "evaluation",
            ],
            "medium_priority": [
                "summarization",
                "question answering",
                "hallucination",
                "chain-of-thought",
                "preference optimization",
            ],
        },
    },
    "agents": {
        "directions": [
            "LLM agents, planning, tool use, and autonomous workflows",
            "Multi-agent coordination and reasoning systems",
            "Evaluation and reliability of agentic systems",
        ],
        "keywords": {
            "high_priority": [
                "agent",
                "agentic",
                "tool use",
                "planning",
                "web agent",
                "computer use",
                "multi-agent",
                "workflow",
                "autonomous",
            ],
            "medium_priority": [
                "reasoning",
                "memory",
                "orchestration",
                "evaluation",
                "reliability",
            ],
        },
    },
}


def available_profiles() -> list[str]:
    return sorted(PROFILE_PRESETS)


def apply_profile(config: dict, profile_name: str) -> dict:
    if profile_name not in PROFILE_PRESETS:
        raise KeyError(f"Unknown profile preset: {profile_name}")

    updated = deepcopy(config)
    updated["research_profile"] = deepcopy(PROFILE_PRESETS[profile_name])
    updated.setdefault("runtime", {})["profile"] = profile_name
    return updated
