"""
Runtime flags and lightweight logging helpers.
"""
from __future__ import annotations

from dataclasses import dataclass


def is_dry_run(config: dict) -> bool:
    return bool(config.get("runtime", {}).get("dry_run", False))


def log(scope: str, message: str):
    print(f"[{scope}] {message}")


@dataclass
class ProgressBar:
    label: str
    total: int
    width: int = 24

    def __post_init__(self):
        self.current = 0
        self._render(force=True)

    def advance(self, step: int = 1, detail: str = ""):
        self.current = min(self.total, self.current + step)
        self._render(detail=detail)

    def finish(self, detail: str = ""):
        self.current = self.total
        self._render(detail=detail, force=True)

    def _render(self, detail: str = "", force: bool = False):
        total = max(self.total, 1)
        display_total = self.total if self.total > 0 else 0
        filled = int(self.width * self.current / total)
        bar = "#" * filled + "-" * (self.width - filled)
        percent = int(100 * self.current / total)
        suffix = f" {detail}" if detail else ""
        print(f"[Progress] {self.label} [{bar}] {self.current}/{display_total} {percent:3d}%{suffix}")
