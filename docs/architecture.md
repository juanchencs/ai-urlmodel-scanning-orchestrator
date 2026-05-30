# Architecture

## Overview

This project is designed as an API-driven orchestration layer for URL model scanning.

Primary components:
- API Layer (API Gateway + Lambda handler)
- Orchestration Layer (SSM/ECS workflow trigger)
- Compute Layer (containerized scanner workers)
- Storage Layer (S3 for CSV and chart artifacts)
- Analysis Layer (summary + chart generation)

## Logical Components

1. **Request Ingress**
   - Receives input payload (`MODEL_VERSION`, `DATA_SOURCE`, `URL_TXT`)
   - Performs schema and security validation

2. **Job Orchestrator**
   - Starts scan execution on worker infrastructure
   - Tracks command/task state
   - Handles retries and terminal failures

3. **Scanner Worker**
   - Runs model image `scr.sophos.com/spoke/sai-url:model-version-{MODEL_VERSION}`
   - Produces output CSV

4. **Artifact & Reporting**
   - Uploads outputs to S3
   - Generates summary and charts for dashboard/report usage

## Security Boundaries

- Prefer private API endpoint + VPC endpoint restrictions
- Use IAM authorization for API method invocation
- Constrain worker IAM role to least privilege
- Store results in scoped S3 prefixes

