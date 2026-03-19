"""
Shared HTTP sessions for outbound network calls.
"""
from __future__ import annotations

from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_RETRY_SESSION: Optional[requests.Session] = None
_DEFAULT_SESSION: Optional[requests.Session] = None


def _build_session(with_retries: bool) -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": "paper-push-bot/1.0"})
    if with_retries:
        retry = Retry(
            total=3,
            connect=3,
            read=3,
            status=3,
            backoff_factor=0.5,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
            respect_retry_after_header=True,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
    return session


def get_retry_session() -> requests.Session:
    global _RETRY_SESSION
    if _RETRY_SESSION is None:
        _RETRY_SESSION = _build_session(with_retries=True)
    return _RETRY_SESSION


def get_default_session() -> requests.Session:
    global _DEFAULT_SESSION
    if _DEFAULT_SESSION is None:
        _DEFAULT_SESSION = _build_session(with_retries=False)
    return _DEFAULT_SESSION
