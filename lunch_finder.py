#!/usr/bin/env python3
"""東劇ビル周辺のランチ候補をOpenStreetMapから探す。"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any


TIMEOUT = 40
USER_AGENT = "lunch-finder/0.1 (personal CLI)"
OVERPASS_URLS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
# 東劇ビル（中央区築地4-1-1）。Nominatimで取得した建物の座標。
OFFICE_NAME = "東劇ビル"
OFFICE_LAT = 35.6676832
OFFICE_LON = 139.7686544
WALK_METERS_PER_MINUTE = 80
HYAKUMEITEN_FILE = Path(__file__).with_name("hyakumeiten.json")
CLOSED_FILE = Path(__file__).with_name("lunch_closed.txt")

CUISINE_LABELS = {
    "japanese": "和食",
    "sushi": "寿司",
    "ramen": "ラーメン",
    "noodle": "麺類",
    "udon": "うどん",
    "soba": "そば",
    "tempura": "天ぷら",
    "tonkatsu": "とんかつ",
    "yakiniku": "焼肉",
    "izakaya": "居酒屋",
    "seafood": "海鮮",
    "chinese": "中華",
    "korean": "韓国料理",
    "indian": "インド料理",
    "thai": "タイ料理",
    "italian": "イタリアン",
    "french": "フレンチ",
    "pizza": "ピザ",
    "burger": "ハンバーガー",
    "sandwich": "サンドイッチ",
    "curry": "カレー",
    "chicken": "鶏料理",
    "steak_house": "ステーキ",
    "regional": "郷土料理",
    "coffee_shop": "カフェ",
}


def overpass_query(lat: float, lon: float, radius: int, include_cafe: bool) -> str:
    kinds = "restaurant|fast_food|cafe" if include_cafe else "restaurant|fast_food"
    return (
        f"[out:json][timeout:25];"
        f'nwr(around:{radius},{lat},{lon})[amenity~"^({kinds})$"][name];'
        f"out center tags;"
    )


def fetch_places(lat: float, lon: float, radius: int, include_cafe: bool) -> list[dict[str, Any]]:
    body = urllib.parse.urlencode({"data": overpass_query(lat, lon, radius, include_cafe)}).encode()
    last_error: Exception | None = None
    for url in OVERPASS_URLS:
        request = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                payload = json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            continue
        return [place for element in payload.get("elements", []) if (place := parse_element(element, lat, lon))]
    raise RuntimeError(f"Overpass APIに接続できませんでした: {last_error}")


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def cuisine_label(tags: dict[str, str]) -> str:
    raw = tags.get("cuisine", "")
    labels = [CUISINE_LABELS.get(item.strip(), item.strip()) for item in raw.split(";") if item.strip()]
    if labels:
        return "・".join(labels)
    return {"cafe": "カフェ", "fast_food": "ファストフード"}.get(tags.get("amenity", ""), "")


def parse_element(element: dict[str, Any], origin_lat: float, origin_lon: float) -> dict[str, Any] | None:
    tags = element.get("tags") or {}
    center = element.get("center") or element
    lat, lon = center.get("lat"), center.get("lon")
    if lat is None or lon is None or not tags.get("name"):
        return None
    meters = distance_meters(origin_lat, origin_lon, lat, lon)
    return {
        "name": tags["name"],
        "branch": tags.get("branch"),
        "genre": cuisine_label(tags),
        "cuisine": tags.get("cuisine", ""),
        "amenity": tags.get("amenity", ""),
        "meters": round(meters),
        "walk_minutes": max(1, math.ceil(meters / WALK_METERS_PER_MINUTE)),
        "opening_hours": tags.get("opening_hours"),
        "checked": tags.get("check_date") or tags.get("survey:date"),
        "hyakumeiten": None,
        "reservation_only": False,
        "note": "",
        "website": tags.get("website") or tags.get("contact:website"),
        "phone": tags.get("phone") or tags.get("contact:phone"),
        "lat": lat,
        "lon": lon,
        "osm": f"https://www.openstreetmap.org/{element['type']}/{element['id']}",
    }


WEEKDAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def parse_days(text: str) -> set[int] | None:
    days: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if part == "PH":
            continue
        match = re.fullmatch(r"(Mo|Tu|We|Th|Fr|Sa|Su)(?:-(Mo|Tu|We|Th|Fr|Sa|Su))?", part)
        if not match:
            return None
        start = WEEKDAYS.index(match.group(1))
        end = WEEKDAYS.index(match.group(2)) if match.group(2) else start
        days.update((start + offset) % 7 for offset in range((end - start) % 7 + 1))
    return days


def minutes(text: str) -> int:
    hour, minute = text.split(":")
    return int(hour) * 60 + int(minute)


def is_open_at(opening_hours: str | None, weekday: int, minute_of_day: int) -> bool | None:
    """OSMのopening_hoursの基本形だけ解釈する。解釈できなければNone。"""
    if not opening_hours:
        return None
    if opening_hours.strip() == "24/7":
        return True
    result: bool | None = None
    for rule in opening_hours.split(";"):
        rule = rule.strip()
        if not rule:
            continue
        match = re.fullmatch(r"([A-Za-z,\- ]+?)?\s*((?:\d{1,2}:\d{2}-\d{1,2}:\d{2}(?:,\s*)?)+|off)", rule)
        if not match:
            return None
        days = parse_days(match.group(1).strip()) if match.group(1) else set(range(7))
        if days is None:
            return None
        spans = match.group(2)
        # 後ろのルールが前のルールを上書きする（OSMの規則）
        if spans == "off":
            if weekday in days:
                result = False
            continue
        for span in re.findall(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", spans):
            start, end = minutes(span[0]), minutes(span[1])
            if start < end:
                # 当日分
                if weekday in days:
                    if start <= minute_of_day < end:
                        result = True
            else:
                # 日またぎ: 当日の開始以降、または前日開始の翌朝分
                if weekday in days and minute_of_day >= start:
                    result = True
                if (weekday - 1) % 7 in days and minute_of_day < end:
                    result = True
    return bool(result) if result is not None else False


def load_closed_names() -> list[str]:
    if not CLOSED_FILE.exists():
        return []
    lines = (line.strip() for line in CLOSED_FILE.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def remove_closed(places: list[dict[str, Any]], closed_names: list[str]) -> list[dict[str, Any]]:
    return [place for place in places if not any(name in display_name(place) for name in closed_names)]


def hyakumeiten_places(origin_lat: float, origin_lon: float, radius: int) -> list[dict[str, Any]]:
    if not HYAKUMEITEN_FILE.exists():
        return []
    places = []
    for entry in json.loads(HYAKUMEITEN_FILE.read_text(encoding="utf-8")):
        meters = distance_meters(origin_lat, origin_lon, entry["lat"], entry["lon"])
        if meters > radius:
            continue
        places.append({
            "name": entry["name"],
            "branch": None,
            "genre": entry["genre"],
            "cuisine": "",
            "amenity": "restaurant",
            "meters": round(meters),
            "walk_minutes": max(1, math.ceil(meters / WALK_METERS_PER_MINUTE)),
            "opening_hours": entry["opening_hours"],
            "checked": None,
            "hyakumeiten": entry["award"],
            "reservation_only": entry["reservation_only"],
            "note": entry["note"],
            "website": entry["url"],
            "phone": None,
            "lat": entry["lat"],
            "lon": entry["lon"],
            "osm": entry["url"],
        })
    return places


def filter_places(places: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    if not keywords:
        return places
    lowered = [keyword.lower() for keyword in keywords]

    def matches(place: dict[str, Any]) -> bool:
        haystack = f"{place['name']} {place['genre']} {place['cuisine']}".lower()
        return any(keyword in haystack for keyword in lowered)

    return [place for place in places if matches(place)]


def display_name(place: dict[str, Any]) -> str:
    return f"{place['name']} {place['branch']}" if place["branch"] else place["name"]


HTML_TEMPLATE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css">
<style>
html, body { height: 100%; margin: 0; font-family: system-ui, sans-serif; }
#map { height: 100%; }
.popup-name { font-weight: bold; }
.popup-meta { color: #555; }
.popup-award { color: #8a6d00; font-weight: bold; }
</style>
</head>
<body>
<div id="map"></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js"></script>
<script>
const data = __DATA__;
const map = L.map("map").setView([data.office.lat, data.office.lon], 17);
L.tileLayer("https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html" target="_blank" rel="noopener">地理院タイル</a> / 店舗データ &copy; OpenStreetMap contributors',
}).addTo(map);
L.circle([data.office.lat, data.office.lon], { radius: data.radius, color: "#888", weight: 1, fill: false }).addTo(map);
L.marker([data.office.lat, data.office.lon]).addTo(map).bindTooltip(data.office.name, { permanent: true, direction: "top" });

function line(parent, className, text) {
  const div = document.createElement("div");
  div.className = className;
  div.textContent = text;
  parent.appendChild(div);
}

for (const place of data.places) {
  const box = document.createElement("div");
  line(box, "popup-name", (place.hyakumeiten ? "★ " : "") + place.display_name);
  if (place.hyakumeiten) line(box, "popup-award", "食べログ " + place.hyakumeiten);
  line(box, "popup-meta", [place.genre, "徒歩" + place.walk_minutes + "分 (" + place.meters + "m)"].filter(Boolean).join(" / "));
  if (place.opening_hours) line(box, "popup-meta", "営業時間: " + place.opening_hours);
  if (place.reservation_only) line(box, "popup-meta", "完全予約制");
  if (place.note) line(box, "popup-meta", place.note);
  if (!place.hyakumeiten) line(box, "popup-meta", "OSM最終確認: " + (place.checked || "なし（要確認）"));
  const link = document.createElement("a");
  link.href = place.website && /^https?:\\/\\//.test(place.website) ? place.website : place.osm;
  link.target = "_blank";
  link.rel = "noopener";
  link.textContent = "詳細";
  box.appendChild(link);
  const check = document.createElement("a");
  check.href = "https://www.google.com/maps/search/?api=1&query=" + encodeURIComponent(place.display_name + " 銀座");
  check.target = "_blank";
  check.rel = "noopener";
  check.textContent = "Googleマップで営業確認";
  check.style.marginLeft = "8px";
  box.appendChild(check);
  const style = place.hyakumeiten
    ? { radius: 11, color: "#8a6d00", fillColor: "#f1c40f", fillOpacity: 0.95, weight: 2 }
    : { radius: 8, color: "#c0392b", fillColor: "#e74c3c", fillOpacity: 0.85 };
  L.circleMarker([place.lat, place.lon], style)
    .addTo(map)
    .bindTooltip((place.hyakumeiten ? "★ " : "") + place.display_name)
    .bindPopup(box);
}
</script>
</body>
</html>
"""


