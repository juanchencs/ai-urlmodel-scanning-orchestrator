# System Architecture Diagram

The diagram below shows the end-to-end flow of `ai-urlmodel-secure-orchestrator`,
from the API request through scanning, AI analysis, and Microsoft Teams delivery.

It is written in Mermaid, which renders as a colored diagram directly on GitHub.

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

## Legend

- Blue: caller/client components
- Indigo: AI components (Bedrock Nova/Claude + analysis)
- Yellow: API Gateway edge
- Red: security controls (IAM auth, resource policy, VPC endpoint)
- Green: orchestration (Lambda + SSM)
- Purple: scan worker (EC2 + Docker + scanner)
- Orange: S3 storage
- Cyan: Microsoft Teams reporting

## Notes

- The caller and backend may live in different AWS accounts (AA and BB); a
  shared IAM principal with access to S3, Lambda, and Bedrock in BB is used.
- The worker uses dynamic container name/port selection starting at `8700` to
  avoid conflicts.
- Charts are uploaded to S3 and referenced via presigned URLs because Microsoft
  Teams cannot render local files.
