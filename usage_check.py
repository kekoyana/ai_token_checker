#!/usr/bin/env python3
"""Show remaining usage for Codex, Claude Code, Antigravity CLI, and Grok Build."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TIMEOUT = 20
LOCAL_CONFIG = ".usage_check.local.json"
GROK_AUTH_FILE = Path.home() / ".grok" / "auth.json"
GROK_BILLING_URL = "https://cli-chat-proxy.grok.com/v1/billing"
GROK_SUBSCRIPTIONS_URL = "https://grok.com/rest/subscriptions"
GROK_OIDC_TOKEN_URL = "https://auth.x.ai/oauth2/token"
GROK_DEFAULT_CLIENT_ID = "b1a00492-073a-47ea-816f-4c329264a828"

# Deliberately rough, cross-service capacity points. These are comparison aids,
# not vendor-published token or request limits.
CAPACITY_POINTS = {
    "codex": {"free": 20, "go": 50, "plus": 100, "pro": 1000, "business": 250, "enterprise": 1000, "edu": 250},
    "claude": {"free": 20, "pro": 100, "max_5x": 500, "max_20x": 2000, "team": 500, "enterprise": 1000},
    "agy": {"free": 20, "ai_pro": 100, "pro": 100, "ultra_5x": 500, "ultra_20x": 2000, "enterprise": 1000},
    "grok": {
        "free": 20,
        "x_basic": 20,
        "lite": 50,
        "supergrok_lite": 50,
        "supergrok": 100,
        "x_premium": 100,
        "x_premium_plus": 150,
        "heavy": 1000,
        "supergrok_heavy": 1000,
    },
}


def error(service: str, message: str) -> dict[str, Any]:
    return {"service": service, "ok": False, "error": message}


def rpc(proc: subprocess.Popen[str], request: dict[str, Any], wanted_id: int) -> dict[str, Any]:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    deadline = time.monotonic() + TIMEOUT
    while time.monotonic() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if message.get("id") == wanted_id:
            if "error" in message:
                raise RuntimeError(message["error"].get("message", str(message["error"])))
            return message.get("result", {})
    raise TimeoutError("Codex app-serverから応答がありません")


def codex_usage() -> dict[str, Any]:
    if not shutil.which("codex"):
        return error("codex", "codex CLIが見つかりません")
    proc: subprocess.Popen[str] | None = None
    try:
        proc = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        rpc(proc, {
            "method": "initialize", "id": 1,
            "params": {"clientInfo": {"name": "usage-check", "title": "Usage Check", "version": "0.1.0"}},
        }, 1)
        assert proc.stdin is not None
        proc.stdin.write(json.dumps({"method": "initialized", "params": {}}) + "\n")
        proc.stdin.flush()
        account = rpc(proc, {"method": "account/read", "id": 2, "params": {"refreshToken": False}}, 2)
        limits = rpc(proc, {"method": "account/rateLimits/read", "id": 3, "params": {}}, 3)
        raw = limits.get("rateLimits") or {}
        windows = []
        for name in ("primary", "secondary"):
            item = raw.get(name)
            if item:
                used = float(item.get("usedPercent", 0))
                windows.append({
                    "name": name,
                    "remaining_percent": max(0.0, 100.0 - used),
                    "used_percent": used,
                    "window_minutes": item.get("windowDurationMins"),
                    "resets_at": item.get("resetsAt"),
                })
        acct = account.get("account") or {}
        return {"service": "codex", "ok": True, "plan": acct.get("planType"), "windows": windows}
    except Exception as exc:
        detail = str(exc)
        if proc is not None and proc.poll() is not None and proc.stderr is not None:
            stderr = proc.stderr.read().strip()
            if stderr:
                detail = f"{detail}: {stderr.splitlines()[-1]}"
        return error("codex", detail)
    finally:
        if proc is not None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()


def claude_credentials() -> dict[str, Any]:
    token = os.environ.get("CLAUDE_ACCESS_TOKEN")
    if token:
        return {"accessToken": token}
    credential_file = Path.home() / ".claude" / ".credentials.json"
    if credential_file.exists():
        data = json.loads(credential_file.read_text())
        return data.get("claudeAiOauth", data)
    if sys.platform == "darwin" and shutil.which("security"):
        completed = subprocess.run(
            ["security", "find-generic-password", "-s", "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if completed.returncode == 0:
            data = json.loads(completed.stdout)
            return data.get("claudeAiOauth", data)
    raise RuntimeError("Claude CodeのOAuth認証情報が見つかりません（claude auth loginを実行してください）")


def claude_usage() -> dict[str, Any]:
    try:
        credentials = claude_credentials()
        token = credentials.get("accessToken")
        if not token:
            raise RuntimeError("Claude Codeのアクセストークンがありません")
        request = urllib.request.Request(
            "https://api.anthropic.com/api/oauth/usage",
            headers={"Authorization": f"Bearer {token}", "anthropic-beta": "oauth-2025-04-20"},
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            raw = json.load(response)
        windows = []
        labels = {"five_hour": "5時間", "seven_day": "7日", "seven_day_sonnet": "7日 Sonnet", "seven_day_opus": "7日 Opus"}
        for key, label in labels.items():
            item = raw.get(key)
            if not item:
                continue
            used = float(item.get("utilization", 0))
            duration = 300 if key == "five_hour" else 10080 if key.startswith("seven_day") else None
            windows.append({"name": label, "remaining_percent": max(0.0, 100.0 - used), "used_percent": used, "resets_at": item.get("resets_at"), "window_minutes": duration})
        plan_parts = [credentials.get("subscriptionType"), credentials.get("rateLimitTier")]
        plan = " ".join(str(part) for part in plan_parts if part)
        return {"service": "claude", "ok": True, "plan": plan, "windows": windows}
    except urllib.error.HTTPError as exc:
        return error("claude", f"APIエラー HTTP {exc.code}")
    except Exception as exc:
        return error("claude", str(exc))


def agy_usage() -> dict[str, Any]:
    modern_command = shutil.which("antigravity-usage")
    if modern_command:
        try:
            completed = subprocess.run(
                [modern_command, "quota", "--json"], capture_output=True, text=True, timeout=TIMEOUT
            )
            if completed.returncode != 0:
                raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "使用量の取得に失敗しました")
            raw = json.loads(completed.stdout)
            models = raw.get("models", []) if isinstance(raw, dict) else []
            windows = []
            seen_windows: set[tuple[str, Any, Any]] = set()
            for model in models:
                if not isinstance(model, dict):
                    continue
                raw_remaining = model.get("remainingPercentage")
                reset = model.get("resetTime")
                if raw_remaining is None and reset is None:
                    continue
                if model.get("isExhausted"):
                    remaining = 0.0
                elif raw_remaining is None:
                    # Gemini系はremainingPercentageを返さない。枠の存在とリセット時刻だけ載せる。
                    remaining = None
                else:
                    remaining = max(0.0, min(100.0, float(raw_remaining) * 100.0))
                name = model.get("label") or model.get("modelId") or model.get("id") or "model"
                identity = (str(name), remaining, reset)
                if identity not in seen_windows:
                    seen_windows.add(identity)
                    windows.append({
                        "name": name,
                        "remaining_percent": remaining,
                        "resets_at": reset,
                        "window_minutes": 300 if remaining is not None else None,
                    })
            if not windows:
                raise RuntimeError("使用枠のJSONにモデル情報がありません")
            return {"service": "agy", "ok": True, "plan": raw.get("planType"), "windows": windows}
        except Exception as exc:
            return error("agy", str(exc))

    command = shutil.which("agy-usage")
    if not command:
        return error("agy", "antigravity-usageが見つかりません（READMEのセットアップを実行してください）")
    try:
        completed = subprocess.run([command, "json"], capture_output=True, text=True, timeout=TIMEOUT)
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "agy-usageの実行に失敗しました")
        raw = json.loads(completed.stdout)
        quota_error = raw.get("quota_summary_error") if isinstance(raw, dict) else None
        if quota_error:
            raise RuntimeError(f"使用枠を取得できません: {quota_error}")
        return {"service": "agy", "ok": True, "data": raw}
    except Exception as exc:
        return error("agy", str(exc))


def grok_number(value: Any) -> float | None:
    """Extract a numeric field from Grok billing payloads (`{"val": n}` or bare number)."""
    if value is None:
        return None
    if isinstance(value, dict):
        if "val" in value and value["val"] is not None:
            return float(value["val"])
        if "value" in value and value["value"] is not None:
            return float(value["value"])
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def grok_percent(value: Any) -> float | None:
    """Normalize a percent-like value to 0–100.

    Grok sometimes returns fractions (0–1) and sometimes whole percents (0–100).
    Values above 1.5 are treated as already-scaled percents.
    """
    number = grok_number(value)
    if number is None:
        return None
    if 0.0 <= number <= 1.5:
        return max(0.0, min(100.0, number * 100.0))
    return max(0.0, min(100.0, number))


def grok_period_label(period: Any) -> str:
    if not isinstance(period, dict):
        return "クレジット"
    period_type = str(period.get("type") or "").upper()
    if "WEEKLY" in period_type:
        return "週間"
    if "MONTHLY" in period_type:
        return "月間"
    if "DAILY" in period_type:
        return "日次"
    return "クレジット"


def grok_period_minutes(period: Any, start: Any, end: Any) -> int | None:
    start_dt = parse_reset_datetime(start)
    end_dt = parse_reset_datetime(end)
    if start_dt is not None and end_dt is not None and end_dt > start_dt:
        return max(1, int((end_dt - start_dt).total_seconds() / 60))
    if isinstance(period, dict):
        period_type = str(period.get("type") or "").upper()
        if "WEEKLY" in period_type:
            return 10080
        if "MONTHLY" in period_type:
            return 43200
        if "DAILY" in period_type:
            return 1440
    return None


def grok_plan_from_tier(tier: Any) -> str | None:
    if not tier:
        return None
    text = str(tier).strip()
    if not text:
        return None
    normalized = text.upper().replace("-", "_").replace(" ", "_")
    if normalized.startswith("SUBSCRIPTION_TIER_"):
        normalized = normalized[len("SUBSCRIPTION_TIER_"):]
    return normalized.lower()


def grok_auth_entries() -> list[dict[str, Any]]:
    if not GROK_AUTH_FILE.exists():
        return []
    try:
        raw = json.loads(GROK_AUTH_FILE.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(raw, dict):
        return []
    entries: list[dict[str, Any]] = []
    for key, value in raw.items():
        if not isinstance(value, dict):
            continue
        entry = dict(value)
        entry.setdefault("_auth_key", key)
        entries.append(entry)
    return entries


def grok_pick_auth_entry() -> dict[str, Any]:
    entries = grok_auth_entries()
    if not entries:
        raise RuntimeError("GrokのOAuth認証情報が見つかりません（grok loginを実行してください）")

    def sort_key(entry: dict[str, Any]) -> tuple[int, float]:
        expires = parse_reset_datetime(entry.get("expires_at"))
        exp_ts = expires.timestamp() if expires is not None else 0.0
        has_token = 1 if entry.get("key") or entry.get("access_token") else 0
        return (has_token, exp_ts)

    return max(entries, key=sort_key)


def grok_token_expired(entry: dict[str, Any], skew_seconds: int = 120) -> bool:
    expires = parse_reset_datetime(entry.get("expires_at"))
    if expires is None:
        return False
    now = datetime.now(timezone.utc)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    return expires <= now + timedelta(seconds=skew_seconds)


def grok_refresh_access_token(entry: dict[str, Any]) -> str:
    refresh_token = entry.get("refresh_token")
    if not refresh_token:
        raise RuntimeError("Grokのリフレッシュトークンがありません（grok loginを実行してください）")
    client_id = entry.get("oidc_client_id") or GROK_DEFAULT_CLIENT_ID
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }).encode()
    request = urllib.request.Request(
        GROK_OIDC_TOKEN_URL,
        data=body,
        method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        payload = json.load(response)
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Grokのアクセストークン更新に失敗しました")
    # Keep the refreshed token in-memory only; never write secrets back to disk.
    entry["key"] = token
    expires_in = payload.get("expires_in")
    if isinstance(expires_in, (int, float)):
        entry["expires_at"] = (datetime.now(timezone.utc) + timedelta(seconds=float(expires_in))).isoformat()
    if payload.get("refresh_token"):
        entry["refresh_token"] = payload["refresh_token"]
    return str(token)


def grok_access_token() -> tuple[str, dict[str, Any] | None]:
    env_token = os.environ.get("GROK_ACCESS_TOKEN") or os.environ.get("XAI_ACCESS_TOKEN")
    if env_token:
        return env_token, None
    entry = grok_pick_auth_entry()
    token = entry.get("key") or entry.get("access_token")
    if token and not grok_token_expired(entry):
        return str(token), entry
    if entry.get("refresh_token"):
        return grok_refresh_access_token(entry), entry
    if token:
        return str(token), entry
    raise RuntimeError("Grokのアクセストークンがありません（grok loginを実行してください）")


def grok_request_json(url: str, token: str, query: dict[str, str] | None = None) -> dict[str, Any]:
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": "usage-check/0.1",
            "x-grok-client-mode": "cli",
            "x-grok-client-surface": "grok-build",
        },
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        raw = json.load(response)
    if not isinstance(raw, dict):
        raise RuntimeError("Grok APIの応答形式が不正です")
    return raw


def grok_billing_windows(credits_config: dict[str, Any], dollars_config: dict[str, Any]) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    period = credits_config.get("currentPeriod")
    period_end = None
    period_start = None
    if isinstance(period, dict):
        period_end = period.get("end") or credits_config.get("billingPeriodEnd")
        period_start = period.get("start") or credits_config.get("billingPeriodStart")
    else:
        period_end = credits_config.get("billingPeriodEnd") or dollars_config.get("billingPeriodEnd")
        period_start = credits_config.get("billingPeriodStart") or dollars_config.get("billingPeriodStart")
    period_minutes = grok_period_minutes(period, period_start, period_end)
    label = grok_period_label(period)

    used_percent = grok_percent(credits_config.get("creditUsagePercent"))
    if used_percent is None:
        monthly_limit = grok_number(dollars_config.get("monthlyLimit"))
        monthly_used = grok_number(dollars_config.get("used"))
        if monthly_limit is not None and monthly_limit > 0 and monthly_used is not None:
            used_percent = max(0.0, min(100.0, (monthly_used / monthly_limit) * 100.0))
            label = "月間"
            period_end = dollars_config.get("billingPeriodEnd") or period_end
            period_start = dollars_config.get("billingPeriodStart") or period_start
            period_minutes = grok_period_minutes(None, period_start, period_end) or 43200

    if used_percent is not None:
        windows.append({
            "name": label,
            "remaining_percent": max(0.0, 100.0 - used_percent),
            "used_percent": used_percent,
            "resets_at": period_end,
            "window_minutes": period_minutes,
        })

    on_demand_cap = grok_number(credits_config.get("onDemandCap"))
    if on_demand_cap is None:
        on_demand_cap = grok_number(dollars_config.get("onDemandCap"))
    on_demand_used = grok_number(credits_config.get("onDemandUsed"))
    if on_demand_used is None:
        on_demand_used = grok_number(dollars_config.get("onDemandUsed"))
    if on_demand_cap is not None and on_demand_cap > 0 and on_demand_used is not None:
        used = max(0.0, min(100.0, (on_demand_used / on_demand_cap) * 100.0))
        windows.append({
            "name": "従量",
            "remaining_percent": max(0.0, 100.0 - used),
            "used_percent": used,
            "resets_at": period_end or dollars_config.get("billingPeriodEnd"),
            "window_minutes": period_minutes or grok_period_minutes(None, dollars_config.get("billingPeriodStart"), dollars_config.get("billingPeriodEnd")),
        })

    return windows


def grok_subscription_plan(token: str) -> str | None:
    try:
        raw = grok_request_json(GROK_SUBSCRIPTIONS_URL, token)
    except Exception:
        return None
    subscriptions = raw.get("subscriptions")
    if not isinstance(subscriptions, list):
        return None
    for item in subscriptions:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").upper()
        if status and "ACTIVE" not in status and "TRIAL" not in status:
            continue
        plan = grok_plan_from_tier(item.get("tier"))
        if plan:
            return plan
    for item in subscriptions:
        if isinstance(item, dict):
            plan = grok_plan_from_tier(item.get("tier"))
            if plan:
                return plan
    return None


def grok_usage() -> dict[str, Any]:
    try:
        token, _entry = grok_access_token()

        def fetch_all(access_token: str) -> tuple[dict[str, Any], dict[str, Any], str | None]:
            credits = grok_request_json(GROK_BILLING_URL, access_token, {"format": "credits"})
            try:
                dollars = grok_request_json(GROK_BILLING_URL, access_token)
            except Exception:
                dollars = {}
            plan = grok_subscription_plan(access_token)
            return credits, dollars, plan

        try:
            credits_raw, dollars_raw, plan = fetch_all(token)
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise
            # Access token may be stale even if expires_at still looks valid.
            entry = _entry or grok_pick_auth_entry()
            token = grok_refresh_access_token(entry)
            credits_raw, dollars_raw, plan = fetch_all(token)

        credits_config = credits_raw.get("config") if isinstance(credits_raw.get("config"), dict) else credits_raw
        dollars_config = dollars_raw.get("config") if isinstance(dollars_raw.get("config"), dict) else dollars_raw
        if not isinstance(credits_config, dict):
            credits_config = {}
        if not isinstance(dollars_config, dict):
            dollars_config = {}

        plan = plan or grok_plan_from_tier(credits_config.get("subscription_tier") or dollars_config.get("subscription_tier"))
        windows = grok_billing_windows(credits_config, dollars_config)
        return {"service": "grok", "ok": True, "plan": plan, "windows": windows}
    except urllib.error.HTTPError as exc:
        return error("grok", f"APIエラー HTTP {exc.code}")
    except Exception as exc:
        return error("grok", str(exc))


def reset_text(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone().strftime("%m/%d %H:%M")
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().strftime("%m/%d %H:%M")
    except ValueError:
        return str(value)


def flatten_agy(value: Any, path: str = "") -> list[tuple[str, float, Any]]:
    found: list[tuple[str, float, Any]] = []
    if isinstance(value, dict):
        remaining = value.get("remaining_percent", value.get("remainingPercent"))
        used = value.get("used_percent", value.get("usedPercent"))
        if remaining is not None or used is not None:
            pct = float(remaining if remaining is not None else 100.0 - float(used))
            reset = value.get("resets_at", value.get("resetsAt", value.get("reset_time")))
            found.append((path or "quota", pct, reset))
        for key, child in value.items():
            if isinstance(child, (dict, list)):
                found.extend(flatten_agy(child, f"{path}/{key}".strip("/")))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            label = child.get("name", child.get("model", str(index))) if isinstance(child, dict) else str(index)
            found.extend(flatten_agy(child, f"{path}/{label}".strip("/")))
    return found


def capacity_text(service: str, plan: Any) -> str:
    """Return the most specific safe plan/capacity label available."""
    if not plan:
        return "不明"
    normalized = str(plan).lower().replace("-", "_").replace(" ", "_")
    if service == "claude":
        if "20x" in normalized:
            return "Max 20x"
        if "5x" in normalized:
            return "Max 5x"
        if "pro" in normalized:
            return "Pro 1x"
        if "free" in normalized:
            return "Free"
        if "team" in normalized:
            return "Team"
        if "enterprise" in normalized:
            return "Enterprise"
        if "max" in normalized:
            return "Max (倍率不明)"
    elif service == "agy":
        if "20x" in normalized or "ultra_200" in normalized:
            return "Ultra 20x"
        if "5x" in normalized or "ultra_100" in normalized:
            return "Ultra 5x"
        if "ai_pro" in normalized:
            return "AI Pro"
        if "pro" in normalized:
            return "Pro 1x"
        if "free" in normalized:
            return "Free"
        if "ultra" in normalized:
            return "Ultra (倍率不明)"
        if "enterprise" in normalized:
            return "Enterprise"
    elif service == "codex":
        if "enterprise" in normalized:
            return "Enterprise"
        if "business" in normalized or "team" in normalized:
            return "Business"
        if "pro" in normalized:
            return "Pro"
        if "plus" in normalized:
            return "Plus"
        if "go" in normalized:
            return "Go"
        if "free" in normalized:
            return "Free"
        if "edu" in normalized:
            return "Edu"
    elif service == "grok":
        if "heavy" in normalized:
            return "SuperGrok Heavy"
        if "lite" in normalized:
            return "SuperGrok Lite"
        if "supergrok" in normalized or normalized == "super":
            return "SuperGrok"
        if "premium_plus" in normalized or "x_premium_plus" in normalized:
            return "X Premium+"
        if "premium" in normalized:
            return "X Premium"
        if "basic" in normalized or "x_basic" in normalized:
            return "X Basic"
        if "free" in normalized:
            return "Free"
    return "不明"


def capacity_points(service: str, plan: Any) -> float:
    """Return deliberately rough full-quota points for cross-service comparison."""
    label = capacity_text(service, plan).lower().replace(" ", "_")
    aliases = {
        "pro_1x": "pro", "max_5x": "max_5x", "max_20x": "max_20x",
        "ultra_5x": "ultra_5x", "ultra_20x": "ultra_20x",
        "supergrok_heavy": "supergrok_heavy", "supergrok_lite": "supergrok_lite",
        "supergrok": "supergrok", "x_basic": "x_basic", "x_premium": "x_premium",
        "x_premium+": "x_premium_plus", "x_premium_plus": "x_premium_plus",
    }
    key = aliases.get(label, label)
    return float(CAPACITY_POINTS.get(service, {}).get(key, 100))


def claude_window_points(plan: Any, limit_name: str, remaining_percent: float) -> float | None:
    """Convert Anthropic's published prompt/hour ranges into rough common points."""
    label = capacity_text("claude", plan)
    five_hour = {"Pro 1x": (10, 40), "Max 5x": (50, 200), "Max 20x": (200, 800)}
    weekly_sonnet = {"Pro 1x": (40, 80), "Max 5x": (140, 280), "Max 20x": (240, 480)}
    weekly_opus = {"Max 5x": (15, 35), "Max 20x": (24, 40)}
    fraction = remaining_percent / 100.0

    def midpoint(values: tuple[int, int]) -> float:
        return (values[0] + values[1]) / 2.0

    if limit_name == "5時間" and label in five_hour:
        return midpoint(five_hour[label]) * fraction
    if limit_name.startswith("7日"):
        points = 0.0
        if "Opus" not in limit_name and label in weekly_sonnet:
            points += midpoint(weekly_sonnet[label]) * 2.0
        if "Sonnet" not in limit_name and label in weekly_opus:
            points += midpoint(weekly_opus[label]) * 10.0
        if points:
            return points * fraction
    return None


