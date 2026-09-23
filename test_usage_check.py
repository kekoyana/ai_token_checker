import json
import re
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from unittest.mock import patch

from usage_check import (
    ANSI_RESET,
    COPILOT_USAGE_URL,
    GROK_SUBSCRIPTIONS_URL,
    agy_usage,
    display_width,
    pace_severity,
    percent_severity,
    capacity_text,
    claude_windows,
    copilot_usage,
    copilot_windows,
    estimated_left_text,
    flatten_agy,
    grok_billing_windows,
    grok_percent,
    grok_plan_from_tier,
    grok_usage,
    pace_text,
    print_table,
    reset_text,
)


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
        self.assertEqual(capacity_text("grok", "supergrok_heavy"), "SuperGrok Heavy")
        self.assertEqual(capacity_text("grok", "x_basic"), "X Basic")

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

    def test_claude_windows_include_model_scoped_limits(self):
        raw = {
            "five_hour": {"utilization": 16.0, "resets_at": "2026-09-02T06:29:59+00:00"},
            "seven_day": {"utilization": 2.0, "resets_at": "2026-09-07T13:59:59+00:00"},
            "seven_day_opus": None,
            "seven_day_sonnet": None,
            "limits": [
                {"kind": "session", "group": "session", "percent": 16, "resets_at": "2026-09-02T06:29:59+00:00", "scope": None},
                {"kind": "weekly_all", "group": "weekly", "percent": 2, "resets_at": "2026-09-07T13:59:59+00:00", "scope": None},
                {
                    "kind": "weekly_scoped", "group": "weekly", "percent": 3,
                    "resets_at": "2026-09-07T13:59:59+00:00",
                    "scope": {"model": {"id": None, "display_name": "Fable"}, "surface": None},
                },
            ],
        }
        windows = claude_windows(raw)
        self.assertEqual([window["name"] for window in windows], ["5時間", "7日", "7日 Fable"])
        fable = windows[-1]
        self.assertEqual(fable["used_percent"], 3.0)
        self.assertEqual(fable["remaining_percent"], 97.0)
        self.assertEqual(fable["window_minutes"], 10080)
        self.assertEqual(fable["resets_at"], "2026-09-07T13:59:59+00:00")

    def test_claude_windows_skip_duplicate_scoped_limits(self):
        raw = {
            "seven_day_opus": {"utilization": 40.0, "resets_at": None},
            "limits": [
                {"kind": "weekly_scoped", "group": "weekly", "percent": 40, "scope": {"model": {"display_name": "Opus"}}},
                {"kind": "weekly_scoped", "group": "weekly", "percent": None, "scope": {"model": {"display_name": "Fable"}}},
            ],
        }
        self.assertEqual([window["name"] for window in claude_windows(raw)], ["7日 Opus"])

    def test_scoped_fable_window_falls_back_to_generic_points(self):
        self.assertEqual(estimated_left_text("claude", "max_5x", 97.0, "7日 Fable"), ("約485pt (非常に多)", 485.0))
        self.assertEqual(estimated_left_text("claude", "max_5x", 100.0, "7日 Opus"), ("約250pt (多)", 250.0))
        self.assertEqual(estimated_left_text("claude", "max_5x", 100.0, "7日 Sonnet"), ("約420pt (非常に多)", 420.0))

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
        self.assertEqual(result["windows"][0]["name"], "Gemini (共通枠)")

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

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_models_without_remaining_percentage_are_kept(self, _which, run):
        """Gemini系はremainingPercentageを返さない場合がある。枠ごと消えると枯渇に気付けない。"""
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "models": [
                {"label": "Claude Opus 4.6", "remainingPercentage": 1, "resetTime": "2026-08-30T18:28:41Z"},
                {"label": "Gemini 3.1 Pro (High)", "resetTime": "2026-09-02T03:40:23Z"},
            ]
        })
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        names = [w["name"] for w in result["windows"]]
        self.assertIn("Gemini (共通枠)", names)
        gemini = next(w for w in result["windows"] if w["name"] == "Gemini (共通枠)")
        self.assertIsNone(gemini["remaining_percent"])
        self.assertEqual(gemini["resets_at"], "2026-09-02T03:40:23Z")
        # 5hウィンドウ前提のペース計算を62hの枠に適用しない
        self.assertIsNone(gemini["window_minutes"])

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_exhausted_model_is_zero_percent(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "models": [{"label": "Gemini 3.7 Flash", "isExhausted": True, "resetTime": "2026-09-02T03:40:23Z"}]
        })
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(result["windows"][0]["remaining_percent"], 0.0)

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_model_without_quota_or_reset_is_skipped(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "models": [
                {"label": "Useless"},
                {"label": "Gemini 3 Flash", "resetTime": "2026-09-02T03:40:23Z"},
            ]
        })
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        self.assertEqual([w["name"] for w in result["windows"]], ["Gemini (共通枠)"])

    @patch("usage_check.subprocess.run")
    @patch("usage_check.shutil.which", return_value="/usr/local/bin/antigravity-usage")
    def test_multiple_gemini_models_are_consolidated(self, _which, run):
        run.return_value.returncode = 0
        run.return_value.stdout = json.dumps({
            "models": [
                {"label": "Claude Opus 4.6 (Thinking)", "remainingPercentage": 1.0, "resetTime": "2026-09-03T06:42:38Z"},
                {"label": "Gemini 2.5 Pro", "modelId": "gemini-2.5-pro", "remainingPercentage": 0.95, "resetTime": "2026-09-03T06:41:42Z"},
                {"label": "Gemini 3 Flash", "modelId": "gemini-3-flash", "remainingPercentage": 0.95, "resetTime": "2026-09-03T06:41:42Z"},
                {"label": "Gemini 3.8 Flash (Medium)", "modelId": "gemini-3.8-flash-medium", "remainingPercentage": 0.95, "resetTime": "2026-09-03T06:41:42Z"},
                {"label": "GPT-OSS 120B (Medium)", "modelId": "gpt-oss-120b-medium", "remainingPercentage": 1.0, "resetTime": "2026-09-03T06:42:38Z"},
            ]
        })
        run.return_value.stderr = ""

        result = agy_usage()

        self.assertTrue(result["ok"])
        windows = result["windows"]
        self.assertEqual(len(windows), 3)
        self.assertEqual(windows[0]["name"], "Claude Opus 4.6 (Thinking)")
        self.assertEqual(windows[1]["name"], "Gemini (共通枠)")
        self.assertEqual(windows[1]["remaining_percent"], 95.0)
        self.assertEqual(windows[1]["resets_at"], "2026-09-03T06:41:42Z")
        self.assertEqual(windows[2]["name"], "GPT-OSS 120B (Medium)")

    def test_print_table_renders_unknown_remaining(self):
        """None行でTypeErrorを出さず、リセット時刻を見せる。"""
        results = [{
            "service": "agy",
            "ok": True,
            "plan": "AI Pro",
            "windows": [
                {"name": "Gemini 3.1 Pro (High)", "remaining_percent": None,
                 "resets_at": "2026-09-02T03:40:23Z", "window_minutes": None},
            ],
        }]
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_table(results)
        output = buffer.getvalue()
        self.assertIn("Gemini 3.1 Pro (High)", output)
        self.assertIn("不明", output)
        self.assertNotIn("100.0%", output)

    def test_pace_text_unknown_when_remaining_is_none(self):
        row = {"name": "Gemini", "remaining_percent": None,
               "resets_at": "2026-09-02T03:40:23Z", "window_minutes": None}
        self.assertEqual(pace_text(row), "不明")

    def test_low_remaining_is_not_labelled_as_early_measurement(self):
        """残り6.2%の枠がペース推定で安心ラベル扱いされないこと。"""
        now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)  # JST 21:00
        row = {"name": "gemini-3.7-flash-tiered", "remaining_percent": 6.2,
               "resets_at": "2026-09-02T03:40:23Z", "window_minutes": 300}
        self.assertEqual(pace_text(row, now), "枯渇寸前")

    def test_remaining_under_quarter_is_flagged(self):
        now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        row = {"remaining_percent": 22.0, "resets_at": "2026-09-02T03:40:23Z", "window_minutes": 300}
        self.assertEqual(pace_text(row, now), "残りわずか")

    def test_window_minutes_inconsistent_with_reset_is_unknown(self):
        """5hウィンドウ想定で62h先のリセットはペース推定に使えない。"""
        now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        row = {"remaining_percent": 80.0, "resets_at": "2026-09-02T03:40:23Z", "window_minutes": 300}
        self.assertEqual(pace_text(row, now), "不明")

    def test_normal_five_hour_window_still_evaluated(self):
        now = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
        row = {"remaining_percent": 100.0, "resets_at": "2026-08-30T16:00:00Z", "window_minutes": 300}
        self.assertEqual(pace_text(row, now), "余裕あり")


