import base64
import json
import os
import random
import re
import time
import uuid
import boto3

ssm = boto3.client("ssm")
s3 = boto3.client("s3")

MODEL_RE = re.compile(r"^\d{6,12}$")
DATASOURCE_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

def _resp(code, body):
    return {"statusCode": code, "headers": {"Content-Type": "application/json"}, "body": json.dumps(body)}

def _parse(event):
    body = event.get("body", "{}")
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    payload = json.loads(body) if isinstance(body, str) else body

    model = str(payload.get("MODEL_VERSION") or payload.get("MODEL_NUMER") or "").strip()
    ds = str(payload.get("DATA_SOURCE") or "").strip()
    url_txt = str(payload.get("URL_TXT") or "").strip()   # newline-separated urls content

    if not MODEL_RE.match(model):
        raise ValueError("MODEL_VERSION/MODEL_NUMER invalid")
    if not DATASOURCE_RE.match(ds):
        raise ValueError("DATA_SOURCE invalid")
    if not url_txt:
        raise ValueError("URL_TXT is empty")
    return model, ds, url_txt

def _run_ssm(instance_id, model_version, data_source, url_txt, output_file):
    bucket = os.environ["BUCKET"]
    prefix = os.environ["PREFIX"].strip("/")
    scan_script = os.environ["SCAN_SCRIPT_PATH"]

    # safe embed
    txt_b64 = base64.b64encode(url_txt.encode("utf-8")).decode("utf-8")

    cmd = f"""#!/bin/bash
set -euo pipefail

MODEL_VERSION="{model_version}"
DATA_SOURCE="{data_source}"
OUTPUT_FILE="{output_file}"
BUCKET="{bucket}"
PREFIX="{prefix}"
SCAN_SCRIPT="{scan_script}"
TXT_B64="{txt_b64}"

WORKDIR="/tmp/urlmodel_${{MODEL_VERSION}}_$$"
mkdir -p "$WORKDIR"
cd "$WORKDIR"

python3 - <<'PY'
import base64, os
txt = base64.b64decode(os.environ["TXT_B64"]).decode("utf-8")
with open("urltest.txt", "w", encoding="utf-8") as f:
    f.write(txt)
PY

pick_name_port() {{
  for p in $(seq 8700 8999); do
    name="urlmodel$((p-8700))"
    if ! docker ps -a --format '{{{{.Names}}}}' | grep -qx "$name"; then
      if ! ss -ltn "( sport = :$p )" | grep -q ":$p"; then
        echo "$name $p"; return 0
      fi
    fi
  done
  return 1
}}

read NAME PORT < <(pick_name_port)
IMAGE="scr.sophos.com/spoke/sai-url:model-version-${{MODEL_VERSION}}"

docker run -d --name "$NAME" -p 127.0.0.1:${{PORT}}:8080 -e WORKERS=1 -e THREADS=0 -e SYSTEM=internal "$IMAGE"

cleanup() {{
  docker stop "$NAME" >/dev/null 2>&1 || true
  docker rm "$NAME" >/dev/null 2>&1 || true
}}
trap cleanup EXIT

python3 - <<'PY'
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("scan_urls", "{scan_script}")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

with open("urltest.txt", "r", encoding="utf-8") as f:
    url_list = [x.strip() for x in f if x.strip()]

mod.scan_single_urls_list(url_list, "{model_version}", int("${{PORT}}"), outputfile="{output_file}")
PY

aws s3 cp "{output_file}" "s3://{bucket}/{prefix}/{output_file}"
"""

    r = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": [cmd]},
        CloudWatchOutputConfig={"CloudWatchOutputEnabled": True},
    )
    return r["Command"]["CommandId"]

def _wait(instance_id, cmd_id, timeout_sec=1800):
    start = time.time()
    while time.time() - start < timeout_sec:
        out = ssm.get_command_invocation(CommandId=cmd_id, InstanceId=instance_id)
        st = out["Status"]
        if st in ("Success", "Failed", "Cancelled", "TimedOut", "Undeliverable", "Terminated"):
            return out
        time.sleep(8)
    raise TimeoutError("SSM command timeout")

def lambda_handler(event, context):
    try:
        model, ds, url_txt = _parse(event)
        rnd = random.randint(0, 99)
        output_file = f"{ds}_{model}_{rnd}.csv"

        cmd_id = _run_ssm(
            instance_id=os.environ["WORKER_INSTANCE_ID"],
            model_version=model,
            data_source=ds,
            url_txt=url_txt,
            output_file=output_file,
        )
        result = _wait(os.environ["WORKER_INSTANCE_ID"], cmd_id)
        if result["Status"] != "Success":
            return _resp(500, {"error": "scan failed", "status": result["Status"], "stderr": result.get("StandardErrorContent", "")[:2000]})

        key = f"{os.environ['PREFIX'].strip('/')}/{output_file}"
        url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": os.environ["BUCKET"], "Key": key},
            ExpiresIn=3600,
        )
        return _resp(200, {"output_file": output_file, "s3_key": key, "download_url": url})
    except Exception as e:
        return _resp(400, {"error": str(e)})
