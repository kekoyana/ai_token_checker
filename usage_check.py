#!/usr/bin/env python3
"""Show remaining usage for Codex, Claude Code, and Antigravity CLI."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


TIMEOUT = 20
LOCAL_CONFIG = ".usage_check.local.json"

# Deliberately rough, cross-service capacity points. These are comparison aids,
# not vendor-published token or request limits.
CAPACITY_POINTS = {
    "codex": {"free": 20, "go": 50, "plus": 100, "pro": 1000, "business": 250, "enterprise": 1000, "edu": 250},
    "claude": {"free": 20, "pro": 100, "max_5x": 500, "max_20x": 2000, "team": 500, "enterprise": 1000},
    "agy": {"free": 20, "ai_pro": 100, "pro": 100, "ultra_5x": 500, "ultra_20x": 2000, "enterprise": 1000},
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
            seen_windows: set[tuple[str, float, Any]] = set()
            for model in models:
                if not isinstance(model, dict) or model.get("remainingPercentage") is None:
                    continue
                remaining = float(model["remainingPercentage"]) * 100.0
                name = model.get("label") or model.get("modelId") or model.get("id") or "model"
                remaining = max(0.0, min(100.0, remaining))
                reset = model.get("resetTime")
                identity = (str(name), remaining, reset)
                if identity not in seen_windows:
                    seen_windows.add(identity)
                    windows.append({"name": name, "remaining_percent": remaining, "resets_at": reset, "window_minutes": 300})
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
    return "不明"


def capacity_points(service: str, plan: Any) -> float:
    """Return deliberately rough full-quota points for cross-service comparison."""
    label = capacity_text(service, plan).lower().replace(" ", "_")
    aliases = {
        "pro_1x": "pro", "max_5x": "max_5x", "max_20x": "max_20x",
        "ultra_5x": "ultra_5x", "ultra_20x": "ultra_20x",
    }
    key = aliases.get(label, label)
    return float(CAPACITY_POINTS.get(service, {}).get(key, 100))


def estimated_left_text(service: str, plan: Any, remaining_percent: float) -> tuple[str, float]:
    points = capacity_points(service, plan) * remaining_percent / 100.0
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
    if reset is None or not duration:
        return "不明"
    now = now or datetime.now().astimezone()
    total = timedelta(minutes=float(duration))
    time_left = reset - now
    elapsed_fraction = 1.0 - time_left / total
    used = 100.0 - float(row["remaining_percent"])
    if time_left.total_seconds() <= 0:
        return "更新待ち"
    if used <= 0.1:
        return "余裕あり"
    if elapsed_fraction <= 0.05:
        return "計測初期"
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
            remaining = row["remaining_percent"]
            used = 100.0 - remaining
            estimate, points = estimated_left_text(result["service"], result.get("plan"), remaining)
            service_scores.setdefault(result["service"], []).append(points)
            print(f"{result['service']:<9} {str(row['name']):<28.28} {plan:<14.14} {used:>6.1f}% {remaining:>7.1f}%  {reset_text(row.get('resets_at')):<12} {pace_text(row):<12} {estimate}")
    scores = {service: min(values) for service, values in service_scores.items() if values}
    if len(scores) > 1:
        ranking = " > ".join(f"{service} ({score:.0f}pt)" for service, score in sorted(scores.items(), key=lambda item: item[1], reverse=True))
        print(f"\n概算残量順位: {ranking}")
    print("※ pt・順位・PACEはプラン倍率と一定消費を仮定した参考推定で、実際のトークン数・回数ではありません。")


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex / Claude Code / agy の残り使用量を一覧表示")
    parser.add_argument("--json", action="store_true", help="機械可読なJSONを出力")
    parser.add_argument("--service", choices=("codex", "claude", "agy"), action="append", help="対象を限定（複数指定可）")
    args = parser.parse_args()
    selected = args.service or ["codex", "claude", "agy"]
    checkers = {"codex": codex_usage, "claude": claude_usage, "agy": agy_usage}
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