class CopilotUsageTests(unittest.TestCase):
    def credit_payload(self, remaining=5824.6):
        return {
            "copilot_plan": "individual_pro",
            "access_type_sku": "plus_monthly_subscriber_quota",
            "token_based_billing": True,
            "quota_reset_date_utc": "2026-10-01T00:00:00Z",
            "quota_snapshots": {
                "chat": {"unlimited": True},
                "completions": {"unlimited": True},
                "premium_interactions": {
                    "unlimited": False,
                    "has_quota": True,
                    "token_based_billing": True,
                    "entitlement": 7000,
                    "quota_remaining": remaining,
                    "remaining": int(remaining),
                    "percent_remaining": 83.2,
                    "timestamp_utc": "2026-09-23T05:21:52Z",
                },
            },
        }

    def test_credit_balance_retains_fraction_and_detects_small_changes(self):
        before = copilot_windows(self.credit_payload())[0]
        after = copilot_windows(self.credit_payload(5824.2))[0]

        self.assertEqual(before["name"], "AI credits")
        self.assertEqual(before["remaining"], 5824.6)
        self.assertEqual(before["entitlement"], 7000)
        self.assertEqual(before["unit"], "credits")
        self.assertEqual(before["snapshot_at"], "2026-09-23T05:21:52Z")
        self.assertAlmostEqual(before["remaining_percent"], 5824.6 / 7000 * 100)
        self.assertLess(after["remaining_percent"], before["remaining_percent"])
        outputs = []
        for window in (before, after):
            output = StringIO()
            with redirect_stdout(output):
                print_table([{"service": "copilot", "ok": True, "plan": "pro_plus", "windows": [window]}], use_color=False)
            outputs.append(output.getvalue())
        self.assertIn("5,824.6 / 7,000.0 cr", outputs[0])
        self.assertIn("5,824.2 / 7,000.0 cr", outputs[1])
        self.assertIn("83.21%", outputs[0])
        self.assertIn("Pro+", outputs[0])
        lines = [line for line in outputs[0].splitlines() if line.startswith(("┌", "│", "├", "└"))]
        self.assertEqual(len({display_width(line) for line in lines}), 1)

    def test_credit_billing_flag_can_come_from_either_level(self):
        for level in ("account", "snapshot"):
            with self.subTest(level=level):
                raw = self.credit_payload()
                if level == "account":
                    del raw["quota_snapshots"]["premium_interactions"]["token_based_billing"]
                else:
                    del raw["token_based_billing"]
                self.assertEqual(copilot_windows(raw)[0]["name"], "AI credits")

    def test_credit_remaining_falls_back_to_integer_or_reported_percent(self):
        for invalid in (None, "invalid", float("nan"), float("inf")):
            with self.subTest(invalid=invalid):
                raw = self.credit_payload()
                item = raw["quota_snapshots"]["premium_interactions"]
                item["quota_remaining"] = invalid
                window = copilot_windows(raw)[0]
                self.assertEqual(window["remaining"], 5824)
                del item["remaining"]
                window = copilot_windows(raw)[0]
                self.assertEqual(window["remaining_percent"], 83.2)
                self.assertNotIn("remaining", window)

    def test_empty_credit_quota_is_unknown_not_full(self):
        for change in ({"entitlement": 0}, {"has_quota": False}):
            with self.subTest(change=change):
                raw = self.credit_payload()
                raw["quota_snapshots"]["premium_interactions"].update(change)
                window = copilot_windows(raw)[0]
                self.assertIsNone(window["remaining_percent"])
                self.assertIsNone(window["used_percent"])
                self.assertNotIn("remaining", window)

    def test_zero_credit_balance_overrides_stale_percent(self):
        window = copilot_windows(self.credit_payload(0))[0]
        self.assertEqual(window["remaining"], 0)
        self.assertEqual(window["remaining_percent"], 0)
        self.assertEqual(window["used_percent"], 100)

    def test_completions_are_not_credit_billed(self):
        raw = self.credit_payload()
        raw["quota_snapshots"]["completions"] = {
            "unlimited": False,
            "token_based_billing": True,
            "entitlement": 2000,
            "remaining": 1500,
        }
        window = copilot_windows(raw)[1]
        self.assertEqual(window["name"], "Completions")
        self.assertEqual(window["remaining_percent"], 75)
        self.assertNotIn("unit", window)

    def test_windows_include_finite_quotas_and_skip_unlimited(self):
        raw = {
            "quota_reset_date_utc": "2026-10-01T00:00:00Z",
            "quota_snapshots": {
                "chat": {"unlimited": True, "percent_remaining": 100},
                "completions": {"unlimited": False, "entitlement": 50, "remaining": 25},
                "premium_interactions": {
                    "unlimited": False,
                    "entitlement": 300,
                    "remaining": 120,
                    "percent_remaining": 40,
                },
            },
        }

        windows = copilot_windows(raw)

        self.assertEqual([window["name"] for window in windows], ["Premium requests", "Completions"])
        self.assertEqual(windows[0]["remaining_percent"], 40.0)
        self.assertEqual(windows[0]["resets_at"], "2026-10-01T00:00:00Z")
        self.assertEqual(windows[0]["window_minutes"], 43200)
        self.assertEqual(windows[1]["remaining_percent"], 50.0)

    def test_zero_remaining_is_preserved(self):
        raw = {
            "quota_snapshots": {
                "premium_interactions": {
                    "unlimited": False,
                    "entitlement": 300,
                    "remaining": 0,
                },
            },
        }
        self.assertEqual(copilot_windows(raw)[0]["remaining_percent"], 0.0)

    @patch("usage_check.copilot_access_token", return_value="token")
    @patch("usage_check.urllib.request.urlopen")
    def test_usage_reports_plan_and_windows(self, urlopen, _token):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = StringIO(json.dumps({
            "copilot_plan": "individual_pro",
            "quota_reset_date_utc": "2026-10-01T00:00:00Z",
            "quota_snapshots": {
                "premium_interactions": {"percent_remaining": 99.6, "unlimited": False},
            },
        }))
        urlopen.return_value = response

        result = copilot_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(result["plan"], "individual_pro")
        self.assertEqual(result["windows"][0]["remaining_percent"], 99.6)
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, COPILOT_USAGE_URL)
        self.assertEqual(request.get_header("Authorization"), "Bearer token")

    @patch("usage_check.copilot_access_token", return_value="token")
    @patch("usage_check.urllib.request.urlopen")
    def test_usage_distinguishes_pro_plus_from_generic_individual_plan(self, urlopen, _token):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value = StringIO(json.dumps(self.credit_payload()))
        urlopen.return_value = response

        result = copilot_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(capacity_text("copilot", result["plan"]), "Pro+")
        self.assertEqual(result["windows"][0]["remaining"], 5824.6)


