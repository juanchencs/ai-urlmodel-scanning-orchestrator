# Design Notes

## Goals

- Keep the API contract simple and explicit.
- Decouple request acceptance from long-running scan execution.
- Enable secure deployment in enterprise AWS environments.
- Keep analysis/report formatting extensible.

## Key Design Choices

1. **Asynchronous orchestration response**
   - API returns quickly with job metadata and output location.
   - Prevents timeout issues on long-running scans.

2. **Strict payload schema validation**
   - Reject malformed requests early.
   - Improves reliability and observability.

3. **Dedicated artifact prefixing**
   - Output key structure supports retention and auditing.
   - Easier lifecycle and policy management in S3.

4. **Defensive summary prompts**
   - Uses aggregate metrics for safe reporting.
   - Avoids exposing raw sensitive URL content.

## Extensibility

- Add job status endpoint (`GET /scan/{command_id}`)
- Add persistence layer for job history
- Add multi-tenant routing by source/account
- Add richer chart/report templates

