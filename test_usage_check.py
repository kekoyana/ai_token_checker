import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from unittest.mock import patch

from usage_check import agy_usage, capacity_text, estimated_left_text, flatten_agy, pace_text, print_table, reset_text


class FormattingTests(unittest.TestCase):
    def test_flatten_remaining(self):
        data = {"models": [{"name": "Gemini", "remainingPercent": 62.5, "resetsAt": 100}]}
        self.assertEqual(flatten_agy(data), [("models/Gemini", 62.5, 100)])

    def test_flatten_used(self):
        data = {"weekly": {"usedPercent": 12}}
        self.assertEqual(flatten_agy(data), [("weekly", 88.0, None)])

    def test_unknown_reset(self):
        self.assertEqual(reset_text("quota available"), "quota available")

    def test_capacity_classes(self):
        self.assertEqual(capacity_text("claude", "max_20x"), "Max 20x")
        self.assertEqual(capacity_text("claude", "max_5x"), "Max 5x")
        self.assertEqual(capacity_text("claude", "pro"), "Pro 1x")
        self.assertEqual(capacity_text("agy", "ultra"), "Ultra (倍率不明)")
        self.assertEqual(capacity_text("agy", "AI Pro"), "AI Pro")
        self.assertEqual(capacity_text("codex", "plus"), "Plus")
        self.assertEqual(capacity_text("codex", None), "不明")

    def test_cross_service_estimated_ranking_is_printed(self):
        results = [
            {"service": "codex", "ok": True, "plan": "plus", "windows": [{"name": "primary", "remaining_percent": 92.0}]},
            {"service": "claude", "ok": True, "plan": "max_5x", "windows": [{"name": "7日", "remaining_percent": 62.0}]},
        ]
        output = StringIO()
        with redirect_stdout(output):
            print_table(results)
        self.assertIn("概算残量順位: claude (415pt) > codex (92pt)", output.getvalue())
        self.assertIn("8.0%", output.getvalue())

    def test_estimated_left_uses_rough_plan_points(self):
        self.assertEqual(estimated_left_text("claude", "max_5x", 100.0, "5時間"), ("約125pt (中)", 125.0))
        self.assertEqual(estimated_left_text("claude", "max_5x", 62.0, "7日"), ("約415pt (非常に多)", 415.4))
        self.assertEqual(estimated_left_text("agy", "AI Pro", 100.0), ("約100pt (中)", 100.0))

    def test_full_window_without_reset_is_marked_full(self):
        self.assertEqual(pace_text({"remaining_percent": 100.0, "resets_at": None, "window_minutes": 300}), "満タン")

    def test_pace_projects_usage_to_reset(self):
        now = datetime(2026, 7, 16, tzinfo=timezone.utc)
        row = {"remaining_percent": 62.0, "resets_at": "2026-07-21T00:00:00Z", "window_minutes": 10080}
        self.assertEqual(pace_text(row, now), "枯渇懸念")


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
