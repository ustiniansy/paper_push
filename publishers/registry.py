"""
Capability-based publisher registry.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

from publishers.feishu_docs import create_daily_document
from publishers.feishu_webhook import (
    poll_user_reply,
    push_conference_status,
    push_to_feishu,
    send_candidate_card,
    send_confirmation,
)
from publishers.local_file import (
    write_conference_html_report,
    write_conference_markdown_report,
    write_html_report,
    write_markdown_report,
)
from publishers.slack import push_conference_to_slack, push_to_slack
from publishers.targets import resolve_output_targets
from publishers.telegram import push_conference_to_telegram, push_to_telegram


@dataclass
class PublishResult:
    target: str
    status: str
    detail: str = ""


@dataclass
class PublisherDefinition:
    name: str
    publish_digest: Optional[Callable[..., PublishResult]] = None
    choose_candidates: Optional[Callable[..., Optional[List[int]]]] = None
    write_knowledge_base: Optional[Callable[..., PublishResult]] = None
    publish_conference_status: Optional[Callable[..., PublishResult]] = None


def _publish_markdown(papers: Iterable[Dict], config: dict, **_: object) -> PublishResult:
    path = write_markdown_report(papers, config)
    return PublishResult(target="markdown", status="written", detail=path)


def _publish_html(papers: Iterable[Dict], config: dict, **_: object) -> PublishResult:
    path = write_html_report(papers, config)
    return PublishResult(target="html", status="written", detail=path)


def _publish_feishu(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
    **_: object,
) -> PublishResult:
    push_to_feishu(list(papers), config, doc_url=doc_url)
    return PublishResult(target="feishu", status="sent")


def _choose_feishu_candidates(
    papers: List[Dict],
    config: dict,
    poll_timeout_minutes: int = 60,
) -> Optional[List[int]]:
    chat_id = config.get("feishu", {}).get("chat_id", "")
    if not chat_id:
        return None
    msg_id = send_candidate_card(papers, config)
    if not msg_id:
        return None
    indices = poll_user_reply(
        config,
        total=len(papers),
        timeout_minutes=poll_timeout_minutes,
    )
    chosen = [papers[index] for index in indices]
    if chosen:
        send_confirmation(
            config,
            f"Received. Preparing {len(chosen)} papers for the knowledge base.",
        )
    return indices


def _write_feishu_knowledge_base(papers: List[Dict], config: dict) -> PublishResult:
    doc_url = create_daily_document(papers, config)
    if doc_url:
        send_confirmation(config, f"Done. Document updated: {doc_url}")
        return PublishResult(target="feishu_docs", status="written", detail=doc_url)
    send_confirmation(config, "Done.")
    return PublishResult(target="feishu_docs", status="skipped", detail="not_configured")


def _publish_telegram(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
    **_: object,
) -> PublishResult:
    push_to_telegram(list(papers), config, doc_url=doc_url)
    return PublishResult(target="telegram", status="sent")


def _publish_telegram_conference(summary: dict, config: dict) -> PublishResult:
    push_conference_to_telegram(summary, config)
    return PublishResult(target="telegram", status="sent")


def _publish_slack(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
    **_: object,
) -> PublishResult:
    push_to_slack(list(papers), config, doc_url=doc_url)
    return PublishResult(target="slack", status="sent")


def _publish_slack_conference(summary: dict, config: dict) -> PublishResult:
    push_conference_to_slack(summary, config)
    return PublishResult(target="slack", status="sent")


def _publish_feishu_conference(summary: dict, config: dict) -> PublishResult:
    push_conference_status(summary, config)
    return PublishResult(target="feishu", status="sent")


def _publish_markdown_conference(summary: dict, config: dict) -> PublishResult:
    path = write_conference_markdown_report(summary, config)
    return PublishResult(target="markdown", status="written", detail=path)


def _publish_html_conference(summary: dict, config: dict) -> PublishResult:
    path = write_conference_html_report(summary, config)
    return PublishResult(target="html", status="written", detail=path)


PUBLISHERS = {
    "markdown": PublisherDefinition(
        name="markdown",
        publish_digest=_publish_markdown,
        publish_conference_status=_publish_markdown_conference,
    ),
    "md": PublisherDefinition(
        name="markdown",
        publish_digest=_publish_markdown,
        publish_conference_status=_publish_markdown_conference,
    ),
    "html": PublisherDefinition(
        name="html",
        publish_digest=_publish_html,
        publish_conference_status=_publish_html_conference,
    ),
    "feishu": PublisherDefinition(
        name="feishu",
        publish_digest=_publish_feishu,
        choose_candidates=_choose_feishu_candidates,
        write_knowledge_base=_write_feishu_knowledge_base,
        publish_conference_status=_publish_feishu_conference,
    ),
    "telegram": PublisherDefinition(
        name="telegram",
        publish_digest=_publish_telegram,
        publish_conference_status=_publish_telegram_conference,
    ),
    "slack": PublisherDefinition(
        name="slack",
        publish_digest=_publish_slack,
        publish_conference_status=_publish_slack_conference,
    ),
}


def resolve_publishers(config: dict) -> List[PublisherDefinition]:
    resolved: List[PublisherDefinition] = []
    for target in resolve_output_targets(config):
        publisher = PUBLISHERS.get(target)
        if publisher:
            resolved.append(publisher)
    return resolved


def publish_daily_digest(
    papers: Iterable[Dict],
    config: dict,
    doc_url: Optional[str] = None,
    allow_network: bool = True,
) -> List[PublishResult]:
    papers = list(papers)
    results: List[PublishResult] = []
    for publisher in resolve_publishers(config):
        if not publisher.publish_digest:
            continue
        if not allow_network and publisher.name in {"feishu", "telegram", "slack"}:
            results.append(PublishResult(target=publisher.name, status="skipped", detail="dry-run"))
            continue
        results.append(publisher.publish_digest(papers, config, doc_url=doc_url))
    return results


def choose_candidate_indices(
    papers: List[Dict],
    config: dict,
    poll_timeout_minutes: int = 60,
) -> Optional[List[int]]:
    for publisher in resolve_publishers(config):
        if not publisher.choose_candidates:
            continue
        indices = publisher.choose_candidates(
            papers,
            config,
            poll_timeout_minutes=poll_timeout_minutes,
        )
        if indices is not None:
            return indices
    return None


def write_knowledge_base_outputs(
    papers: List[Dict],
    config: dict,
) -> List[PublishResult]:
    results: List[PublishResult] = []
    for publisher in resolve_publishers(config):
        if publisher.write_knowledge_base:
            results.append(publisher.write_knowledge_base(papers, config))
    return results


def publish_conference_status_outputs(
    summary: dict,
    config: dict,
    allow_network: bool = True,
) -> List[PublishResult]:
    results: List[PublishResult] = []
    for publisher in resolve_publishers(config):
        if not publisher.publish_conference_status:
            continue
        if not allow_network and publisher.name in {"feishu", "telegram", "slack"}:
            results.append(PublishResult(target=publisher.name, status="skipped", detail="dry-run"))
            continue
        results.append(publisher.publish_conference_status(summary, config))
    return results