class GrokUsageTests(unittest.TestCase):
    def test_percent_accepts_fraction_and_whole(self):
        self.assertEqual(grok_percent({"val": 0.25}), 25.0)
        self.assertEqual(grok_percent(42), 42.0)
        self.assertIsNone(grok_percent(None))

    def test_plan_tier_prefix_is_stripped(self):
        self.assertEqual(grok_plan_from_tier("SUBSCRIPTION_TIER_SUPER_GROK_HEAVY"), "super_grok_heavy")
        self.assertIsNone(grok_plan_from_tier(None))

    def test_billing_windows_from_credits_and_on_demand(self):
        credits = {
            "creditUsagePercent": {"val": 0.25},
            "currentPeriod": {
                "type": "BILLING_PERIOD_TYPE_MONTHLY",
                "start": "2026-07-01T00:00:00Z",
                "end": "2026-08-01T00:00:00Z",
            },
            "onDemandCap": {"val": 100},
            "onDemandUsed": {"val": 20},
        }

        windows = grok_billing_windows(credits, {})

        self.assertEqual([w["name"] for w in windows], ["月間", "従量"])
        self.assertEqual(windows[0]["remaining_percent"], 75.0)
        self.assertEqual(windows[0]["window_minutes"], 44640)
        self.assertEqual(windows[1]["remaining_percent"], 80.0)

    def test_dollar_limits_are_used_when_credits_missing(self):
        dollars = {
            "monthlyLimit": {"val": 200},
            "used": {"val": 50},
            "billingPeriodEnd": "2026-08-01T00:00:00Z",
        }

        windows = grok_billing_windows({}, dollars)

        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["name"], "月間")
        self.assertEqual(windows[0]["remaining_percent"], 75.0)

    @patch("usage_check.grok_access_token", return_value=("token", None))
    def test_usage_reports_plan_from_subscriptions(self, _token):
        def fake_request(url, _token_value, query=None):
            if url == GROK_SUBSCRIPTIONS_URL:
                return {"subscriptions": [{"status": "ACTIVE", "tier": "SUBSCRIPTION_TIER_SUPERGROK"}]}
            if query:
                return {"config": {"creditUsagePercent": {"val": 0.1}}}
            return {}

        with patch("usage_check.grok_request_json", side_effect=fake_request):
            result = grok_usage()

        self.assertTrue(result["ok"])
        self.assertEqual(result["plan"], "supergrok")
        self.assertEqual(result["windows"][0]["remaining_percent"], 90.0)

    @patch("usage_check.grok_access_token", side_effect=RuntimeError("GrokのOAuth認証情報が見つかりません"))
    def test_missing_credentials_are_reported(self, _token):
        result = grok_usage()

        self.assertFalse(result["ok"])
        self.assertEqual(result["service"], "grok")
        self.assertIn("GrokのOAuth認証情報が見つかりません", result["error"])


