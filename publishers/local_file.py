"""
Local file publishers for report generation.
"""
from __future__ import annotations

import html
import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional
from publishers.targets import resolve_output_targets


def _default_output_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")


def resolve_output_dir(config: dict) -> str:
    local_cfg = config.get("local_output", {})
    output_dir = local_cfg.get("output_dir") or _default_output_dir()
    return os.path.abspath(output_dir)


def _write_with_latest(
    output_dir: str,
    filename: str,
    latest_filename: str,
    content: str,
) -> str:
    path = os.path.join(output_dir, filename)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)

    latest_path = os.path.join(output_dir, latest_filename)
    with open(latest_path, "w", encoding="utf-8") as handle:
        handle.write(content)

    _write_output_index(output_dir)
    return path


def _write_output_index(output_dir: str) -> str:
    date_display = _generated_at()
    entries = [
        ("Daily HTML", "Latest browser view for the daily paper report.", "daily_latest.html"),
        ("Daily Markdown", "Latest markdown export for notes, git, or static hosting.", "daily_latest.md"),
        ("Conference HTML", "Latest browser view for the conference monitor.", "conference_latest.html"),
        ("Conference Markdown", "Latest markdown export for the conference monitor.", "conference_latest.md"),
        ("Daily Demo HTML", "Screenshot-friendly demo page with built-in sample papers.", "daily_demo.html"),
        ("Daily Demo Markdown", "Stable markdown demo artifact for docs and sample snippets.", "daily_demo.md"),
        ("Conference Demo HTML", "Screenshot-friendly conference demo page with built-in venue updates.", "conference_demo.html"),
        ("Conference Demo Markdown", "Stable markdown conference demo artifact.", "conference_demo.md"),
    ]
    available_count = 0
    items = []
    for label, description, filename in entries:
        file_path = os.path.join(output_dir, filename)
        exists = os.path.exists(file_path)
        if exists:
            available_count += 1
        status = "Available" if exists else "Not generated yet"
        status_class = "ready" if exists else "waiting"
        link = (
            f'<a href="{html.escape(filename)}">{html.escape(label)}</a>'
            if exists
            else html.escape(label)
        )
        items.append(
            "\n".join(
                [
                    '      <li class="entry">',
                    "        <div>",
                    f"          <div class=\"entry-title\">{link}</div>",
                    f"          <div class=\"entry-desc\">{html.escape(description)}</div>",
                    "        </div>",
                    f"        <span class=\"status {status_class}\">{html.escape(status)}</span>",
                    "      </li>",
                ]
            )
        )

    daily_count = sum(
        os.path.exists(os.path.join(output_dir, name))
        for name in ("daily_latest.html", "daily_latest.md", "daily_demo.html", "daily_demo.md")
    )
    conference_count = sum(
        os.path.exists(os.path.join(output_dir, name))
        for name in ("conference_latest.html", "conference_latest.md", "conference_demo.html", "conference_demo.md")
    )
    body = "\n".join(
        [
            '    <section class="hero">',
            '      <span class="eyebrow">local output hub</span>',
            "      <h1>Paper Push Output Index</h1>",
            "      <p class=\"meta\">A single landing page for the latest reports plus stable demo files for screenshots and GIF capture.</p>",
            f'      <p class="meta">Updated at {html.escape(date_display)}</p>',
            '      <div class="hero-grid">',
            '        <div class="stat">',
            '          <div class="stat-label">Available Artifacts</div>',
            f'          <div class="stat-value">{available_count}/8</div>',
            '        </div>',
            '        <div class="stat">',
            '          <div class="stat-label">Daily Outputs</div>',
            f'          <div class="stat-value">{daily_count}/4</div>',
            '        </div>',
            '        <div class="stat">',
            '          <div class="stat-label">Conference Outputs</div>',
            f'          <div class="stat-value">{conference_count}/4</div>',
            '        </div>',
            "      </div>",
            "    </section>",
            '    <section class="paper">',
            '      <h2 class="section-title">Latest Reports</h2>',
            f'      <div class="summary"><ul class="index-list">{"".join(items)}</ul></div>',
            "    </section>",
        ]
    )
    content = _html_page("Paper Push Output Index", body).replace(
        ".summary {",
        ".index-list { list-style: none; padding: 0; margin: 0; }\n"
        ".entry { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; padding: 16px 0; border-bottom: 1px solid var(--line); }\n"
        ".entry:last-child { border-bottom: 0; }\n"
        ".entry-title { font-size: 18px; font-weight: 700; margin-bottom: 4px; }\n"
        ".entry-desc { color: var(--muted); line-height: 1.6; }\n"
        ".status { white-space: nowrap; border-radius: 999px; padding: 6px 10px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.05em; }\n"
        ".status.ready { background: var(--accent-soft); color: var(--accent); }\n"
        ".status.waiting { background: #f3e3ce; color: #c67628; }\n"
        ".summary {",
        1,
    )
    index_path = os.path.join(output_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return index_path


def _render_empty_report(config: dict) -> str:
    directions = config.get("research_profile", {}).get("directions", [])
    lines = [
        "# Daily Paper Report",
        "",
        f"- Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "- Status: no selected papers",
    ]
    if directions:
        lines.append(f"- Research focus: {', '.join(directions[:3])}")
    lines.extend(["", "No papers were selected in this run.", ""])
    return "\n".join(lines)


def _report_title() -> str:
    return "Daily Paper Report"


def _conference_report_title() -> str:
    return "Conference Monitor Report"


def _generated_at() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def _paper_source_label(paper: Dict) -> str:
    source = paper.get("source", "arxiv")
    if source == "both":
        return "arXiv + Hugging Face"
    if source == "huggingface":
        return "Hugging Face"
    if source == "conference":
        return paper.get("venue", "Conference")
    return "arXiv"


def render_markdown_report(papers: Iterable[Dict], config: dict) -> str:
    papers = list(papers)
    if not papers:
        return _render_empty_report(config)

    lines = [
        f"# {_report_title()}",
        "",
        f"- Generated at: {_generated_at()}",
        f"- Selected papers: {len(papers)}",
        "",
    ]

    for index, paper in enumerate(papers, 1):
        lines.append(f"## {index}. {paper['title']}")
        lines.append("")
        lines.append(f"- Source: {_paper_source_label(paper)}")
        lines.append(f"- Score: {paper.get('score', 0)}/10")
        lines.append(f"- URL: {paper.get('url', '')}")
        if paper.get("code_url"):
            lines.append(f"- Code: {paper['code_url']}")
        if paper.get("score_reason"):
            lines.append(f"- Why selected: {paper['score_reason']}")
        lines.append("")
        summary_text = (paper.get("summary_text") or paper.get("abstract") or "").strip()
        if summary_text:
            lines.append("### Summary")
            lines.append("")
            lines.append(summary_text)
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _html_page(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <style>
    :root {{
      --bg: #f4f1e8;
      --panel: #fffdf8;
      --ink: #1e2430;
      --muted: #5f6776;
      --line: #d7cfbe;
      --accent: #0d6e6e;
      --accent-deep: #0a5252;
      --accent-soft: #dff1ed;
      --warm: #c67628;
      --warm-soft: #f3e3ce;
      --score: #a63f00;
      --shadow: 0 20px 60px rgba(31, 36, 48, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top right, rgba(13, 110, 110, 0.14), transparent 25%),
        linear-gradient(180deg, #f6f2e9 0%, var(--bg) 100%);
    }}
    .wrap {{
      max-width: 960px;
      margin: 0 auto;
      padding: 48px 20px 72px;
    }}
    .hero {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 24px;
      padding: 28px;
      box-shadow: var(--shadow);
      margin-bottom: 24px;
    }}
    .eyebrow {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 13px;
      letter-spacing: 0.04em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 14px 0 8px;
      font-size: clamp(32px, 5vw, 52px);
      line-height: 1.05;
    }}
    .meta {{
      color: var(--muted);
      font-size: 15px;
    }}
    .hero-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .stat {{
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px 16px;
      background: linear-gradient(180deg, #fffefb 0%, #fbf7ee 100%);
    }}
    .stat-label {{
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .stat-value {{
      font-size: 24px;
      font-weight: 700;
      color: var(--accent-deep);
    }}
    .paper {{
      background: rgba(255, 253, 248, 0.92);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 22px;
      box-shadow: var(--shadow);
      margin-bottom: 18px;
    }}
    .paper h2 {{
      margin: 0 0 10px;
      font-size: 26px;
      line-height: 1.2;
    }}
    .facts {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin: 0 0 14px;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-size: 14px;
    }}
    .facts li {{
      padding: 6px 10px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fff;
    }}
    .score {{
      color: var(--score);
      font-weight: 700;
    }}
    .summary {{
      margin-top: 16px;
      padding-top: 16px;
      border-top: 1px solid var(--line);
      white-space: pre-wrap;
      line-height: 1.7;
    }}
    a {{
      color: var(--accent);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .empty {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      padding: 28px;
      box-shadow: var(--shadow);
      color: var(--muted);
      font-size: 18px;
    }}
    .section-title {{
      margin: 0 0 14px;
      font-size: 26px;
    }}
  </style>
</head>
<body>
  <main class="wrap">
{body}
  </main>
</body>
</html>
"""


def render_html_report(papers: Iterable[Dict], config: dict) -> str:
    papers = list(papers)
    hero = [
        '    <section class="hero">',
        '      <span class="eyebrow">paper intelligence</span>',
        f"      <h1>{html.escape(_report_title())}</h1>",
        f'      <p class="meta">Generated at {html.escape(_generated_at())}</p>',
    ]
    if papers:
        hero.append(f'      <p class="meta">Selected papers: {len(papers)}</p>')
    else:
        hero.append('      <p class="meta">Selected papers: 0</p>')
    hero.append("    </section>")

    sections = ["\n".join(hero)]
    if not papers:
        sections.append(
            '    <section class="empty">No papers were selected in this run.</section>'
        )
        return _html_page(_report_title(), "\n".join(sections))

    for index, paper in enumerate(papers, 1):
        summary_text = (paper.get("summary_text") or paper.get("abstract") or "").strip()
        links = [f'<a href="{html.escape(paper.get("url", ""))}">Paper link</a>']
        if paper.get("code_url"):
            links.append(f'<a href="{html.escape(paper["code_url"])}">Code</a>')
        links_html = " | ".join(links)
        section = [
            '    <section class="paper">',
            f"      <h2>{index}. {html.escape(paper['title'])}</h2>",
            '      <ul class="facts">',
            f"        <li>{html.escape(_paper_source_label(paper))}</li>",
            f'        <li class="score">Score {html.escape(str(paper.get("score", 0)))}/10</li>',
            "      </ul>",
            f"      <p>{links_html}</p>",
        ]
        if paper.get("score_reason"):
            section.append(
                f"      <p><strong>Why selected:</strong> {html.escape(paper['score_reason'])}</p>"
            )
        if summary_text:
            section.append(f'      <div class="summary">{html.escape(summary_text)}</div>')
        section.append("    </section>")
        sections.append("\n".join(section))
    return _html_page(_report_title(), "\n".join(sections))


def write_markdown_report(
    papers: Iterable[Dict],
    config: dict,
    filename: Optional[str] = None,
) -> str:
    output_dir = resolve_output_dir(config)
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    content = render_markdown_report(papers, config)
    return _write_with_latest(output_dir, filename, "daily_latest.md", content)


def write_html_report(
    papers: Iterable[Dict],
    config: dict,
    filename: Optional[str] = None,
) -> str:
    output_dir = resolve_output_dir(config)
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"daily_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    content = render_html_report(papers, config)
    return _write_with_latest(output_dir, filename, "daily_latest.html", content)


def render_conference_markdown_report(summary: dict, config: dict) -> str:
    lines = [
        f"# {_conference_report_title()}",
        "",
        f"- Generated at: {_generated_at()}",
        f"- Detected papers: {summary.get('detected_total', 0)}",
        f"- Relevant papers: {summary.get('relevant_total', 0)}",
        "",
        summary.get("message", "Conference status checked."),
        "",
    ]

    venue_counts = summary.get("venue_counts", {})
    if venue_counts:
        lines.extend(["## Detected Venues", ""])
        for venue, count in sorted(venue_counts.items()):
            relevant = summary.get("relevant_by_venue", {}).get(venue, 0)
            lines.append(f"- {venue}: new {count}, relevant {relevant}")
        lines.append("")

    not_released = summary.get("not_released", [])
    if not_released:
        lines.extend(["## Not Released Yet", ""])
        for venue in sorted(not_released):
            lines.append(f"- {venue}")
        lines.append("")

    errors = summary.get("errors", [])
    if errors:
        lines.extend(["## Errors", ""])
        for item in errors:
            lines.append(f"- {item}")
        lines.append("")

    if summary.get("doc_url"):
        lines.extend(["## Knowledge Base", "", summary["doc_url"], ""])

    return "\n".join(lines).rstrip() + "\n"


def render_conference_html_report(summary: dict, config: dict) -> str:
    hero = [
        '    <section class="hero">',
        '      <span class="eyebrow">conference radar</span>',
        f"      <h1>{html.escape(_conference_report_title())}</h1>",
        f'      <p class="meta">Generated at {html.escape(_generated_at())}</p>',
        f'      <p class="meta">Detected papers: {summary.get("detected_total", 0)} | Relevant papers: {summary.get("relevant_total", 0)}</p>',
        "    </section>",
    ]
    sections = ["\n".join(hero)]

    sections.append(
        "\n".join(
            [
                '    <section class="paper">',
                f'      <p>{html.escape(summary.get("message", "Conference status checked."))}</p>',
                "    </section>",
            ]
        )
    )

    venue_counts = summary.get("venue_counts", {})
    if venue_counts:
        items = []
        for venue, count in sorted(venue_counts.items()):
            relevant = summary.get("relevant_by_venue", {}).get(venue, 0)
            items.append(f"<li>{html.escape(venue)}: new {count}, relevant {relevant}</li>")
        sections.append(
            "\n".join(
                [
                    '    <section class="paper">',
                    "      <h2>Detected Venues</h2>",
                    f"      <div class=\"summary\"><ul>{''.join(items)}</ul></div>",
                    "    </section>",
                ]
            )
        )

    not_released = summary.get("not_released", [])
    if not_released:
        items = "".join(f"<li>{html.escape(venue)}</li>" for venue in sorted(not_released))
        sections.append(
            "\n".join(
                [
                    '    <section class="paper">',
                    "      <h2>Not Released Yet</h2>",
                    f"      <div class=\"summary\"><ul>{items}</ul></div>",
                    "    </section>",
                ]
            )
        )

    errors = summary.get("errors", [])
    if errors:
        items = "".join(f"<li>{html.escape(item)}</li>" for item in errors)
        sections.append(
            "\n".join(
                [
                    '    <section class="paper">',
                    "      <h2>Errors</h2>",
                    f"      <div class=\"summary\"><ul>{items}</ul></div>",
                    "    </section>",
                ]
            )
        )

    if summary.get("doc_url"):
        sections.append(
            "\n".join(
                [
                    '    <section class="paper">',
                    "      <h2>Knowledge Base</h2>",
                    f'      <p><a href="{html.escape(summary["doc_url"])}">Feishu doc</a></p>',
                    "    </section>",
                ]
            )
        )

    return _html_page(_conference_report_title(), "\n".join(sections))


def write_conference_markdown_report(
    summary: dict,
    config: dict,
    filename: Optional[str] = None,
) -> str:
    output_dir = resolve_output_dir(config)
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"conference_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"

    content = render_conference_markdown_report(summary, config)
    return _write_with_latest(output_dir, filename, "conference_latest.md", content)


def write_conference_html_report(
    summary: dict,
    config: dict,
    filename: Optional[str] = None,
) -> str:
    output_dir = resolve_output_dir(config)
    os.makedirs(output_dir, exist_ok=True)

    if not filename:
        filename = f"conference_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"

    content = render_conference_html_report(summary, config)
    return _write_with_latest(output_dir, filename, "conference_latest.html", content)