def estimated_left_text(service: str, plan: Any, remaining_percent: float, limit_name: str = "") -> tuple[str, float]:
    points = capacity_points(service, plan) * remaining_percent / 100.0
    if service == "claude":
        window_points = claude_window_points(plan, limit_name, remaining_percent)
        if window_points is not None:
            points = window_points
    if points < 20:
        grade = "ごく少"
    elif points < 60:
        grade = "少"
    elif points < 150:
        grade = "中"
    elif points < 400:
        grade = "多"
    else:
        grade = "非常に多"
    return f"約{points:.0f}pt ({grade})", points


def parse_reset_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value).astimezone()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone()
    except ValueError:
        return None


def pace_text(row: dict[str, Any], now: datetime | None = None) -> str:
    reset = parse_reset_datetime(row.get("resets_at"))
    duration = row.get("window_minutes")
    remaining = row.get("remaining_percent")
    if remaining is None:
        return "不明"
    remaining = float(remaining)
    if reset is None and remaining >= 99.9:
        return "満タン"
    # 残量が少ない事実はペース推定より優先する。ペース推定はウィンドウ長に
    # 依存するため、そこを誤ると残り数%の枠に安心ラベルが付いてしまう。
    if remaining <= 10.0:
        return "枯渇寸前"
    if remaining <= 25.0:
        return "残りわずか"
    if reset is None or not duration:
        return "不明"
    now = now or datetime.now().astimezone()
    total = timedelta(minutes=float(duration))
    time_left = reset - now
    if time_left.total_seconds() <= 0:
        return "更新待ち"
    if time_left > total * 2:
        # 想定ウィンドウ長を大きく超えるリセット = window_minutesが実態と合っていない
        # （取得タイミングによる誤差は許容するため2倍で判定）
        return "不明"
    elapsed_fraction = 1.0 - time_left / total
    used = 100.0 - remaining
    if used <= 0.1:
        return "余裕あり"
    projected_used = used / max(0.01, elapsed_fraction)
    if projected_used <= 70:
        return "余裕あり"
    if projected_used <= 100:
        return "持つ見込み"
    if projected_used <= 125:
        return "やや速い"
    return "枯渇懸念"


