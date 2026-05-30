# ai-urlmodel-secure-orchestrator

`ai-urlmodel-secure-orchestrator` is a secure AI-supported API orchestration project for URL model scanning workflows on AWS.

It provides a reference structure for:
- receiving scan requests through API Gateway
- orchestrating scanning with a trained Machine Learning model on a worker (for example EC2 via SSM)
- storing results in S3
- analyzing results and generating summaries/charts with AI Model(supported by AWS Bedrock): claude / Nova
- preparing outputs for dashboard/reporting use supported by AI Model (supported by AWS Bedrock): claude / Nova

## What This Project Does

- Exposes a REST-style scan entrypoint.
- Validates input fields such as `MODEL_VERSION`, `DATA_SOURCE`, and URL text payload.
- Submits scanning work to backend execution (containerized URL model).
- Writes scan artifacts (CSV/charts) to storage.
- Produces concise, defensive-oriented summaries for reporting.

## Project Structure

```text
ai-urlmodel-secure-orchestrator/
├── README.md
├── LICENSE
├── .gitignore
├── src/
│   ├── __init__.py
│   ├── app.py
│   └── schemas.py
├── tests/
│   └── test_schemas.py
└── docs/
    ├── architecture.md
    ├── api.md
    ├── design.md
    └── dataflow.md
```

## How to Use

### 1) Clone and enter project

```bash
git clone https://github.com/juanchencs/ai-urlmodel-secure-orchestrator.git
cd ai-urlmodel-secure-orchestrator
```

### 2) Create Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
```

### 3) Run local schema validation demo

```bash
python src/app.py
```

### 4) Run tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

## Examples

### Example request payload

```json
{
  "MODEL_VERSION": "20250301",
  "DATA_SOURCE": "VT",
  "URL_TXT": "https://example.com\nhttps://example.org"
}
```

### Example validation output

```text
Payload accepted.
Model version: 20250301
Data source: VT
URL count: 2
```

## Documentation

- Architecture: `docs/architecture.md`
- API contract: `docs/api.md`
- Design details: `docs/design.md`
- End-to-end dataflow: `docs/dataflow.md`

