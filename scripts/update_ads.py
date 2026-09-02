#!/usr/bin/env python3
"""Fetch the latest musician ads and keep a rolling, ranked 60-day radar."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data" / "ads.json"
RSS = "https://hudebnibazar.cz/inzerat/rss/?kategorie=210000"
WINDOW_DAYS = 60
UA = "HudebniRadar/1.0 (public-interest music ad index)"

INFLUENCES = {
    "Linkin Park": ["linkin park"],
    "Bring Me The Horizon": ["bring me the horizon", "bmth"],
    "Bad Omens": ["bad omens"],
    "Ghost": ["ghost"],
    "Architects": ["architects"],
    "Poppy": ["poppy"],
    "Spiritbox": ["spiritbox"],
    "Marilyn Manson": ["marilyn manson"],
    "Sleep Token": ["sleep token"],
    "Enter Shikari": ["enter shikari"],
    "Starset": ["starset"],
    "The Plot In You": ["the plot in you"],
    "Dayseeker": ["dayseeker"],
    "Normandie": ["normandie"],
    "Caskets": ["caskets"],
    "Motionless In White": ["motionless in white"],
    "Falling In Reverse": ["falling in revers"],
}
GENRES = ["alt rock", "alternative rock", "alternativní rock", "alt-rock", "alt metal", "alternative metal", "alternativní metal", "alt-metal", "nu metal", "nu-metal", "modern metal", "moderní metal", "modern rock", "moderní rock", "pop metal", "pop-metal", "emo", "electronic rock", "elektronika", "industrial", "grunge"]
PRIORITY_GENRES = ["nu metal", "nu-metal", "alt rock", "alt-rock", "alternative rock", "alternativní rock", "alt metal", "alt-metal", "alternative metal", "alternativní metal"]
GENRE_FILTERS = {
    "Nu-metal": ["nu metal", "nu-metal"],
    "Alt-rock": ["alt rock", "alt-rock", "alternative rock", "alternativní rock"],
    "Alt-metal": ["alt metal", "alt-metal", "alternative metal", "alternativní metal"],
    "Modern metal": ["modern metal", "moderní metal"],
    "Modern rock": ["modern rock", "moderní rock"],
    "Pop-metal": ["pop metal", "pop-metal"],
    "Emo": ["emo"],
    "Electronic rock": ["electronic rock"],
    "Elektronika": ["elektronika", "electro"],
    "Industrial": ["industrial"],
    "Grunge": ["grunge"],
}
DISCOVERY_TERMS = GENRES + ["metal", "rock", "hardcore", "electro"]
HARD_EXCLUDES = ["zábavová", "zabavova", "tribute", "revival", "cover band", "dechovka", "cimbál", "country kapel", "jazzov", "soulov"]
SINGER_EXCLUDES = HARD_EXCLUDES + ["čistě žensk", "ženskou kapelu", "jen muzikantky"]
QUALITY = ["vlastní tvor", "autorsk", "nahráv", "koncert", "zkušeb", "projekt", "album", "singl", "ambice", "spolehliv", "dlouhodob"]
SEEKER = [r"zpěvačk[ay]\s+hled", r"zpěvák\s+hled", r"jsem\s+(?:zpěvačka|zpěvák)", r"zpívám.*hled", r"jako\s+zpěvačk[ae].*(?:přidat|hled)"]
WANTED = [r"hledáme\s+(?:zpěváka|zpěvačku|vokalist)", r"hledám\s+(?:zpěváka|zpěvačku|vokalist)", r"singer wanted"]

# Regression examples supplied by the owner. The rules, not these URLs, decide
# whether they are displayed; keeping them in discovery prevents RSS-window
# limits from hiding the examples while the initial 60-day history is built.
DISCOVERY_SEEDS = [
    "https://hudebnibazar.cz/hledame-baskytaristu-baskytaristku-do-modern-metal-kapely/ID775914/",
    "https://hudebnibazar.cz/hledame-bubenika/ID775768/",
    "https://hudebnibazar.cz/hledame-zpevaka-na-nu-metal/ID772038/",
    "https://hudebnibazar.cz/hledam-shoegaze-nu-metal-kapelu-vek-16-20-praha/ID777343/",
]

def plain(value: str) -> str:
    return " ".join(value.lower().replace("–", "-").split())

def matched_influences(value: str) -> list[str]:
    normalized = plain(value)
    return [name for name, aliases in INFLUENCES.items() if any(alias in normalized for alias in aliases)]

def matched_genre_labels(value: str) -> list[str]:
    normalized = plain(value)
    return [name for name, aliases in GENRE_FILTERS.items() if any(alias in normalized for alias in aliases)]

def has_external_link(value: str) -> bool:
    normalized = plain(value)
    services = ["http://", "https://", "www.", "instagram", "facebook", "youtube", "youtu.be", "spotify", "bandzone", "soundcloud", "tiktok"]
    return any(service in normalized for service in services)

def fetch(session: requests.Session, url: str) -> str:
    response = session.get(url, timeout=35)
    response.raise_for_status()
    time.sleep(float(os.getenv("RADAR_DELAY", "0.35")))
    return response.text

def parse_detail(html: str, fallback_title: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title_el = soup.select_one(".detail-h1-text")
    desc_el = soup.select_one(".detail-desc .InzeratText")
    meta = " ".join(e.get_text(" ", strip=True) for e in soup.select(".detail-meta-item"))
    inserted = re.search(r"Vloženo\s+(\d{1,2}\.\d{1,2}\.\d{4})\s+(\d{1,2}:\d{2})", meta)
    location_el = soup.select_one(".user-details-row .user-meta")
    author_el = soup.select_one(".user-nick-row a")
    description = desc_el.get_text("\n", strip=True) if desc_el else ""
    links = []
    for element in soup.select(".detail-desc a[href], .InzeratOdkaz iframe[src]"):
        link = element.get("href") or element.get("src")
        if link and link.startswith("http") and "hudebnibazar.cz" not in link and "kytary.cz" not in link:
            link = re.sub(r"youtube\.com/embed/([^?]+).*", r"youtube.com/watch?v=\1", link)
            links.append(link)
    links.extend(re.findall(r"https?://[^\s]+", description))
    instagram = re.search(r"instagram\s*:\s*@?([\w.]+)", description, re.IGNORECASE)
    if instagram:
        links.append(f"https://instagram.com/{instagram.group(1)}")
    links = list(dict.fromkeys(link.rstrip(".,;)") for link in links))
    return {
        "title": title_el.get_text(" ", strip=True) if title_el else fallback_title,
        "description": description,
        "location": location_el.get_text(" ", strip=True) if location_el else "Neuvedeno",
        "author": author_el.get_text(" ", strip=True) if author_el else "Neuvedeno",
        "externalLinks": links[:5],
        "inserted": datetime.strptime(" ".join(inserted.groups()), "%d.%m.%Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Prague")).isoformat() if inserted else None,
    }

def explicit_age_over_40(text: str) -> bool:
    ages = [int(n) for n in re.findall(r"(?:je mi|mně je|muj věk je|můj věk je|věk)\s*[:\-]?\s*([1-8]\d)", text)]
    return bool(ages and min(ages) >= 40)

def local(location: str, text: str) -> bool:
    value = plain(location + " " + text)
    central = ["praha", "středočesk", "kladno", "beroun", "mělník", "kolín", "příbram", "rakovník", "benešov", "nymburk", "mladá boleslav"]
    return any(place in value for place in central)

def singer_score(title: str, text: str, location: str) -> tuple[int, list[str]]:
    value = plain(text)
    if any(re.search(pattern, plain(title)) for pattern in WANTED): return 0, []
    if not any(re.search(pattern, value) for pattern in SEEKER): return 0, []
    if not local(location, value) or any(x in value for x in SINGER_EXCLUDES) or explicit_age_over_40(value): return 0, []
    score, reasons = 62, ["zpěv hledá", location]
    matched_genres = [g for g in GENRES if g in value]
    influence_matches = matched_influences(value)
    if influence_matches: score += 22; reasons.append(influence_matches[0])
    if matched_genres: score += min(18, len(matched_genres) * 6); reasons.append(matched_genres[0])
    if "vlastní tvor" in value or "autorsk" in value: score += 8; reasons.append("vlastní tvorba")
    if len(value) > 500: score += 5; reasons.append("podrobný inzerát")
    return min(99, score), reasons[:4]

def interesting_score(text: str, location: str) -> tuple[int, list[str]]:
    value = plain(text)
    influence = matched_influences(value)
    genres = [x for x in GENRES if x in value]
    priority_genres = [x for x in PRIORITY_GENRES if x in value]
    quality = [x for x in QUALITY if x in value]
    linked = has_external_link(value)
    prague = "praha" in plain(location) or "praha" in value
    # A named reference band is an explicit owner preference and overrides all
    # other positive/negative scoring rules in this broad networking section.
    if influence:
        reasons = influence[:2] + (["odkaz na profil / ukázku"] if linked else []) + ([location] if location != "Neuvedeno" else [])
        return 100 if linked else 99, reasons[:4]
    # The owner's core genres are guaranteed inclusions as well.
    if priority_genres:
        score = 88 + (6 if prague else 0) + (6 if linked else 0)
        reasons = priority_genres[:2] + (["odkaz na profil / ukázku"] if linked else []) + ([location] if location != "Neuvedeno" else [])
        return min(100, score), reasons[:4]
    # Prague is independently relevant for local networking, even when the
    # genre is not named clearly enough for the genre rules.
    if prague and not genres:
        score = 66 + (12 if linked else 0) + min(12, len(quality) * 3) + (5 if len(value) >= 450 else 0)
        reasons = [location, "lokální networking"] + (["odkaz na profil / ukázku"] if linked else []) + (["podrobný inzerát"] if len(value) >= 450 else [])
        return min(94, score), reasons[:4]
    # A concrete, substantial ad is useful for networking even without the
    # owner's preferred genres or a Prague location.
    well_developed = len(value) >= 320 and len(quality) >= 2
    exceptionally_detailed = len(value) >= 600
    linked_and_concrete = linked and len(value) >= 220 and bool(quality)
    if not genres and (well_developed or exceptionally_detailed or linked_and_concrete):
        score = 60 + min(18, len(quality) * 3) + (12 if linked else 0) + (6 if len(value) >= 600 else 0)
        reasons = ["podrobný inzerát"] + (["jasný projekt / zkušenosti"] if quality else []) + (["odkaz na profil / ukázku"] if linked else []) + ([location] if location != "Neuvedeno" else [])
        return min(92, score), reasons[:4]
    if not genres: return 0, []
    score = 40 + min(42, len(influence) * 16) + min(36, len(genres) * 12) + min(16, len(quality) * 3)
    if linked: score += 12
    if prague: score += 8
    if len(value) >= 450: score += 7
    if any(x in value for x in HARD_EXCLUDES): score -= 28
    reasons = (genres[:2] + (["odkaz na profil / ukázku"] if linked else []) + (["vlastní tvorba"] if any("tvor" in x or "autorsk" in x for x in quality) else []) + ([location] if location != "Neuvedeno" else []))
    return (min(99, score), reasons[:4]) if score >= 58 else (0, [])

def summarize(text: str, limit: int = 330) -> str:
    clean = " ".join(text.split())
    if len(clean) <= limit: return clean
    return clean[:limit].rsplit(" ", 1)[0] + "…"

def main() -> None:
    previous = json.loads(DATA.read_text(encoding="utf-8")) if DATA.exists() else {"singerSeeking": [], "interesting": []}
    by_id = {ad["id"]: ad for group in (previous.get("singerSeeking", []), previous.get("interesting", [])) for ad in group}
    session = requests.Session(); session.headers.update({"User-Agent": UA, "Accept-Language": "cs,en;q=0.8"})
    root = ET.fromstring(fetch(session, RSS))
    candidates = []
    for item in root.findall("./channel/item"):
        title = item.findtext("title", ""); description = item.findtext("description", ""); url = item.findtext("link", "")
        ad_id = (re.search(r"ID(\d+)", url) or [None, ""])[1]
        text = plain(title + " " + description)
        may_seek = any(re.search(p, text) for p in SEEKER)
        may_interest = bool(matched_influences(text)) or any(x in text for x in DISCOVERY_TERMS)
        quality_hits = sum(1 for marker in QUALITY if marker in text)
        may_quality = (len(text) >= 180 and quality_hits >= 2) or (has_external_link(text) and len(text) >= 150)
        if ad_id and (may_seek or may_interest or may_quality): candidates.append((ad_id, title, description, url, item.findtext("pubDate", "")))

    for url in DISCOVERY_SEEDS:
        ad_id = (re.search(r"ID(\d+)", url) or [None, ""])[1]
        if ad_id and not any(item[0] == ad_id for item in candidates):
            candidates.append((ad_id, "", "", url, ""))

    singer, interesting = {}, {}
    evaluated_ids = {item[0] for item in candidates}
    for ad_id, title, short, url, pubdate in candidates:
        try: detail = parse_detail(fetch(session, url), title)
        except requests.RequestException as exc:
            print(f"Skipping {url}: {exc}"); continue
        text = f"{detail['title']} {detail['description']} {' '.join(detail['externalLinks'])}"
        ad_date = detail["inserted"] or (parsedate_to_datetime(pubdate).isoformat() if pubdate else datetime.now(timezone.utc).isoformat())
        base = {"id": ad_id, "title": detail["title"], "url": url, "date": ad_date, "location": detail["location"], "author": detail["author"], "excerpt": summarize(detail["description"] or short), "externalLinks": detail["externalLinks"], "influences": matched_influences(text), "genres": matched_genre_labels(text), "isPrague": "praha" in plain(detail["location"])}
        score, reasons = singer_score(detail["title"], text, detail["location"])
        if score: singer[ad_id] = {**base, "score": score, "reasons": reasons}
        score, reasons = interesting_score(text, detail["location"])
        if score: interesting[ad_id] = {**base, "score": score, "reasons": reasons}

    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    def merge(group: str, fresh: dict) -> list[dict]:
        combined = {ad["id"]: ad for ad in previous.get(group, []) if ad["id"] not in evaluated_ids}; combined.update(fresh)
        kept = [ad for ad in combined.values() if datetime.fromisoformat(ad["date"]).astimezone(timezone.utc) >= cutoff]
        return sorted(kept, key=lambda ad: (ad["date"], ad["score"]), reverse=True)
    result = {"updatedAt": datetime.now(timezone.utc).isoformat(), "windowDays": WINDOW_DAYS, "singerSeeking": merge("singerSeeking", singer), "interesting": merge("interesting", interesting)}
    DATA.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(result['singerSeeking'])} singer leads and {len(result['interesting'])} interesting ads")

if __name__ == "__main__": main()
