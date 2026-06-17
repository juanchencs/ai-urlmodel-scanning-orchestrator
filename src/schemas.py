"""Input schema helpers for scan requests."""

from __future__ import annotations

import re
from dataclasses import dataclass

MODEL_RE = re.compile(r"^\d{6,12}$")
SOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass(frozen=True)
class ScanRequest:
    model_version: str
    data_source: str
    url_txt: str


def parse_scan_request(payload: dict) -> ScanRequest:
    """Validate and normalize a scan request payload."""
    model_version = str(payload.get("MODEL_VERSION", "")).strip()
    data_source = str(payload.get("DATA_SOURCE", "")).strip()
    url_txt = str(payload.get("URL_TXT", "")).strip()

    if not MODEL_RE.match(model_version):
        raise ValueError("MODEL_VERSION must be 6-12 digits, e.g. 123456.")
    if not SOURCE_RE.match(data_source):
        raise ValueError("DATA_SOURCE must match ^[A-Za-z0-9_-]{1,40}$.")
    if not url_txt:
        raise ValueError("URL_TXT must not be empty.")

    return ScanRequest(
        model_version=model_version,
        data_source=data_source,
        url_txt=url_txt,
    )

