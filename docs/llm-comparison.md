# LLM Comparison: Nova Lite vs Claude Opus

The reporting step uses a Bedrock-hosted LLM to turn aggregate scan metrics into a
human-readable summary. Below is a side-by-side comparison of two models run on the
**same input** (7 URLs, 3 flagged, mean risk score ~38.3, no phishing keywords detected).

## Input Metrics (identical for both models)

| Metric | Value |
|---|---|
| Total URLs monitored | 7 |
| Flagged URLs | 3 (≈43%) |
| Average risk score | 38.3 / 100 |
| Phishing keywords detected | None (e.g. login, password, payment, bank) |

## Model Output: `amazon.nova-lite-v1:0`

- **Total URLs Monitored:** 7
- **Flagged URLs:** 3 (42.86%)
- **Average Risk Score:** 38.29
- **Keyword Frequency:** No high-risk keywords detected (e.g., "login", "password", "payment")

## Model Output: `anthropic.claude-opus-4-6-v1`

- **Flagged URL Rate:** 3 of 7 monitored URLs (43%) were flagged as potentially suspicious, indicating a notable proportion warranting further review.
- **Average Risk Score:** The mean risk score across all URLs is 38.3 out of 100, suggesting a moderate overall threat level in the current batch.
- **Keyword Indicators:** No common phishing/social-engineering keywords (e.g., "login," "password," "payment," "bank") were detected, suggesting flagged URLs may rely on other deceptive techniques.
- **Recommendation:** Investigate the 3 flagged URLs manually to determine root cause of elevated scores despite absence of typical phishing keywords; consider updating detection heuristics accordingly.

## Side-by-Side Analysis

| Dimension | Nova Lite (`nova-lite-v1:0`) | Claude Opus (`claude-opus-4-6-v1`) |
|---|---|---|
| Style | Concise, metric-first | Narrative, analytical |
| Numeric fidelity | Exact (42.86%, 38.29) | Rounded for readability (43%, 38.3) |
| Interpretation | States facts only | Adds context (e.g. "moderate threat level") |
| Actionability | None | Includes an explicit recommendation |
| Insight depth | Surface-level | Infers "other deceptive techniques" |
| Verbosity | Low (4 short bullets) | Higher (full sentences) |
| Best for | Dashboards, at-a-glance KPIs | Analyst triage, decision support |

## Takeaways

- **Nova Lite** is faster and cheaper, and is ideal when the audience just needs the
  raw numbers in a compact card (e.g. an executive Teams dashboard).
- **Claude Opus** produces richer, decision-oriented narrative — it interprets the
  numbers and recommends next actions, which is more useful for security analysts.
- Both models agreed on the underlying facts; they differ mainly in **tone, depth,
  and actionability** rather than accuracy.
- A practical pattern: use **Nova Lite** for routine/high-volume runs and switch to
  **Claude Opus** when a flagged batch needs deeper human-facing analysis.
