# Security Policy

## Supported Versions

The public repository currently supports the latest `main` branch.

## Reporting a Vulnerability

Please report security issues privately to the repository owner instead of opening a public issue with sensitive details.

Include:

- A short description of the issue
- Steps to reproduce, if available
- Any affected configuration fields or output targets

## Secret Handling

Do not commit real API keys, bot tokens, webhook URLs, chat IDs, or generated runtime databases.

The repository ignores:

- `config.yaml`
- `.env` files
- `db/`
- `output/`
- Python virtual environments and build artifacts

Use `config.yaml.example` for shareable defaults and put real credentials only in local ignored files or environment variables.