def load_local_config() -> dict[str, Any]:
    path = Path.cwd() / LOCAL_CONFIG
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def print_table(results: list[dict[str, Any]]) -> None:
    print(f"{'SERVICE':<9} {'LIMIT':<28} {'PLAN':<14} {'USED':>7} {'REMAIN':>8}  {'RESET':<12} {'PACE':<12} EST. LEFT")
    print("-" * 116)
    service_scores: dict[str, list[float]] = {}
    for result in results:
        if not result["ok"]:
            print(f"{result['service']:<9} {'ERROR':<28} {'-':<14} {'-':>7} {'-':>8}  {'-':<12} {'-':<12} {result['error']}")
            continue
        plan = capacity_text(result["service"], result.get("plan"))
        rows = result.get("windows", [])
        if result["service"] == "agy" and "data" in result:
            rows = [{"name": n, "remaining_percent": p, "resets_at": r} for n, p, r in flatten_agy(result["data"])]
        if not rows:
            print(f"{result['service']:<9} {'取得済み（表示可能な枠なし）':<28}")
        for row in rows:
            remaining = row.get("remaining_percent")
            if remaining is None:
                # 残量を返さない枠（Antigravity の Gemini 系）。枠の存在とリセット時刻は表示する。
                used_text, remaining_text, estimate = "-", "不明", "残量API未提供"
            else:
                used_text = f"{100.0 - remaining:.1f}%"
                remaining_text = f"{remaining:.1f}%"
                estimate, points = estimated_left_text(result["service"], result.get("plan"), remaining, str(row["name"]))
                service_scores.setdefault(result["service"], []).append(points)
            print(f"{result['service']:<9} {str(row['name']):<28.28} {plan:<14.14} {used_text:>7} {remaining_text:>8}  {reset_text(row.get('resets_at')):<12} {pace_text(row):<12} {estimate}")
    scores = {service: sum(values) / len(values) for service, values in service_scores.items() if values}
    if len(scores) > 1:
        ranking = " > ".join(f"{service} ({score:.0f}pt)" for service, score in sorted(scores.items(), key=lambda item: item[1], reverse=True))
        print(f"\n概算残量順位: {ranking}")
    print("※ Claudeは公表目安を5h=プロンプト中央値、週次=Sonnet 2pt/h・Opus 10pt/hで換算。順位は各枠平均の参考推定です。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex / Claude Code / agy / Grok の残り使用量を一覧表示")
    parser.add_argument("--json", action="store_true", help="機械可読なJSONを出力")
    parser.add_argument("--service", choices=("codex", "claude", "agy", "grok"), action="append", help="対象を限定（複数指定可）")
    args = parser.parse_args()
    selected = args.service or ["codex", "claude", "agy", "grok"]
    checkers = {"codex": codex_usage, "claude": claude_usage, "agy": agy_usage, "grok": grok_usage}
    results = [checkers[name]() for name in selected]
    plans = load_local_config().get("plans", {})
    if isinstance(plans, dict):
        for result in results:
            if result.get("ok") and plans.get(result["service"]):
                result["plan"] = plans[result["service"]]
    if args.json:
        print(json.dumps({"checked_at": datetime.now().astimezone().isoformat(), "services": results}, ensure_ascii=False, indent=2))
    else:
        print_table(results)
    return 0 if all(item["ok"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
