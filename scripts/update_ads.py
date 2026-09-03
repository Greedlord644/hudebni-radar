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
from urllib.parse import quote_plus, urljoin
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "app" / "data" / "ads.json"
RSS = "https://hudebnibazar.cz/inzerat/rss/?kategorie=210000"
MIDI_URLS = ["https://www.midi.cz/kategorie/41/kapely/", "http://www.midi.cz/kategorie/41/kapely/"]
SKYTAROU_URLS = ["http://skytarou.cz/inzerce-kytara.php?zobrazit=muzikanti", "https://www.skytarou.cz/inzerce-kytara.php?zobrazit=muzikanti"]
BANDMATE_API = "https://nopibhycbaasthswzrov.supabase.co/rest/v1"
BANDMATE_KEY = "sb_publishable_ciCNMBqmNutJQmZpXoP2Vg_-uJKuDyG"
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
# These are disqualifiers, not negative scoring signals. Ads for commercial
# entertainment/cover projects are outside the radar even if they also mention
# a preferred genre, Prague or one of the owner's reference bands.
HARD_EXCLUDES = [
    "zábavová", "zabavova", "zábavovka", "zabavovka", "zábavy", "zabavy",
    "pivní slavnosti", "pivni slavnosti", "motosraz", "moto sraz",
    "bigbít", "bigbit", "big beat", "tribute", "revival", "cover band",
    "covery", "coverů", "coveru", "coverech", "coverem", "coverům", "coverama",
    "coverová", "coverova", "coverové", "coverove", "coverový", "coverovy",
    "převzaté skladby", "prevzate skladby", "převzaté písně", "prevzate pisne",
    "dechovka", "cimbál", "country kapel", "jazzov", "soulov",
]
SINGER_EXCLUDES = HARD_EXCLUDES + ["čistě žensk", "ženskou kapelu", "jen muzikantky"]
QUALITY = ["vlastní tvor", "autorsk", "nahráv", "koncert", "zkušeb", "projekt", "album", "singl", "ambice", "spolehliv", "dlouhodob"]
SEEKER = [r"zpěvačk[ay]\s+hled", r"zpěvák\s+hled", r"jsem\s+(?:zpěvačka|zpěvák)", r"zpívám.*hled", r"jako\s+zpěvačk[ae].*(?:přidat|hled)"]
WANTED = [r"hledáme\s+(?:zpěváka|zpěvačku|vokalist)", r"hledám\s+(?:zpěváka|zpěvačku|vokalist)", r"singer wanted"]
PRODUCTION_SEEKING = [
    r"(?:hledám|hledáme|sháním|sháníme|potřebuji|potřebujeme)\s+(?:někoho[^.!?]{0,80})?(?:producent|produkci|aranžér|skladatel|mix|master|studio)",
    r"(?:hledám|hledáme|sháním|sháníme|potřebuji|potřebujeme)[^.!?]{0,120}(?:aranž|sklád|složit|nahrát|nahrávání|zmixovat|mixing|mastering)",
    r"(?:někoho|člověka|parťáka)[^.!?]{0,80}(?:pomohl|pomůže|pomáhal)[^.!?]{0,100}(?:písnič|skladb|song|aranž|produk|nahrá|mix|master)",
    r"(?:pomoc|spoluprác)[^.!?]{0,60}(?:s\s+)?(?:produkc|aranž|sklád|nahráv|mix|master|dokončením\s+(?:písní|skladeb|songů|dem))",
]

# Regression examples supplied by the owner. The rules, not these URLs, decide
# whether they are displayed; keeping them in discovery prevents RSS-window
# limits from hiding the examples while the initial 60-day history is built.
DISCOVERY_SEEDS = [
    "https://hudebnibazar.cz/hledame-baskytaristu-baskytaristku-do-modern-metal-kapely/ID775914/",
    "https://hudebnibazar.cz/hledame-bubenika/ID775768/",
    "https://hudebnibazar.cz/hledame-zpevaka-na-nu-metal/ID772038/",
    "https://hudebnibazar.cz/hledam-shoegaze-nu-metal-kapelu-vek-16-20-praha/ID777343/",
    "https://hudebnibazar.cz/hledame-kytaristku/ID779842/",
]

def plain(value: str) -> str:
    return " ".join(value.lower().replace("–", "-").split())

def is_hard_excluded(value: str) -> bool:
    normalized = plain(value)
    return any(term in normalized for term in HARD_EXCLUDES)

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

