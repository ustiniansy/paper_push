# Paper Push

[English](README.md) | [简体中文](README.zh-CN.md)

`paper_push` is a paper-intelligence system for researchers and labs.

It is built around three things:

- Incremental paper collection with lower miss risk
- Conference monitoring for target venues
- Multi-output delivery for local files and chat platforms

The pipeline fetches papers from `arXiv` and `Hugging Face Daily Papers`, filters them by your research profile, scores relevance with DeepSeek, generates Chinese summaries, and publishes the result to Feishu, Telegram, Slack, or local files.

## Demo Preview

![Paper Push Demo Preview](docs/assets/paper-push-demo.gif)

### Screenshots

![Output Index](docs/assets/paper-push-output-index.png)

![Daily Demo](docs/assets/paper-push-daily-demo.png)

![Conference Demo](docs/assets/paper-push-conference-demo.png)

## Quickstart

If you want screenshot-ready demo assets without configuring any APIs, run:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py demo
```

This writes a polished local showcase into `output/` using built-in sample papers and conference data. It is the fastest path for README screenshots, GIF capture, and static previews.

If you want the real pipeline next, run the local output path:

```powershell
copy config.yaml.example config.yaml
.\.venv\Scripts\python.exe main.py daily --dry-run --output markdown --output html
```

This writes to `output/`:

- `daily_latest.md`
- `daily_latest.html`
- `conference_latest.md`
- `conference_latest.html`
- `index.html`

If you want a built-in research profile instead of editing keywords first:

```powershell
.\.venv\Scripts\python.exe main.py daily --profile multimodal --dry-run --output markdown --output html
```

Available presets:

- `multimodal`
- `vision`
- `nlp`
- `agents`

## Installation

For normal source installs:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

After installation, you can use either the module entrypoint:

```powershell
.\.venv\Scripts\python.exe main.py demo
```

or the console script:

```powershell
.\.venv\Scripts\paper-push.exe demo
```

On macOS or Linux, replace the virtual-environment commands with:

```bash
python3 -m venv .venv
./.venv/bin/python -m pip install -e .
./.venv/bin/paper-push demo
```

## Commands

`main.py` now supports subcommands:

- `daily`
  Runs the normal daily pipeline, then conference monitoring.
- `conference`
  Runs only the conference monitor path.
- `demo`
  Generates screenshot-ready local artifacts with built-in sample content.

Examples:

```powershell
.\.venv\Scripts\python.exe main.py demo
.\.venv\Scripts\python.exe main.py daily --output markdown --output telegram
.\.venv\Scripts\python.exe main.py conference --output html --output slack
py -3 main.py --seed-conference-baseline
```

If you omit the subcommand, the default behavior remains the normal daily flow.

## Output Modes

The `runtime.outputs` config field and the `--output` flag support:

- `feishu`
- `markdown`
- `html`
- `telegram`
- `slack`

You can mix outputs freely. For example, local files are useful for inspection, while Telegram or Slack is useful for team delivery.

## Standout Feature

Conference monitoring is a first-class feature, not a side effect of the daily digest.

Every normal run also checks whether configured conferences have new papers. The monitor reports:

- Whether the current run found new conference papers
- Which venues have new papers
- Which venues are still unreleased in the current year window

If you want to initialize the conference baseline from currently visible papers without summaries or pushes:

```powershell
py -3 main.py --seed-conference-baseline
```

The local output path also renders dedicated conference reports, so the latest venue status is easy to open in a browser or share as a file.

## Configuration

Copy the example config and fill in the fields you need:

```powershell
copy config.yaml.example config.yaml
```

For local output, you still need:

- `llm.api_key`

If you enable Feishu output, also set:

- `feishu.webhook_url`

If you enable interactive Feishu selection and knowledge-base writing, also set:

- `feishu.chat_id`
- `feishu.app_id`
- `feishu.app_secret`
- `feishu.wiki_space_id`
- `feishu.wiki_parent_node`

If you enable Telegram or Slack output, also set:

- `telegram.bot_token`
- `telegram.chat_id`
- `slack.webhook_url`

Missing required fields fail fast at startup with a clear message.

## Local Artifacts

The local writer produces both archive files and stable `latest` files:

- `daily_report_YYYYMMDD_HHMMSS.md`
- `daily_report_YYYYMMDD_HHMMSS.html`
- `daily_latest.md`
- `daily_latest.html`
- `conference_report_YYYYMMDD_HHMMSS.md`
- `conference_report_YYYYMMDD_HHMMSS.html`
- `conference_latest.md`
- `conference_latest.html`
- `index.html`

## Development

Run the test suite before publishing changes:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

The GitHub Actions workflow runs the same test suite on Windows with Python 3.12.

## Security

- Do not commit real secrets in `config.yaml`
- `config.yaml` is already ignored by Git
- `.env`, `db/`, `output/`, virtual environments, and build artifacts are ignored
- Double-check logs and sample configs before sharing screenshots or publishing outputs
- See [SECURITY.md](SECURITY.md) for vulnerability reporting and secret-handling notes

## Release Checklist

Before making the repository public:

- Run the full test suite
- Confirm `config.yaml`, `.env`, `db/`, and `output/` are not tracked
- Search for accidental tokens, webhook URLs, and private chat IDs
- Update `CHANGELOG.md` when user-facing behavior changes
