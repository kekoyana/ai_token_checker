import json
import unittest
from unittest.mock import patch

from usage_check import agy_usage, flatten_agy, reset_text


class FormattingTests(unittest.TestCase):
    def test_flatten_remaining(self):
        data = {"models": [{"name": "Gemini", "remainingPercent": 62.5, "resetsAt": 100}]}
        self.assertEqual(flatten_agy(data), [("models/Gemini", 62.5, 100)])

    def test_flatten_used(self):
        data = {"weekly": {"usedPercent": 12}}
        self.assertEqual(flatten_agy(data), [("weekly", 88.0, None)])

    def test_unknown_reset(self):
        self.assertEqual(reset_text("quota available"), "quota available")


class AgyUsageTests(unittest.TestCase):
    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", side_effect=[None, "/usr/local/bin/agy-usage"])
    def test_legacy_quota_summary_error_is_reported(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = '{"quota_summary_error":"No Antigravity OAuth token"}'
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertFalse(result["ok"])
        self.assertEqual(result["service"], "agy")
        self.assertIn("No Antigravity OAuth token", result["error"])

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_modern_cli_models_are_converted_to_percent(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "models": [{
                "modelId": "gemini-3.5-flash",
                "label": "Gemini 3.5 Flash",
                "remainingPercentage": 0.625,
                "resetTime": "2026-07-16T06:10:00Z",
            }]
        })
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(result["windows"][0]["remaining_percent"], 62.5)
        self.assertEqual(result["windows"][0]["name"], "Gemini 3.5 Flash")

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_identical_model_windows_are_deduplicated(self, _which, run):
        model = {
            "label": "Gemini 3.1 Pro (High)",
            "remainingPercentage": 0.999,
            "resetTime": "2026-07-16T06:49:00Z",
        }
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({"models": [model, {**model, "modelId": "alias"}]})
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(len(result["windows"]), 1)


if __name__ == "__main__":
    unittest.main()