def social_links_from_text(value: str) -> list[str]:
    links = []
    # A standalone @handle is overwhelmingly used as an Instagram contact in
    # these ads. The negative lookbehind prevents matching the domain part of
    # an e-mail address.
    instagram_handles = re.findall(r"(?<![\w.+-])@([a-z0-9._]{1,30})\b", value, re.IGNORECASE)
    instagram_handles += re.findall(r"\b(?:instagram|insta|ig)\b\s*(?::|[-–]|je)?\s*@?([a-z0-9._]{1,30})\b", value, re.IGNORECASE)
    links.extend(f"https://instagram.com/{handle}" for handle in instagram_handles)

    facebook_usernames = re.findall(r"(?:facebook|fb)\s*(?:profil|kontakt)?\s*[:\-]\s*@?([a-z0-9._-]{3,60})\b", value, re.IGNORECASE)
    links.extend(f"https://facebook.com/{username}" for username in facebook_usernames)
    facebook_names = re.findall(r"(?:facebook(?:ové)?\s+(?:jméno|jmeno)|na\s+facebooku\s+jako)\s*[:\-]?\s*([^\n,;]{3,80})", value, re.IGNORECASE)
    links.extend(f"https://www.facebook.com/search/top?q={quote_plus(name.strip())}" for name in facebook_names)
    return list(dict.fromkeys(links))

def fetch(session: requests.Session, url: str, timeout: int = 35) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    # Some older Czech classifieds (notably MIDI.cz) serve UTF-8 HTML while
    # omitting the charset from the HTTP header. Requests then defaults to
    # ISO-8859-1 and produces mojibake such as "HledĂ¡me".
    if not response.encoding or response.encoding.lower().replace("_", "-") in {"iso-8859-1", "latin-1"}:
        response.encoding = response.apparent_encoding or "utf-8"
    time.sleep(float(os.getenv("RADAR_DELAY", "0.35")))
    return response.text

def external_links(value: str, soup=None) -> list[str]:
    links = []
    if soup:
        links.extend(a.get("href") for a in soup.select("a[href]") if (a.get("href") or "").startswith("http"))
    links.extend(re.findall(r"https?://[^\s<>]+", value))
    links.extend(social_links_from_text(value))
    return list(dict.fromkeys(link.rstrip(".,;)") for link in links if link))[:5]

def fetch_first(session: requests.Session, urls: list[str], timeout: int) -> tuple[str, str]:
    errors = []
    for url in urls:
        try: return fetch(session, url, timeout=timeout), url
        except requests.RequestException as exc: errors.append(f"{url}: {exc}")
    raise requests.RequestException("; ".join(errors))

def bandmate_candidates(session: requests.Session) -> list[dict]:
    headers = {"apikey": BANDMATE_KEY}
    response = session.get(
        f"{BANDMATE_API}/listings",
        params={"select": "*", "active": "eq.true", "order": "bumped_at.desc.nullslast,created_at.desc", "limit": "250"},
        headers=headers, timeout=25,
    )
    response.raise_for_status()
    rows = response.json()
    user_ids = sorted({row.get("user_id") for row in rows if row.get("user_id")})
    names = {}
    if user_ids:
        profiles = session.get(
            f"{BANDMATE_API}/profiles",
            params={"select": "id,name", "id": f"in.({','.join(user_ids)})"},
            headers=headers, timeout=25,
        )
        profiles.raise_for_status()
        names = {profile["id"]: profile.get("name") or "Uživatel Bandmate" for profile in profiles.json()}
    result = []
    for row in rows:
        title, body = row.get("title") or "", row.get("body") or ""
        public_id = row.get("public_id")
        slug = re.sub(r"[^a-z0-9]+", "-", plain(title))[:60].strip("-") or "inzerat"
        url = f"https://bandmate.cz/inzerat/{slug}-{public_id}" if public_id else f"https://bandmate.cz/listings?id={row['id']}"
        text = " ".join(filter(None, [title, body, row.get("genre"), row.get("tag")]))
        result.append({
            "id": f"bandmate:{row['id']}", "title": title, "description": text, "url": url,
            # created_at intentionally wins over bumped_at: a bump must not masquerade as a new ad.
            "date": row.get("created_at"), "location": row.get("city") or "Neuvedeno",
            "author": names.get(row.get("user_id"), "Uživatel Bandmate"),
            "externalLinks": external_links(body), "source": "Bandmate",
        })
    return result

