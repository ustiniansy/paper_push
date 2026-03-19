# Contributing

Thanks for taking the time to improve `paper_push`.

## What matters most

- Keep changes focused and easy to review.
- Prefer small, testable steps over broad refactors.
- Preserve the current daily and conference flows unless a change explicitly improves them.
- Avoid adding new dependencies unless they are necessary.

## Before opening a PR

- Run the test suite locally.
- Verify the daily pipeline still works in `--dry-run` mode.
- If you changed output formats, inspect the generated files in `output/`.
- If you changed publisher behavior, check both daily and conference paths.

## Suggested workflow

1. Create a branch from the latest main branch.
2. Make one logical change per commit.
3. Add or update tests for behavior changes.
4. Update docs only when the user-facing behavior changed.
5. Open a PR with a short summary and the verification you ran.

## Local checks

```powershell
py -3 -m unittest discover -s tests -p "test_*.py"
```

If you are on Windows and using the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## Reporting issues

Include:

- What you expected
- What happened instead
- The command you ran
- Any relevant logs or screenshots

## Code style

- Keep ASCII-only edits unless the file already uses non-ASCII text.
- Use clear names for new helpers.
- Prefer explicit tests over indirect coverage.
- Do not change unrelated behavior while fixing a bug.
