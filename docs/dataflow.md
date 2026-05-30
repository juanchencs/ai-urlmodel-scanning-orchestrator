# Dataflow

## End-to-End Flow

1. Client sends `POST /scan` with model version, source, and URL text.
2. API layer validates payload and authorization.
3. Orchestrator submits scan job to worker runtime.
4. Worker starts model container and performs URL scan.
5. Worker writes CSV output and uploads to S3.
6. Orchestrator returns job metadata and artifact link.
7. Analysis/report process reads CSV, computes metrics, builds charts, and generates summary.
8. Final step: charts are uploaded to S3 and the AI-supported report (summary + charts) is posted to a Microsoft Teams channel via an Incoming Webhook.

## Sequence (Text)

```text
Client -> API Gateway -> Lambda Orchestrator
Lambda Orchestrator -> Worker Runtime (SSM/ECS)
Worker Runtime -> Scanner Container
Scanner Container -> S3 (CSV output)
Client/Reporter -> S3 (read output) -> Charts + Summary
Reporter -> S3 (upload charts) -> Microsoft Teams (Adaptive Card)
```

## Failure Paths

- Validation failure at ingress: reject with `400`.
- Worker start failure: return `500` with reason.
- Artifact upload failure: mark job failed and alert.
- Analysis failure: keep raw CSV as source-of-truth artifact.
- Teams delivery failure: report is still available in S3; retry the webhook post.

