"""Unit tests for request schema validation."""

import unittest

from src.schemas import parse_scan_request


class TestSchemas(unittest.TestCase):
    def test_valid_payload(self) -> None:
        payload = {
            "MODEL_VERSION": "20250301",
            "DATA_SOURCE": "VT",
            "URL_TXT": "https://example.com",
        }
        req = parse_scan_request(payload)
        self.assertEqual(req.model_version, "20250301")

    def test_invalid_model(self) -> None:
        payload = {
            "MODEL_VERSION": "20x50301",
            "DATA_SOURCE": "VT",
            "URL_TXT": "https://example.com",
        }
        with self.assertRaises(ValueError):
            parse_scan_request(payload)


if __name__ == "__main__":
    unittest.main()

