#!/usr/bin/env python3
import json
import os
import random
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from analysis import (
    build_html_report,
    create_analysis_artifacts,
    detect_score_column,
    load_csv_from_s3,
)
from ecs_runner import ECSRunner, ECSRunResult


MODEL_PATTERN = re.compile(r"^\d{6,12}$")
DATASOURCE_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


@dataclass
class ScanRequest:
    model_number: str
    data_source: str
    url_txt: str


def _json_response(status_code: int, payload: dict[str, Any], content_type: str = "application/json"):
    body = json.dumps(payload, ensure_ascii=False) if content_type == "application/json" else payload["html"]
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": content_type},
        "body": body,
    }


def _parse_request(event: dict[str, Any]) -> ScanRequest:
    if "body" not in event:
        raise ValueError("Missing request body.")

    body = event["body"]
    if event.get("isBase64Encoded"):
        import base64

        body = base64.b64decode(body).decode("utf-8")

    payload = json.loads(body) if isinstance(body, str) else body

    for key in ("MODEL_NUMER", "DATA_SOURCE", "URL_TXT"):
        if key not in payload:
            raise ValueError(f"Missing required field: {key}")

    model_number = str(payload["MODEL_NUMER"]).strip()
    data_source = str(payload["DATA_SOURCE"]).strip()
    url_txt = str(payload["URL_TXT"]).strip()

    if not MODEL_PATTERN.match(model_number):
        raise ValueError("MODEL_NUMER must match ^\\d{6,12}$, for example 123456.")
    if not DATASOURCE_PATTERN.match(data_source):
        raise ValueError("DATA_SOURCE must match ^[A-Za-z0-9_-]{1,40}$.")

    parsed = urlparse(url_txt)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("URL_TXT must be a valid public http/https URL.")

    return ScanRequest(model_number=model_number, data_source=data_source, url_txt=url_txt)


def _build_output_file(data_source: str, model_number: str) -> str:
    rnd = random.randint(0, 99)
    return f"{data_source}_{model_number}_{rnd}.csv"


def _build_bedrock_summary(stats: dict[str, Any], model_id: str) -> list[str]:
    prompt = (
        "You are a security analyst. Analyze URL model output statistics and return at most 4 concise bullet points. "
        "Focus on malicious-rate implications, score distribution, URL length observations, and suspicious keyword signal. "
        "Each bullet should be short and actionable.\n\n"
        f"Stats JSON:\n{json.dumps(stats, indent=2)}"
    )

    client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "eu-west-2"))
    response = client.converse(
        modelId=model_id,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 500, "temperature": 0.2},
    )

    content = response.get("output", {}).get("message", {}).get("content", [])
    text_blocks = [block.get("text", "") for block in content if "text" in block]
    raw_text = "\n".join(text_blocks).strip()
    lines = [line.strip(" -\t") for line in raw_text.splitlines() if line.strip()]
    return lines[:4]


def _fallback_summary(stats: dict[str, Any]) -> list[str]:
    total = stats.get("total_rows", 0)
    malicious = stats.get("malicious_rows", 0)
    ratio = stats.get("malicious_ratio", 0.0)
    avg_score = stats.get("avg_score", 0.0)
    return [
        f"Processed {total} URLs, with {malicious} flagged as malicious (score >= 30).",
        f"Malicious rate is {ratio:.2%}, and mean ML score is {avg_score:.2f}.",
        "Score and URL-length distributions indicate where detections are concentrated.",
        "Top suspicious keywords highlight likely phishing/malware patterns for triage.",
    ]


def _extract_context_request_id(event: dict[str, Any]) -> str:
    context = event.get("requestContext") or {}
    req_id = context.get("requestId") or context.get("extendedRequestId")
    return str(req_id or uuid.uuid4())


def handler(event, context):
    try:
        request = _parse_request(event)
        request_id = getattr(context, "aws_request_id", None) or _extract_context_request_id(event)
        output_file = _build_output_file(request.data_source, request.model_number)

        results_bucket = os.environ["RESULTS_BUCKET"]
        results_prefix = os.getenv("RESULTS_PREFIX", "url-model-results")
        nova_model_id = os.getenv("NOVA_MODEL_ID") or os.getenv("FOUNDATION_MODEL_ID", "<FOUNDATION_MODEL_ID>")

        ecs_runner = ECSRunner(
            cluster_arn=os.environ["ECS_CLUSTER_ARN"],
            task_execution_role_arn=os.environ["TASK_EXECUTION_ROLE_ARN"],
            task_role_arn=os.environ["TASK_ROLE_ARN"],
            scanner_image_uri=os.environ["SCANNER_IMAGE_URI"],
            subnets=os.environ["ECS_SUBNETS"].split(","),
            security_groups=os.environ["ECS_SECURITY_GROUPS"].split(","),
            assign_public_ip=os.getenv("ECS_ASSIGN_PUBLIC_IP", "ENABLED"),
            cpu=os.getenv("ECS_TASK_CPU", "2048"),
            memory=os.getenv("ECS_TASK_MEMORY", "4096"),
        )

        run_result: ECSRunResult = ecs_runner.run_scan_task(
            model_version=request.model_number,
            url_txt=request.url_txt,
            data_source=request.data_source,
            output_file=output_file,
            results_bucket=results_bucket,
            results_prefix=results_prefix,
            request_id=request_id,
        )

        result_key = run_result.result_s3_key
        df = load_csv_from_s3(bucket=results_bucket, key=result_key)
        score_col = detect_score_column(df)
        artifacts = create_analysis_artifacts(
            dataframe=df,
            score_column=score_col,
            model_version=request.model_number,
            request_id=request_id,
            results_bucket=results_bucket,
            results_prefix=results_prefix,
        )

        try:
            summary_bullets = _build_bedrock_summary(artifacts.stats, nova_model_id)
            if not summary_bullets:
                summary_bullets = _fallback_summary(artifacts.stats)
        except Exception:
            summary_bullets = _fallback_summary(artifacts.stats)

        html = build_html_report(
            summary_bullets=summary_bullets,
            chart_urls=artifacts.chart_urls,
            stats=artifacts.stats,
            output_csv_uri=f"s3://{results_bucket}/{result_key}",
            model_version=request.model_number,
            data_source=request.data_source,
        )
        return _json_response(200, {"html": html}, content_type="text/html")
    except ValueError as exc:
        return _json_response(400, {"error": str(exc)})
    except (ClientError, BotoCoreError) as exc:
        return _json_response(502, {"error": f"AWS operation failed: {exc}"})
    except Exception as exc:
        return _json_response(500, {"error": f"Unhandled error: {exc}"})


if __name__ == "__main__":
    # Simple local sanity run
    mock_event = {
        "body": json.dumps(
            {
                "MODEL_NUMER": "123456",
                "DATA_SOURCE": "VT",
                "URL_TXT": "https://example.com/urls.txt",
            }
        )
    }
    print(handler(mock_event, context=None))
