# ai-urlmodel-secure-orchestrator

`ai-urlmodel-secure-orchestrator` is a secure **AI-supported** API orchestration project for URL model scanning workflows on AWS.

It provides a reference structure for:
- receiving scan requests through API Gateway
- orchestrating scanning with a trained machine-learning model on a worker (for example EC2 via SSM or ECS)
- storing results in S3
- analyzing results and generating summaries/charts with Bedrock-supported AI models (for example Nova or Claude)
- preparing outputs for dashboard/reporting use
- delivering the AI-supported report to a Microsoft Teams channel

## What This Project Does

- Exposes a REST-style scan entrypoint.
- Validates input fields such as `MODEL_VERSION`, `DATA_SOURCE`, and URL text payload.
- Submits scanning work to backend execution (containerized URL model).
- Writes scan artifacts (CSV/charts) to storage.
- Produces concise, defensive-oriented summaries for reporting.
- Sends the final AI-supported report (summary + charts) to Microsoft Teams.

## System Architecture

```mermaid
flowchart TB
    classDef client fill:#dbeafe,stroke:#1e3a8a,stroke-width:2px,color:#0f172a;
    classDef api fill:#fef9c3,stroke:#a16207,stroke-width:2px,color:#0f172a;
    classDef compute fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#0f172a;
    classDef worker fill:#fae8ff,stroke:#86198f,stroke-width:2px,color:#0f172a;
    classDef storage fill:#ffedd5,stroke:#9a3412,stroke-width:2px,color:#0f172a;
    classDef ai fill:#e0e7ff,stroke:#3730a3,stroke-width:2px,color:#0f172a;
    classDef report fill:#cffafe,stroke:#155e75,stroke-width:2px,color:#0f172a;
    classDef security fill:#fee2e2,stroke:#991b1b,stroke-width:2px,color:#0f172a;

    subgraph CALLER["Caller environment (Account AA / EC2 A)"]
        A1["Client / EC2 A<br/>src/fetch_scan_results.py"]:::client
        A2["AI analysis + charts<br/>src/ai_analysis_report.py"]:::ai
        A3["Teams reporter<br/>src/send_teams_report.py"]:::report
    end

    subgraph EDGE["API edge"]
        G1["API Gateway (REST)<br/>POST /scan"]:::api
        SEC["IAM auth / resource policy<br/>(AWS_IAM, VPC endpoint)"]:::security
    end

    subgraph ORCH["Orchestration (Account BB)"]
        L1["Lambda<br/>lambda_function.py / api_handler.py"]:::compute
        SSM["SSM Run Command"]:::compute
    end

    subgraph WORK["Scan worker (Account BB)"]
        W1["EC2 worker (jane-ec2)"]:::worker
        W2["Docker container<br/>sai-url:model-version-NNN<br/>port 8700+"]:::worker
        W3["scan_urls.py<br/>scan_single_urls_list()"]:::worker
    end

    subgraph DATA["Storage & AI (Account BB)"]
        S3["S3 bucket<br/>lrs-jane-s3/mlmodels/urlmodel"]:::storage
        BR["Amazon Bedrock<br/>Nova / Claude (Converse)"]:::ai
    end

    TEAMS["Microsoft Teams channel<br/>Incoming Webhook (Adaptive Card)"]:::report

    A1 -->|"POST MODEL_VERSION,<br/>DATA_SOURCE, URL_TXT"| G1
    G1 --> SEC
    SEC --> L1
    L1 -->|"SendCommand"| SSM
    SSM -->|"shell script"| W1
    W1 -->|"docker run"| W2
    W2 --> W3
    W3 -->|"results CSV"| W1
    W1 -->|"aws s3 cp"| S3
    L1 -->|"presigned URL +<br/>job metadata"| G1
    G1 -->|"download_url, s3_key"| A1

    A1 -->|"GET presigned URL"| S3
    S3 -->|"output CSV"| A2
    A2 -->|"aggregate metrics prompt"| BR
    BR -->|"summary bullets"| A2
    A2 -->|"summary + chart paths"| A3
    A3 -->|"upload charts"| S3
    A3 -->|"Adaptive Card<br/>(summary + chart URLs)"| TEAMS
```

A full-page version with a color legend is in `docs/architecture-diagram.md`.

## Data Workflow

