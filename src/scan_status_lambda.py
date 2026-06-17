import json, os, time, boto3
from botocore.exceptions import ClientError

ssm = boto3.client("ssm", region_name="eu-west-2")
s3 = boto3.client("s3", region_name="eu-west-2")

INSTANCE_ID = os.environ["INSTANCE_ID"]
STATUS_BUCKET = os.environ["STATUS_BUCKET"]
STATUS_PREFIX = os.environ["STATUS_PREFIX"]

def resp(code, body):
    return {"statusCode": code, "body": json.dumps(body)}

def is_transient_ssm_error(exc: ClientError) -> bool:
    code = (exc.response or {}).get("Error", {}).get("Code", "")
    return code in {
        "InvocationDoesNotExist",
        "ThrottlingException",
        "InternalServerError",
        "ServiceUnavailableException",
    }

def read_status_file(job_id):
    key = f"{STATUS_PREFIX}{job_id}.json"
    try:
        obj = s3.get_object(Bucket=STATUS_BUCKET, Key=key)
        return json.loads(obj["Body"].read().decode("utf-8"))
    except ClientError as e:
        if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
            return None
        raise

def safe_get_command_invocation(command_id: str, instance_id: str):
    # Brief retry window for eventual consistency right after SendCommand.
    for attempt in range(3):
        try:
            return ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        except ClientError as e:
            if is_transient_ssm_error(e):
                time.sleep(1 + attempt)
                continue
            raise
    return None

def lambda_handler(event, context):
    try:
        qs = event.get("queryStringParameters") or {}
        job_id = qs.get("job_id")
        command_id = qs.get("command_id")
        if not job_id or not command_id:
            return resp(400, {"error": "missing job_id or command_id"})

        inv = safe_get_command_invocation(command_id, INSTANCE_ID)
        ssm_status = (inv or {}).get("Status", "Unknown")

        st = read_status_file(job_id)

        if st and st.get("status") in ("SUCCEEDED", "FAILED"):
            st["ssm_status"] = ssm_status
            return resp(200, st)

        if ssm_status in ("Failed", "Cancelled", "TimedOut"):
            return resp(200, {
                "job_id": job_id,
                "status": "FAILED",
                "ssm_status": ssm_status,
                "error": "SSM command failed before completion"
            })

        return resp(200, {
            "job_id": job_id,
            "status": "RUNNING",
            "ssm_status": ssm_status
        })

    except ClientError as e:
        # Treat temporary service-side errors as RUNNING to avoid noisy 500s.
        if is_transient_ssm_error(e):
            qs = event.get("queryStringParameters") or {}
            return resp(200, {
                "job_id": qs.get("job_id"),
                "status": "RUNNING",
                "ssm_status": "Unknown",
                "detail": "scan status not ready yet"
            })
        return resp(500, {"error": str(e)})
    except Exception as e:
        return resp(500, {"error": str(e)})