def render_html(places: list[dict[str, Any]], radius: int) -> str:
    data = {
        "office": {"name": OFFICE_NAME, "lat": OFFICE_LAT, "lon": OFFICE_LON},
        "radius": radius,
        "places": [{**place, "display_name": display_name(place)} for place in places],
    }
    # "</" を含む店名で <script> が閉じないようにする
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__TITLE__", f"{OFFICE_NAME}周辺のランチ").replace("__DATA__", payload)


def print_places(places: list[dict[str, Any]]) -> None:
    for place in places:
        genre = f" [{place['genre']}]" if place["genre"] else ""
        badge = f"★百名店({place['hyakumeiten']}) " if place["hyakumeiten"] else ""
        note = " (営業時間不明)" if place.get("open_at", True) is None else ""
        print(f"{badge}{display_name(place)}{genre}{note}  徒歩{place['walk_minutes']}分 ({place['meters']}m)")
        if place["opening_hours"]:
            print(f"    営業時間: {place['opening_hours']}")
        if place["reservation_only"]:
            print("    完全予約制")
        if place["note"]:
            print(f"    {place['note']}")
        if place["hyakumeiten"] is None:
            print(f"    OSM最終確認: {place['checked'] or 'なし（閉店の可能性あり、要確認）'}")
        print(f"    {place['website'] or place['osm']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=f"{OFFICE_NAME}周辺のランチ候補を表示")
    parser.add_argument("keyword", nargs="*", help="店名・ジャンルで絞り込む（例: ラーメン 寿司 ramen）")
    parser.add_argument("-r", "--radius", type=int, default=500, help="検索半径(m)（既定: 500）")
    parser.add_argument("-n", "--limit", type=int, default=20, help="表示件数（既定: 20）")
    parser.add_argument("--at", metavar="HH:MM", help="この時刻（今日）に営業している店だけにする（例: 13:30）")
    parser.add_argument("--unknown", action="store_true", help="--at のとき、営業時間が不明な店も含める")
    parser.add_argument("--hyakumeiten", action="store_true", help="食べログ百名店だけを表示")
    parser.add_argument("--cafe", action="store_true", help="カフェも含める")
    parser.add_argument("--pick", action="store_true", help="候補からランダムに1軒選ぶ")
    parser.add_argument("--json", action="store_true", help="JSONで出力")
    parser.add_argument(
        "--html",
        nargs="?",
        const="lunch_map.html",
        metavar="FILE",
        help="地図付きHTMLを書き出してブラウザで開く（既定: lunch_map.html）",
    )
    args = parser.parse_args()

    places: list[dict[str, Any]] = []
    if not args.hyakumeiten:
        try:
            places = fetch_places(OFFICE_LAT, OFFICE_LON, args.radius, args.cafe)
        except RuntimeError as exc:
            print(exc, file=sys.stderr)
            return 1

    places = remove_closed(places, load_closed_names())
    places += hyakumeiten_places(OFFICE_LAT, OFFICE_LON, args.radius)
    places = filter_places(places, args.keyword)
    if args.at:
        try:
            at = datetime.strptime(args.at, "%H:%M")
        except ValueError:
            print("--at は HH:MM 形式で指定してください（例: 13:30）", file=sys.stderr)
            return 2
        weekday = datetime.now().weekday()
        for place in places:
            place["open_at"] = is_open_at(place["opening_hours"], weekday, at.hour * 60 + at.minute)
        unknown = sum(1 for place in places if place["open_at"] is None)
        places = [place for place in places if place["open_at"] or (args.unknown and place["open_at"] is None)]
        if not args.unknown and unknown:
            print(f"営業時間が不明な{unknown}件は除外しました（含めるには --unknown）", file=sys.stderr)
    places.sort(key=lambda place: place["meters"])
    if not places:
        print("該当する店が見つかりませんでした。半径(-r)を広げるか、キーワードを変えてください。", file=sys.stderr)
        return 1

    if args.pick:
        places = [random.choice(places)]
    else:
        places = places[: args.limit]

    if args.html:
        path = Path(args.html).resolve()
        path.write_text(render_html(places, args.radius), encoding="utf-8")
        print(f"{len(places)}件を地図に出力しました: {path}")
        webbrowser.open(path.as_uri())
    elif args.json:
        print(json.dumps(places, ensure_ascii=False, indent=2))
    else:
        print_places(places)
    return 0


if __name__ == "__main__":
    sys.exit(main())
