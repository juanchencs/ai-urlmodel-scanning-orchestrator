# Dataflow

## End-to-End Flow

1. Client sends `POST /scan` with model version, source, and URL text.
2. API layer validates payload and authorization.
3. Orchestrator submits scan job to worker runtime.
4. Worker starts model container and performs URL scan.
5. Worker writes CSV output and uploads to S3.
6. Orchestrator returns job metadata and artifact link.
7. Analysis/report process reads CSV, computes metrics, builds charts, and generates summary.

## Sequence (Text)

```text
Client -> API Gateway -> Lambda Orchestrator
Lambda Orchestrator -> Worker Runtime (SSM/ECS)
Worker Runtime -> Scanner Container
Scanner Container -> S3 (CSV output)
Client/Reporter -> S3 (read output) -> Charts + Summary
```

## Failure Paths

- Validation failure at ingress: reject with `400`.
- Worker start failure: return `500` with reason.
- Artifact upload failure: mark job failed and alert.
- Analysis failure: keep raw CSV as source-of-truth artifact.

