"""Generate charts and AI-assisted summary from scan CSV."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import boto3
import matplotlib.pyplot as plt
import pandas as pd

try:
    from IPython.display import Markdown, display
except Exception:  # pragma: no cover
    Markdown = None
    display = None


def apply_plot_style() -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    plt.rcParams.update(
        {
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "xtick.labelsize": 10,
            "ytick.labelsize": 10,
            "figure.facecolor": "#f8fafc",
        }
    )


def display_structured_summary(summary_text: str) -> None:
    lines = [ln.strip() for ln in summary_text.splitlines() if ln.strip()]
    bullets = []
    for ln in lines:
        if ln.startswith("- ") or ln.startswith("* "):
            bullets.append(f"- {ln[2:].strip()}")
        elif ln.startswith("• "):
            bullets.append(f"- {ln[2:].strip()}")
        else:
            bullets.append(f"- {ln}")

    if Markdown and display:
        md = "### Nova Summary\n" + ("\n".join(bullets) if bullets else "- (empty)")
        display(Markdown(md))
    else:
        print("Nova Summary:")
        for item in bullets or ["- (empty)"]:
            print(item)


def build_keyword_counts(df: pd.DataFrame) -> dict[str, int]:
    keywords = ["login", "verify", "update", "secure", "account", "password", "invoice", "payment", "gift", "bank"]
    text = df["url"].astype(str).str.lower()
    counts = {k: int(text.str.contains(k, regex=False).sum()) for k in keywords}
    return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10])


def save_charts(df: pd.DataFrame, score_col: str, output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    scores = df[score_col].astype(float)

    # Chart 1: score distribution
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.hist(scores, bins=18, color="#3b82f6", edgecolor="#1e3a8a", alpha=0.9)
    ax.axvline(30, color="#ef4444", linestyle="--", linewidth=2, label="Malicious threshold (30)")
    ax.set_title("ML Score Distribution")
    ax.set_xlabel("ML score")
    ax.set_ylabel("URL count")
    ax.legend(frameon=True)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    score_path = output_dir / "chart_score.png"
    fig.savefig(score_path, dpi=200)
    plt.close(fig)

    # Chart 2: URL length distribution
    fig, ax = plt.subplots(figsize=(8, 4.8))
    url_len = df["url"].astype(str).str.len()
    ax.hist(url_len, bins=16, color="#10b981", edgecolor="#065f46", alpha=0.9)
    median_len = float(url_len.median())
    ax.axvline(median_len, color="#0f766e", linestyle="--", linewidth=2, label=f"Median: {median_len:.0f}")
    ax.set_title("URL Length Distribution")
    ax.set_xlabel("URL length (characters)")
    ax.set_ylabel("URL count")
    ax.legend(frameon=True)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    length_path = output_dir / "chart_length.png"
    fig.savefig(length_path, dpi=200)
    plt.close(fig)

    # Chart 3: keyword frequency
    top = build_keyword_counts(df)
    fig, ax = plt.subplots(figsize=(9, 5))
    bars = ax.bar(list(top.keys()), list(top.values()), color="#f59e0b", edgecolor="#92400e", alpha=0.9)
    ax.set_title("Top Suspicious Keywords in URLs")
    ax.set_xlabel("Keyword")
    ax.set_ylabel("Matched URL count")
    ax.grid(axis="y", alpha=0.25)
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    for bar in bars:
        h = bar.get_height()
        ax.annotate(f"{int(h)}", (bar.get_x() + bar.get_width() / 2, h), ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    keyword_path = output_dir / "chart_keywords.png"
    fig.savefig(keyword_path, dpi=200)
    plt.close(fig)

    return {
        "chart_score": score_path,
        "chart_length": length_path,
        "chart_keywords": keyword_path,
    }


def summarize_with_nova(
    total: int,
    flagged: int,
    mean_score: float,
    top_keywords: dict[str, int],
    region: str,
    model_id: str,
) -> str:
    prompt = f"""
You are helping with internal defensive security monitoring only.
Return no more than 4 short bullet points for an executive dashboard.
Use only aggregate metrics provided below; do not provide attack, evasion, or exploitation guidance.

Metrics:
- total_urls={total}
- flagged_count={flagged}
- flagged_rate={(flagged / max(total, 1)):.4f}
- mean_score={mean_score:.4f}
- keyword_frequency={json.dumps(top_keywords)}
"""
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    if hasattr(bedrock, "converse"):
        res = bedrock.converse(
            modelId=model_id,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 300, "temperature": 0.2},
        )
        content = res.get("output", {}).get("message", {}).get("content", [])
        return "\n".join([c.get("text", "") for c in content if "text" in c]).strip()

    body = {
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 300, "temperature": 0.2},
    }
    res = bedrock.invoke_model(
        modelId=model_id,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(res["body"].read())
    content = payload.get("output", {}).get("message", {}).get("content", [])
    return "\n".join([c.get("text", "") for c in content if "text" in c]).strip()


def run(
    csv_file: Path,
    region: str,
    model_id: str,
    output_dir: Path,
    teams_webhook: str | None = None,
    teams_bucket: str = "example-bucket",
    teams_prefix: str = "mlmodels/urlmodel/reports",
) -> None:
    apply_plot_style()
    df = pd.read_csv(csv_file)
    score_col = next((c for c in df.columns if re.match(r"^score\d+$", c)), None)
    if not score_col:
        raise RuntimeError("No score column like score20250301 found.")

    charts = save_charts(df=df, score_col=score_col, output_dir=output_dir)
    scores = df[score_col].astype(float)
    total = len(df)
    flagged = int((scores >= 30).sum())
    top = build_keyword_counts(df)
    summary = summarize_with_nova(
        total=total,
        flagged=flagged,
        mean_score=float(scores.mean()),
        top_keywords=top,
        region=region,
        model_id=model_id,
    )
    print("Summary:\n", summary or "(empty)")
    display_structured_summary(summary or "")
    print("Saved charts:")
    for name, path in charts.items():
        print(f"- {name}: {path}")

    # Final step: optionally deliver the AI-supported report to Microsoft Teams.
    if teams_webhook:
        from send_teams_report import send_report

        send_report(
            webhook_url=teams_webhook,
            summary_text=summary or "(no summary content)",
            chart_paths=charts,
            bucket=teams_bucket,
            prefix=teams_prefix,
        )
        print("Report sent to Microsoft Teams.")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate charts and Nova summary from URL scan CSV.")
    parser.add_argument("--csv-file", required=True, help="Path to output CSV file")
    parser.add_argument("--region", default="eu-west-2", help="AWS region for Bedrock")
    parser.add_argument("--nova-model-id", default="amazon.nova-lite-v1:0", help="Bedrock model ID")
    parser.add_argument("--output-dir", default=".", help="Directory to save chart images")
    parser.add_argument("--teams-webhook", default=None, help="Microsoft Teams Incoming Webhook URL (optional)")
    parser.add_argument("--teams-bucket", default="example-bucket", help="S3 bucket for hosting chart images")
    parser.add_argument(
        "--teams-prefix",
        default="mlmodels/urlmodel/reports",
        help="S3 prefix for hosting chart images",
    )
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    run(
        csv_file=Path(args.csv_file),
        region=args.region,
        model_id=args.nova_model_id,
        output_dir=Path(args.output_dir),
        teams_webhook=args.teams_webhook,
        teams_bucket=args.teams_bucket,
        teams_prefix=args.teams_prefix,
    )


if __name__ == "__main__":
    main()