def midi_candidates(session: requests.Session) -> list[dict]:
    html, source_url = fetch_first(session, MIDI_URLS, timeout=20)
    soup = BeautifulSoup(html, "html.parser")
    result = []
    for item in soup.select("#mainCol .item"):
        link = item.select_one("h2 a[href]")
        date_el = item.select_one("p.date strong")
        desc = item.select_one(".popisInzeratu")
        if not link or not date_el or not desc: continue
        match = re.search(r"/inzerat/(\d+)/", link.get("href", ""))
        if not match: continue
        info = {}
        for row in item.select(".table_info tr"):
            cells = row.select("td")
            if len(cells) >= 2: info[cells[0].get_text(" ", strip=True).rstrip(":")] = cells[1].get_text(" ", strip=True)
        description = desc.get_text("\n", strip=True)
        result.append({
            "id": f"midi:{match.group(1)}", "title": link.get_text(" ", strip=True),
            "description": description, "url": urljoin(source_url, link["href"]),
            "date": datetime.strptime(date_el.get_text(" ", strip=True), "%d. %m. %Y %H:%M").replace(tzinfo=ZoneInfo("Europe/Prague")).isoformat(),
            "location": info.get("Region", "Neuvedeno"), "author": info.get("Inzerent", "Uživatel MIDI.cz").split("|")[0].strip(),
            "externalLinks": external_links(description, item), "source": "MIDI.cz",
        })
    return result

def skytarou_candidates(session: requests.Session) -> list[dict]:
    """Parse the legacy listing defensively; the site is occasionally slow."""
    html, source_url = fetch_first(session, SKYTAROU_URLS, timeout=15)
    soup = BeautifulSoup(html, "html.parser")
    result, seen = [], set()
    for detail in soup.find_all("a", string=re.compile(r"Detail", re.I)):
        href = detail.get("href") or ""
        container = detail
        for parent in detail.parents:
            text = parent.get_text(" ", strip=True)
            if re.search(r"\d{1,2}\.\d{1,2}\.\d{4}", text) and 80 <= len(text) <= 2500:
                container = parent; break
        text = container.get_text("\n", strip=True)
        date_match = re.search(r"(\d{1,2}\.\d{1,2}\.\d{4})(?:\s+(\d{1,2}:\d{2}))?", text)
        if not date_match: continue
        absolute = urljoin(source_url, href)
        identity = re.search(r"(?:editovat|id)=(\d+)", absolute, re.I)
        ad_id = identity.group(1) if identity else str(abs(hash(absolute)))
        if ad_id in seen: continue
        seen.add(ad_id)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        title = next((line for line in lines if len(line) >= 4 and not re.match(r"^(Hledám|Nabízím|Detail)$", line, re.I)), lines[0] if lines else "Inzerát")
        locality = next((line for line in reversed(lines) if any(x in plain(line) for x in ["praha", "středoč", "brno", "morav", "česko", "vysočina", "liberec", "zlín", "plzeň"])), "Neuvedeno")
        stamp = " ".join(x for x in date_match.groups() if x)
        fmt = "%d.%m.%Y %H:%M" if date_match.group(2) else "%d.%m.%Y"
        result.append({
            "id": f"skytarou:{ad_id}", "title": title, "description": text, "url": absolute,
            "date": datetime.strptime(stamp, fmt).replace(tzinfo=ZoneInfo("Europe/Prague")).isoformat(),
            "location": locality, "author": "Uživatel S kytarou", "externalLinks": external_links(text, container), "source": "S kytarou",
        })
    return result

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
    links.extend(social_links_from_text(description))
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
    if is_hard_excluded(value): return 0, []
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
    # Production work leads are a separate owner priority. A genuine request
    # for help always wins; ads merely offering production services do not.
    if any(re.search(pattern, value) for pattern in PRODUCTION_SEEKING):
        reasons = ["hledá produkci / pomoc se skladbami"]
        if has_external_link(value): reasons.append("odkaz na profil / ukázku")
        if location != "Neuvedeno": reasons.append(location)
        return 100, reasons[:4]
    if is_hard_excluded(value): return 0, []
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
    reasons = (genres[:2] + (["odkaz na profil / ukázku"] if linked else []) + (["vlastní tvorba"] if any("tvor" in x or "autorsk" in x for x in quality) else []) + ([location] if location != "Neuvedeno" else []))
    return (min(99, score), reasons[:4]) if score >= 58 else (0, [])

