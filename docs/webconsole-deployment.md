# Web Console Deployment Guide

This guide shows core steps to deploy the AI powered URL model orchestrator using AWS Web Console.

Region used in this guide: `eu-west-2`.

## 1) Create IAM role for Lambda

### 1.1 Open IAM role creation

1. Go to **IAM** -> **Roles** -> **Create role**.
2. Trusted entity type: **AWS service**.
3. Use case: **Lambda**.
4. Click **Next**.

### 1.2 Attach baseline policy

Attach managed policy:

- `AWSLambdaBasicExecutionRole`

Click **Next**.

### 1.3 Name the role

Set role name:

- `lambda-urlmodel-orchestrator-role`

Create role.

### 1.4 Add custom inline policy

Open the new role:

1. **Add permissions** -> **Create inline policy**.
2. Choose **JSON** tab.
3. Paste policy below (adjust account/region/resource IDs if needed):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SsmInvoke",
      "Effect": "Allow",
      "Action": [
        "ssm:SendCommand",
        "ssm:GetCommandInvocation"
      ],
      "Resource": "*"
    },
    {
      "Sid": "Ec2Describe",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeInstances"
      ],
      "Resource": "*"
    },
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::lrs-jane-s3",
        "arn:aws:s3:::lrs-jane-s3/*"
      ]
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "*"
    }
  ]
}
```

1. Review and create inline policy with name:

- `urlmodel-orchestrator-inline-policy`

## 2) Create Lambda function

1. Go to **Lambda** -> **Create function**.
2. Choose **Author from scratch**.
3. Function name:

- `urlmodel-api-handler`

1. Runtime:

- `Python 3.12`

1. Execution role:

- **Use an existing role**
- Select `lambda-urlmodel-orchestrator-role`

1. Create function.

### 2.1 Configure Lambda environment variables

In Lambda function:

1. Open **Configuration** -> **Environment variables**.
2. Add:
  - `WORKER_INSTANCE_ID` = `<jane-ec2-instance-id>`
  - `BUCKET` = `lrs-jane-s3`
  - `PREFIX` = `mlmodels/urlmodel`
  - `SCAN_SCRIPT_PATH` = `/home/ubuntu/efs/urlmodel/scan_urls.py`
3. Save.

Do not add reserved key `AWS_REGION` as custom env var.

### 2.2 Upload handler code

1. In **Code** tab, upload or paste your `lambda_function.py`.
2. Set handler name to:

- `lambda_function.lambda_handler`

1. Deploy.

## 3) Ensure worker EC2 prerequisites

On worker EC2 (`jane-ec2`), ensure:

- SSM Agent installed and online.
- Instance profile allows SSM command execution.
- Docker installed and usable.
- `scan_urls.py` exists at `/home/ubuntu/efs/urlmodel/scan_urls.py`.
- Instance can pull image:
  - `scr.sophos.com/spoke/sai-url:model-version-{MODEL_VERSION}`

## 4) Create REST API Gateway

1. Go to **API Gateway** -> **Create API**.
2. Choose **REST API** (Regional).
3. API name:

- `urlmodel-scan-api`

1. Create API.

### 4.1 Create resource and method

1. Under **Resources**, create resource:
  - Resource path: `/scan`
2. Select `/scan` -> **Create method** -> `POST`.
3. Integration type:
  - **Lambda function**
4. Enable:
  - **Lambda proxy integration**
5. Lambda region: `eu-west-2`
6. Lambda function: `urlmodel-api-handler`
7. Save and grant permission when prompted.

### 4.2 Deploy API

1. **Actions** -> **Deploy API**.
2. Stage:
  - `prod`
3. Deploy.
4. Note invoke URL:
  - `https://<api-id>.execute-api.eu-west-2.amazonaws.com/prod/scan`

## 5) API method auth and security (recommended)

For stronger security:

1. In method request, set Authorization to `AWS_IAM`.
2. Add API resource policy to restrict source VPC endpoint or principal.
3. Optionally add WAF and usage plan throttling.

## 6) Example API invocation payload

```json
{
  "MODEL_VERSION": "20250301",
  "DATA_SOURCE": "VT",
  "URL_TXT": "https://example.com\nhttps://example.org"
}
```

## 7) Troubleshooting checklist

- `403 Missing Authentication Token`:
  - wrong resource path or method not deployed.
- `403 Permission denied`:
  - IAM/resource policy mismatch or wrong principal.
- `500 scan failed`:
  - inspect SSM command logs and Lambda CloudWatch logs.
- `Invalid username or token` on GitHub operations:
  - use PAT/SSH setup for correct account.

