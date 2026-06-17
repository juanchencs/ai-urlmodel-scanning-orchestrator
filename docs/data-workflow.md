# Data Workflow

This diagram focuses on how **data** is transformed and moved through the
pipeline, from the raw URL list to the final Microsoft Teams report. It is
written in Mermaid and renders as a colored diagram on GitHub.

Shapes:
- Rounded boxes = data artifacts (files, payloads, objects)
- Rectangles = processing steps
- Cylinders = persistent storage

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

    S1[("S3<br/>example-bucket/mlmodels/urlmodel")]:::store
    D5(["presigned download URL"]):::payload
    P4["Download CSV<br/>local copy on caller"]:::process

    P5["Load into DataFrame<br/>ai_analysis_report.py"]:::process
    D6(["Metrics<br/>total, flagged>=30,<br/>mean score, keyword counts"]):::data
    P6["Render charts (matplotlib)"]:::process
    D7(["chart_score.png<br/>chart_length.png<br/>chart_keywords.png"]):::data

    P7["Bedrock Model A/B<br/>aggregate-metrics prompt"]:::ai
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

## Stage-by-Stage

1. **Raw input**: `urltest.txt` holds one URL per line.
2. **Request payload**: packaged into JSON with `MODEL_VERSION`, `DATA_SOURCE`, `URL_TXT`.
3. **Orchestration**: API Gateway + Lambda validate and embed the URL text
   (base64) into an SSM shell script.
4. **Scan**: the worker recreates `urltest.txt`, runs the model container, and
   produces a CSV with columns like `url`, `sha256`, and `scoreNNN`.
5. **Persistence**: CSV is uploaded to S3; a presigned URL is returned.
6. **Local load**: the caller downloads the CSV and loads it into a DataFrame.
7. **Metrics**: totals, flagged count (`score >= 30`), mean score, and keyword
   frequencies are computed.
8. **Charts**: three PNG charts are rendered.
9. **AI summary**: Bedrock (Model A/B) produces up to 4 bullet points from the
   aggregate metrics only.
10. **Report delivery**: charts are uploaded to S3, an Adaptive Card is built
    (summary + chart URLs), and posted to the Microsoft Teams channel.

## Color Legend

- Blue: raw input
- Yellow: payloads / transport artifacts
- Green: processing steps
- Purple: derived data artifacts
- Indigo: AI (Bedrock) steps and outputs
- Orange: S3 storage
- Cyan: final Teams output
