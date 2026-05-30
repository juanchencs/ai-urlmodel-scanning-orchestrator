"""Minimal local runner for payload validation demo."""

from __future__ import annotations

from schemas import parse_scan_request


def main() -> None:
    payload = {
        "MODEL_VERSION": "20250301",
        "DATA_SOURCE": "VT",
        "URL_TXT": "https://example.com\nhttps://example.org",
    }

    request = parse_scan_request(payload)
    url_count = len([line for line in request.url_txt.splitlines() if line.strip()])

    print("Payload accepted.")
    print(f"Model version: {request.model_version}")
    print(f"Data source: {request.data_source}")
    print(f"URL count: {url_count}")


if __name__ == "__main__":
    main()

