"""Helpers for generating screenshot-ready demo artifacts."""
from __future__ import annotations

from typing import Dict, List

from publishers.local_file import (
    write_conference_html_report,
    write_conference_markdown_report,
    write_html_report,
    write_markdown_report,
)


def _demo_papers() -> List[Dict]:
    return [
        {
            "title": "OmniCanvas: Multimodal Agents That Edit Video with Grounded Scene Memory",
            "source": "both",
            "score": 9,
            "url": "https://arxiv.org/abs/2503.01234",
            "code_url": "https://github.com/example/omnicanvas",
            "score_reason": "Strong match on multimodal agents, long-context scene editing, and practical system design.",
            "summary_text": (
                "This paper presents a multimodal agent stack for video editing. "
                "It keeps a persistent scene memory, grounds edits in temporal anchors, "
                "and plans tool usage across clips instead of frame-level prompts."
            ),
        },
        {
            "title": "SparseReasoner-VL: Budget-Aware Visual Reasoning with Dynamic Token Routing",
            "source": "arxiv",
            "score": 8,
            "url": "https://arxiv.org/abs/2503.05678",
            "code_url": "https://github.com/example/sparse-reasoner-vl",
            "score_reason": "Relevant to efficient multimodal reasoning and inference-time scaling.",
            "summary_text": (
                "The model routes visual tokens adaptively so harder regions receive more compute. "
                "The result is lower latency at similar accuracy, which is useful for deployment-oriented research tracking."
            ),
        },
        {
            "title": "MemoryPatch: Retrieval-Augmented UI Agents for Long-Horizon Desktop Tasks",
            "source": "huggingface",
            "score": 8,
            "url": "https://arxiv.org/abs/2503.07890",
            "code_url": "https://github.com/example/memory-patch",
            "score_reason": "Fits the agent tooling profile and includes concrete evaluation on realistic workflows.",
            "summary_text": (
                "MemoryPatch stores task state as structured retrieval records and uses them to recover after interruption. "
                "It is a strong example of an applied agent paper that is easy to explain in a daily digest."
            ),
        },
    ]



def _demo_conference_summary() -> Dict:
    return {
        "message": "Conference radar found new proceedings updates across the tracked venues. Two papers passed the current research profile threshold.",
        "detected_total": 7,
        "relevant_total": 2,
        "venue_counts": {"CVPR 2026": 3, "ICLR 2026": 2, "ACL 2026": 2},
        "relevant_by_venue": {"CVPR 2026": 1, "ICLR 2026": 1},
        "not_released": ["NeurIPS 2026", "ICML 2026"],
        "errors": [],
        "doc_url": "https://example.com/demo/conference-digest",
    }



def generate_demo_artifacts(config: dict) -> Dict[str, List[str]]:
    papers = _demo_papers()
    conference_summary = _demo_conference_summary()
    daily_paths = [
        write_markdown_report(papers, config, filename="daily_demo.md"),
        write_html_report(papers, config, filename="daily_demo.html"),
    ]
    conference_paths = [
        write_conference_markdown_report(conference_summary, config, filename="conference_demo.md"),
        write_conference_html_report(conference_summary, config, filename="conference_demo.html"),
    ]
    return {
        "daily_paths": daily_paths,
        "conference_paths": conference_paths,
        "daily_count": len(papers),
        "conference_detected": conference_summary["detected_total"],
        "conference_relevant": conference_summary["relevant_total"],
    }
