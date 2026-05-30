# AWS RestAPI GateWay Contract

## Endpoint

- **Method:** `POST`
- **Path:** `/scan`
- **Content-Type:** `application/json`

## Request Body

```json
{
  "MODEL_VERSION": "20250301",
  "DATA_SOURCE": "VT",
  "URL_TXT": "https://example.com\nhttps://example.org"
}
```

## Field Definitions

- `MODEL_VERSION` (string, required): 6-12 digits.
- `DATA_SOURCE` (string, required): 1-40 chars, `[A-Za-z0-9_-]`.
- `URL_TXT` (string, required): newline-separated URLs.

## Example Success Response

```json
{
  "status": "submitted",
  "command_id": "1234abcd-5678-ef90-1234-56789abcdef0",
  "output_file": "VT_20250301_63.csv",
  "s3_key": "mlmodels/urlmodel/VT_20250301_63.csv",
  "download_url": "https://...presigned..."
}
```

## Common Error Responses

- `400 Bad Request`: schema validation failure.
- `401/403`: authorization or resource policy denial.
- `500`: worker execution failure or downstream dependency error.

