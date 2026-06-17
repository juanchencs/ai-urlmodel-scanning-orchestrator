import json, os, uuid, boto3

ssm = boto3.client("ssm", region_name="eu-west-2")

INSTANCE_ID = os.environ["INSTANCE_ID"]
RUNNER_SCRIPT = os.environ["RUNNER_SCRIPT"]
OUTPUT_S3_PREFIX = os.environ["OUTPUT_S3_PREFIX"]
STATUS_S3_PREFIX = os.environ["STATUS_S3_PREFIX"]

def resp(code, body):
    return {"statusCode": code, "body": json.dumps(body)}

def lambda_handler(event, context):
    try:
        body = event.get("body") or "{}"
        if isinstance(body, str):
            body = json.loads(body)

        required = ["model_version", "data_source", "type", "flag", "input_s3_uri"]
        for k in required:
            if not body.get(k):
                return resp(400, {"error": f"missing {k}"})

        model_version = str(body["model_version"])
        data_source = body["data_source"]
        scan_type = body["type"]
        flag = body["flag"]
        input_s3_uri = body["input_s3_uri"]

        if scan_type not in ("url", "domain"):
            return resp(400, {"error": "type must be url/domain"})
        if flag not in ("mal", "clean", "unknown"):
            return resp(400, {"error": "flag must be mal/clean/unknown"})

        job_id = str(uuid.uuid4())

        cmd = (
            f"nohup {RUNNER_SCRIPT} "
            f"'{job_id}' '{model_version}' '{data_source}' '{scan_type}' '{flag}' "
            f"'{input_s3_uri}' '{OUTPUT_S3_PREFIX}' '{STATUS_S3_PREFIX}' "
            f"> /tmp/urlmodel_{job_id}.log 2>&1 &"
        )

        r = ssm.send_command(
            InstanceIds=[INSTANCE_ID],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [cmd]},
            TimeoutSeconds=3600,
            Comment=f"urlmodel scan {job_id}"
        )

        return resp(200, {
            "job_id": job_id,
            "command_id": r["Command"]["CommandId"],
            "status_s3_uri": f"{STATUS_S3_PREFIX}{job_id}.json",
            "status": "RUNNING"
        })

    except Exception as e:
        return resp(500, {"error": str(e)})