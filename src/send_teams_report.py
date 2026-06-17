"""Send the AI-supported URL scan report to a Microsoft Teams channel.

This is the final step of the pipeline. It takes:
- the Nova-generated summary text, and
- the three chart images produced by ``ai_analysis_report.py``

It uploads the charts to S3 (so Teams can render them via public/presigned
URLs) and posts an Adaptive Card to the configured Teams Incoming Webhook.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import boto3
import requests


def upload_chart_to_s3(
    local_path: Path,
    bucket: str,
    prefix: str,
    expires_in: int = 3600,
) -> str:
    """Upload a chart image to S3 and return a presigned GET URL."""
    s3 = boto3.client("s3")
    key = f"{prefix.strip('/')}/{local_path.name}"
    s3.upload_file(str(local_path), bucket, key, ExtraArgs={"ContentType": "image/png"})
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_in,
    )


def summary_to_bullets(summary_text: str) -> list[str]:
    """Normalize a raw summary string into clean bullet strings."""
    bullets: list[str] = []
    for line in summary_text.splitlines():
        line = line.strip()
        if not line:
            continue
        for marker in ("- ", "* ", "• "):
            if line.startswith(marker):
                line = line[len(marker):].strip()
                break
        bullets.append(line)
    return bullets or ["(no summary content)"]


def build_adaptive_card(
    title: str,
    summary_text: str,
    chart_urls: dict[str, str],
) -> dict:
    """Build a Teams Adaptive Card payload with summary and chart images."""
    body: list[dict] = [
        {
            "type": "TextBlock",
            "size": "Large",
            "weight": "Bolder",
            "text": title,
            "wrap": True,
        }
    ]

    for bullet in summary_to_bullets(summary_text):
        body.append({"type": "TextBlock", "text": f"- {bullet}", "wrap": True})

    chart_titles = {
        "chart_score": "ML Score Distribution",
        "chart_length": "URL Length Distribution",
        "chart_keywords": "Top Suspicious Keywords",
    }
    for key, url in chart_urls.items():
        body.append(
            {
                "type": "TextBlock",
                "weight": "Bolder",
                "text": chart_titles.get(key, key),
                "wrap": True,
            }
        )
        body.append({"type": "Image", "url": url, "size": "Stretch"})

    return {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "type": "AdaptiveCard",
                    "version": "1.4",
                    "body": body,
                },
            }
        ],
    }


def send_report(
    webhook_url: str,
    summary_text: str,
    chart_paths: dict[str, Path],
    bucket: str,
    prefix: str,
    title: str = "URL Model Scan Report (AI-supported)",
) -> int:
    """Upload charts, build the card, and post it to the Teams webhook."""
    chart_urls = {
        name: upload_chart_to_s3(path, bucket=bucket, prefix=prefix)
        for name, path in chart_paths.items()
        if path.exists()
    }

    card = build_adaptive_card(title=title, summary_text=summary_text, chart_urls=chart_urls)
    response = requests.post(webhook_url, json=card, timeout=60)
    print("Teams POST status:", response.status_code)
    print("Teams POST body:", response.text)
    response.raise_for_status()
    return response.status_code


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Send AI-supported URL scan report to Microsoft Teams.")
    parser.add_argument("--webhook-url", required=True, help="Microsoft Teams Incoming Webhook URL")
    parser.add_argument("--summary-file", required=True, help="Path to a text file with the Nova summary")
    parser.add_argument("--bucket", default="example-bucket", help="S3 bucket for chart hosting")
    parser.add_argument("--prefix", default="mlmodels/urlmodel/reports", help="S3 prefix for chart hosting")
    parser.add_argument("--chart-score", default="chart_score.png", help="Path to ML score chart")
    parser.add_argument("--chart-length", default="chart_length.png", help="Path to URL length chart")
    parser.add_argument("--chart-keywords", default="chart_keywords.png", help="Path to keywords chart")
    parser.add_argument("--title", default="URL Model Scan Report (AI-supported)", help="Card title")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    summary_text = Path(args.summary_file).read_text(encoding="utf-8")
    send_report(
        webhook_url=args.webhook_url,
        summary_text=summary_text,
        chart_paths={
            "chart_score": Path(args.chart_score),
            "chart_length": Path(args.chart_length),
            "chart_keywords": Path(args.chart_keywords),
        },
        bucket=args.bucket,
        prefix=args.prefix,
        title=args.title,
    )


if __name__ == "__main__":
    main()