```mermaid
flowchart TB
    classDef input fill:#dbeafe,stroke:#1e3a8a,stroke-width:2px,color:#0f172a;
    classDef process fill:#dcfce7,stroke:#166534,stroke-width:2px,color:#0f172a;
    classDef payload fill:#fef9c3,stroke:#a16207,stroke-width:2px,color:#0f172a;
    classDef data fill:#fae8ff,stroke:#86198f,stroke-width:2px,color:#0f172a;
    classDef store fill:#ffedd5,stroke:#9a3412,stroke-width:2px,color:#0f172a;
    classDef ai fill:#e0e7ff,stroke:#3730a3,stroke-width:2px,color:#0f172a;
    classDef output fill:#cffafe,stroke:#155e75,stroke-width:2px,color:#0f172a;

    D1(["urltest.txt<br/>(raw URL list)"]):::input
    P1["Build request payload<br/>fetch_scan_results.py"]:::process
    D2(["JSON payload<br/>MODEL_VERSION, DATA_SOURCE, URL_TXT"]):::payload

    P2["API Gateway + Lambda<br/>validate + orchestrate"]:::process
    D3(["base64 URL_TXT<br/>embedded in SSM script"]):::payload
    P3["Worker writes urltest.txt<br/>then runs model scan"]:::process
    D4(["scan output CSV<br/>url, sha256, scoreNNN"]):::data

    S1[("S3<br/>lrs-jane-s3/mlmodels/urlmodel")]:::store
    D5(["presigned download URL"]):::payload
    P4["Download CSV<br/>local copy on caller"]:::process

    P5["Load into DataFrame<br/>ai_analysis_report.py"]:::process
    D6(["Metrics<br/>total, flagged>=30,<br/>mean score, keyword counts"]):::data
    P6["Render charts (matplotlib)"]:::process
    D7(["chart_score.png<br/>chart_length.png<br/>chart_keywords.png"]):::data

    P7["Bedrock Nova/Claude<br/>aggregate-metrics prompt"]:::ai
    D8(["Summary bullets<br/>(<= 4)"]):::ai

    P8["Upload charts + build<br/>Adaptive Card"]:::process
    S2[("S3<br/>.../reports")]:::store
    D9(["Adaptive Card<br/>summary + chart URLs"]):::payload
    OUT(["Microsoft Teams channel"]):::output

    D1 --> P1 --> D2 --> P2 --> D3 --> P3 --> D4
    D4 -->|aws s3 cp| S1
    S1 --> D5 --> P4 --> P5 --> D6 --> P6 --> D7
    D6 --> P7 --> D8
    D7 --> P8
    D8 --> P8
    P8 -->|upload charts| S2
    P8 --> D9 --> OUT
```

A stage-by-stage explanation with a color legend is in `docs/data-workflow.md`.

## Project Structure

```text
ai-urlmodel-secure-orchestrator/
├── README.md
├── LICENSE
├── .gitignore
├── requirements.txt
├── api_handler.py
├── ecs_runner.py
├── lambda_function.py
├── src/
│   ├── __init__.py
│   ├── app.py
│   ├── fetch_scan_results.py
│   ├── ai_analysis_report.py
│   ├── send_teams_report.py
│   └── schemas.py
├── tests/
│   └── test_schemas.py
└── docs/
    ├── architecture.md
    ├── architecture-diagram.md
    ├── api.md
    ├── design.md
    ├── dataflow.md
    ├── data-workflow.md
    ├── webconsole-deployment.md
    └── teams-reporting.md
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
pip install -r requirements.txt
```

### 3) Run local schema validation demo

```bash
python src/app.py
```

### 4) Run tests

```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 5) Fetch scan result CSV (split from old test_io flow)

```bash
python src/fetch_scan_results.py \
  --api-url "https://fi0d5laq4a.execute-api.eu-west-2.amazonaws.com/prod/scan" \
  --model-version "20250301" \
  --data-source "VT" \
  --url-file "urltest.txt"
```

### 6) Generate AI-assisted analysis + charts from CSV

```bash
python src/ai_analysis_report.py \
  --csv-file "VT_20250301_63.csv" \
  --region "eu-west-2" \
  --nova-model-id "amazon.nova-lite-v1:0" \
  --output-dir "."
```

### 7) Send the AI-supported report to Microsoft Teams (final step)

Deliver as part of the analysis step by adding `--teams-webhook`:

```bash
python src/ai_analysis_report.py \
  --csv-file "VT_20250301_63.csv" \
  --region "eu-west-2" \
  --nova-model-id "amazon.nova-lite-v1:0" \
  --output-dir "." \
  --teams-webhook "https://prod-XXX.logic.azure.com:443/workflows/.../invoke?..."
```

Or run the Teams delivery on its own from an existing summary and charts:

```bash
python src/send_teams_report.py \
  --webhook-url "https://prod-XXX.logic.azure.com:443/workflows/.../invoke?..." \
  --summary-file "summary.txt" \
  --bucket "lrs-jane-s3" \
  --prefix "mlmodels/urlmodel/reports"
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
- Architecture diagram (colored): `docs/architecture-diagram.md`
- API contract: `docs/api.md`
- Design details: `docs/design.md`
- End-to-end dataflow: `docs/dataflow.md`
- Data workflow diagram (colored): `docs/data-workflow.md`
- Web Console deployment (IAM role, Lambda, API Gateway, policies): `docs/webconsole-deployment.md`
- Microsoft Teams reporting (final step): `docs/teams-reporting.md`