class TableRenderingTests(unittest.TestCase):
    def test_full_width_characters_count_as_two_columns(self):
        self.assertEqual(display_width("5時間"), 5)
        self.assertEqual(display_width("Max 5x"), 6)

    def test_rows_with_japanese_stay_aligned(self):
        results = [{
            "service": "claude",
            "ok": True,
            "plan": "max_5x",
            "windows": [
                {"name": "5時間", "remaining_percent": 64.0, "window_minutes": 300},
                {"name": "7日 Fable", "remaining_percent": 96.0, "window_minutes": 10080},
            ],
        }]
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_table(results)
        lines = [line for line in buffer.getvalue().splitlines() if line.startswith(("┌", "│", "├", "└"))]
        widths = {display_width(line) for line in lines}
        self.assertEqual(len(widths), 1, f"罫線幅が揃っていない: {sorted(widths)}")

    def test_long_error_is_clipped_in_table_and_shown_in_full_below(self):
        message = "GrokのOAuth認証情報が見つかりません（grok loginを実行してください）"
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_table([{"service": "grok", "ok": False, "error": message}])
        output = buffer.getvalue()
        self.assertIn("…", output)
        self.assertIn(f"grok: {message}", output)
        table_lines = [line for line in output.splitlines() if line.startswith("│")]
        self.assertTrue(all(display_width(line) < 100 for line in table_lines))


