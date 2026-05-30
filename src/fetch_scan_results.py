"""Fetch URL scan results from REST API and save CSV locally."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import requests


def submit_scan_request(
    api_url: str,
    model_version: str,
    data_source: str,
    url_txt: str,
    timeout_seconds: int = 900,
) -> dict:
    payload = {
        "MODEL_VERSION": model_version,
        "DATA_SOURCE": data_source,
        "URL_TXT": url_txt,
    }
    response = requests.post(api_url, json=payload, timeout=timeout_seconds)
    response.raise_for_status()
    return response.json()


def download_output_csv(
    download_url: str,
    output_file: Path,
    max_attempts: int = 30,
    poll_seconds: int = 10,
) -> Path:
    csv_resp = None
    for _ in range(max_attempts):
        resp = requests.get(download_url, timeout=60)
        if resp.status_code == 200 and resp.content:
            csv_resp = resp
            break
        time.sleep(poll_seconds)

    if csv_resp is None:
        raise RuntimeError("CSV not available within polling window.")

    output_file.write_bytes(csv_resp.content)
    return output_file


def run(
    api_url: str,
    model_version: str,
    data_source: str,
    url_file: Path,
) -> Path:
    url_txt = url_file.read_text(encoding="utf-8")
    data = submit_scan_request(
        api_url=api_url,
        model_version=model_version,
        data_source=data_source,
        url_txt=url_txt,
    )
    print("POST response:")
    print(json.dumps(data, indent=2))

    output_path = Path(data["output_file"])
    download_output_csv(download_url=data["download_url"], output_file=output_path)
    print(f"Downloaded: {output_path}")
    return output_path


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Submit URL scan request and download output CSV.")
    parser.add_argument("--api-url", required=True, help="REST API endpoint, e.g. https://.../prod/scan")
    parser.add_argument("--model-version", required=True, help="Model version, e.g. 20250301")
    parser.add_argument("--data-source", required=True, help="Data source label, e.g. VT")
    parser.add_argument("--url-file", default="urltest.txt", help="Path to text file containing URLs")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run(
        api_url=args.api_url,
        model_version=args.model_version,
        data_source=args.data_source,
        url_file=Path(args.url_file),
    )


if __name__ == "__main__":
    main()