def summarize(text: str, limit: int = 330) -> str:
    # The generated JSON is public. Contact details stay only on the original
    # ad page; the radar publishes names, locations and public profile/media links.
    clean = re.sub(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", "", text, flags=re.IGNORECASE)
    clean = re.sub(r"\b[\w.+-]+\s*(?:\(\s*zavináč\s*\)|\[\s*zavináč\s*\]|zavináč)\s*[\w.-]+(?:\.[a-z]{2,})?\b", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(?<!\w)(?:\+?420[\s.-]*)?(?:\d[\s.-]*){9}(?!\w)", "", clean)
    clean = re.sub(r"\b(?:tel(?:efon)?|mobil|whatsapp|e-?mail)\s*[:：-]?\s*(?=$|[,;|])", "", clean, flags=re.IGNORECASE)
    clean = " ".join(clean.split())
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
        may_production = any(re.search(p, text) for p in PRODUCTION_SEEKING)
        may_interest = bool(matched_influences(text)) or any(x in text for x in DISCOVERY_TERMS)
        quality_hits = sum(1 for marker in QUALITY if marker in text)
        may_quality = (len(text) >= 180 and quality_hits >= 2) or (has_external_link(text) and len(text) >= 150)
        if ad_id and (may_seek or may_production or may_interest or may_quality): candidates.append((ad_id, title, description, url, item.findtext("pubDate", "")))

    for url in DISCOVERY_SEEDS:
        ad_id = (re.search(r"ID(\d+)", url) or [None, ""])[1]
        if ad_id and not any(item[0] == ad_id for item in candidates):
            candidates.append((ad_id, "", "", url, ""))

    singer, interesting = {}, {}
    evaluated_ids = {value for item in candidates for value in (item[0], f"hudebnibazar:{item[0]}")}
    for ad_id, title, short, url, pubdate in candidates:
        try: detail = parse_detail(fetch(session, url), title)
        except requests.RequestException as exc:
            print(f"Skipping {url}: {exc}"); continue
        text = f"{detail['title']} {detail['description']} {' '.join(detail['externalLinks'])}"
        ad_date = detail["inserted"] or (parsedate_to_datetime(pubdate).isoformat() if pubdate else datetime.now(timezone.utc).isoformat())
        base = {"id": f"hudebnibazar:{ad_id}", "title": detail["title"], "url": url, "date": ad_date, "location": detail["location"], "author": detail["author"], "excerpt": summarize(detail["description"] or short), "externalLinks": detail["externalLinks"], "influences": matched_influences(text), "genres": matched_genre_labels(text), "isPrague": "praha" in plain(detail["location"]), "source": "Hudební bazar"}
        score, reasons = singer_score(detail["title"], text, detail["location"])
        if score: singer[base["id"]] = {**base, "score": score, "reasons": reasons}
        score, reasons = interesting_score(text, detail["location"])
        if score: interesting[base["id"]] = {**base, "score": score, "reasons": reasons}

    # Every source is isolated: a temporary outage must not prevent the other
    # three sources from updating or delete the last successfully seen items.
    for loader in (bandmate_candidates, midi_candidates, skytarou_candidates):
        try:
            source_ads = loader(session)
        except (requests.RequestException, ValueError, TypeError) as exc:
            print(f"Source {loader.__name__} unavailable: {exc}")
            continue
        for ad in source_ads:
            evaluated_ids.add(ad["id"])
            text = f"{ad['title']} {ad['description']} {' '.join(ad['externalLinks'])}"
            base = {
                "id": ad["id"], "title": ad["title"], "url": ad["url"], "date": ad["date"],
                "location": ad["location"], "author": ad["author"], "excerpt": summarize(ad["description"]),
                "externalLinks": ad["externalLinks"], "influences": matched_influences(text),
                "genres": matched_genre_labels(text), "isPrague": "praha" in plain(ad["location"]), "source": ad["source"],
            }
            score, reasons = singer_score(ad["title"], text, ad["location"])
            if score: singer[ad["id"]] = {**base, "score": score, "reasons": reasons}
            score, reasons = interesting_score(text, ad["location"])
            if score: interesting[ad["id"]] = {**base, "score": score, "reasons": reasons}

    cutoff = datetime.now(timezone.utc) - timedelta(days=WINDOW_DAYS)
    def merge(group: str, fresh: dict) -> list[dict]:
        combined = {ad["id"]: ad for ad in previous.get(group, []) if ad["id"] not in evaluated_ids}; combined.update(fresh)
        kept = [ad for ad in combined.values() if datetime.fromisoformat(ad["date"]).astimezone(timezone.utc) >= cutoff and not is_hard_excluded(f"{ad.get('title', '')} {ad.get('excerpt', '')}")]
        for ad in kept:
            ad["excerpt"] = summarize(ad.get("excerpt", ""))
            ad["externalLinks"] = [link for link in ad.get("externalLinks", []) if link.startswith(("http://", "https://"))][:5]
        return sorted(kept, key=lambda ad: (ad["date"], ad["score"]), reverse=True)
    result = {"updatedAt": datetime.now(timezone.utc).isoformat(), "windowDays": WINDOW_DAYS, "singerSeeking": merge("singerSeeking", singer), "interesting": merge("interesting", interesting)}
    DATA.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(result['singerSeeking'])} singer leads and {len(result['interesting'])} interesting ads")

if __name__ == "__main__": main()