class ColorTests(unittest.TestCase):
    RED = "\033[91m"
    YELLOW = "\033[93m"

    def render(self, windows, use_color=True, service="agy", plan="AI Pro"):
        buffer = StringIO()
        with redirect_stdout(buffer):
            print_table([{"service": service, "ok": True, "plan": plan, "windows": windows}], use_color=use_color)
        return buffer.getvalue()

    def test_severity_thresholds(self):
        self.assertEqual(percent_severity(8.3), "red")
        self.assertEqual(percent_severity(10.0), "red")
        self.assertEqual(percent_severity(12.8), "yellow")
        self.assertEqual(percent_severity(25.0), "yellow")
        self.assertIsNone(percent_severity(25.1))
        self.assertIsNone(percent_severity(None))

    def test_pace_severity_is_independent_of_remaining(self):
        self.assertEqual(pace_severity("枯渇寸前"), "red")
        self.assertEqual(pace_severity("枯渇懸念"), "yellow")
        self.assertIsNone(pace_severity("余裕あり"))

    def test_low_remaining_is_red_and_warning_is_yellow(self):
        output = self.render([
            {"name": "Gemini (共通枠)", "remaining_percent": 8.3, "window_minutes": None},
            {"name": "Claude Opus 4.6", "remaining_percent": 12.8, "window_minutes": None},
        ])
        self.assertIn(f"{self.RED}  8.3%{ANSI_RESET}", output)
        self.assertIn(f"{self.YELLOW} 12.8%{ANSI_RESET}", output)

    def test_ample_remaining_is_not_colored(self):
        output = self.render([{"name": "7日", "remaining_percent": 94.0, "window_minutes": None}])
        self.assertNotIn("\033[", output)

    def test_pace_warning_does_not_colour_remaining(self):
        """残量83%の行はREMAINを塗らず、速い消費ペースだけをPACE列で警告する。"""
        reset = (datetime.now().astimezone() + timedelta(days=6)).isoformat()
        output = self.render(
            [{"name": "7日", "remaining_percent": 83.0, "window_minutes": 10080, "resets_at": reset}],
            service="claude", plan="max_5x",
        )
        self.assertNotIn(f"{self.YELLOW} 83.0%", output)
        self.assertRegex(output, r"\033\[93m(やや速い|枯渇懸念)")

    def test_colors_are_off_when_disabled(self):
        output = self.render([{"name": "Gemini (共通枠)", "remaining_percent": 8.3}], use_color=False)
        self.assertNotIn("\033[", output)

    def test_colored_rows_stay_aligned(self):
        output = self.render([
            {"name": "Gemini (共通枠)", "remaining_percent": 8.3, "window_minutes": None},
            {"name": "Claude Opus 4.6 (Thinking)", "remaining_percent": 88.0, "window_minutes": None},
        ])
        plain = re.sub(r"\033\[[0-9;]*m", "", output)
        lines = [line for line in plain.splitlines() if line.startswith(("┌", "│", "├", "└"))]
        self.assertEqual(len({display_width(line) for line in lines}), 1)


if __name__ == "__main__":
    unittest.main()
