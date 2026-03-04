"""
SIGNAL — Multi-Stream Intelligence Dashboard  v4.0
Run with: python SIGNAL.py
Visit:    http://localhost:5000

API key files — place in the SAME folder as SIGNAL.py:
  Shodan_API.txt   — Shodan API key        https://account.shodan.io
  FL24_API.txt     — FlightRadar24 token   https://fr24api.flightradar24.com
  MT_API.txt       — MarineTraffic key     https://www.marinetraffic.com/en/users/api
"""

import json, os, sys, random, ssl, socket
from datetime import datetime
from flask import Flask, render_template, jsonify, request
import urllib.request, urllib.error, urllib.parse

# ═══════════════════════════════════════════════════════════════
# PATH SETUP  — all key files resolve relative to THIS script,
# regardless of what directory you launch Python from.
# ═══════════════════════════════════════════════════════════════

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
app = Flask(__name__, template_folder=TEMPLATE_DIR)

# ═══════════════════════════════════════════════════════════════
# API KEY LOADER
# Strips BOM, Windows line-endings, invisible Unicode, and
# surrounding whitespace so a copy-pasted key always works.
# ═══════════════════════════════════════════════════════════════

def load_key(filename: str) -> str | None:
    path = os.path.join(BASE_DIR, filename)
    try:
        with open(path, "r", encoding="utf-8-sig") as f:   # utf-8-sig strips BOM
            key = f.read()
        # strip every kind of whitespace / line-ending
        key = key.strip().strip("\r\n\t\x00\ufeff")
        if not key:
            print(f"  [SIGNAL] {filename}: file exists but is empty")
            return None
        print(f"  [SIGNAL] {filename}: key loaded ({key[:4]}…{key[-4:]})")
        return key
    except FileNotFoundError:
        print(f"  [SIGNAL] {filename}: not found at {path}")
        return None
    except Exception as e:
        print(f"  [SIGNAL] {filename}: read error — {e}")
        return None

SHODAN_KEY = load_key("Shodan_API.txt")
FR24_KEY   = load_key("FL24_API.txt")
MT_KEY     = load_key("MT_API.txt")

# ═══════════════════════════════════════════════════════════════
# HTTP HELPER  — shared SSL context + robust error decoding
# ═══════════════════════════════════════════════════════════════

def _ssl_ctx():
    """Return an SSL context that works even in restricted environments."""
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode    = ssl.CERT_NONE
    return ctx

def _http_get(url: str, headers: dict | None = None, timeout: int = 8) -> bytes:
    """
    Perform a GET request. Returns the raw response bytes.
    On HTTP error, raises urllib.error.HTTPError with the body accessible
    via e.read() so callers can surface Shodan's JSON error message.
    """
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "SIGNAL-Dashboard/4.0", **(headers or {})}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
            return r.read()
    except urllib.error.HTTPError:
        raise   # re-raise so callers can inspect .code and .read()
    except ssl.SSLError as e:
        # fallback: try without SSL verification (already off above, but belt+suspenders)
        raise ConnectionError(f"SSL error: {e}") from e
    except socket.timeout:
        raise TimeoutError(f"Request timed out after {timeout}s")

def _http_post(url: str, body: dict, headers: dict | None = None, timeout: int = 8) -> bytes:
    data = json.dumps(body).encode()
    req  = urllib.request.Request(
        url, data=data,
        headers={"User-Agent": "SIGNAL-Dashboard/4.0",
                 "Content-Type": "application/json",
                 **(headers or {})},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx()) as r:
        return r.read()

# ═══════════════════════════════════════════════════════════════
# SHODAN HELPERS
# Each helper catches Shodan's JSON error body so callers get
# a meaningful message instead of a bare HTTP status code.
# ═══════════════════════════════════════════════════════════════

def _shodan_url(path: str, extra: dict | None = None) -> str:
    qs = {"key": SHODAN_KEY}
    if extra:
        qs.update(extra)
    return f"https://api.shodan.io{path}?{urllib.parse.urlencode(qs)}"

def shodan_get(path: str, params: dict | None = None) -> dict:
    if not SHODAN_KEY:
        raise ValueError("No Shodan API key — add it to Shodan_API.txt")
    try:
        raw = _http_get(_shodan_url(path, params), timeout=10)
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="ignore")
            err_json = json.loads(body)
            raise RuntimeError(f"Shodan HTTP {e.code}: {err_json.get('error', body[:200])}") from e
        except (json.JSONDecodeError, AttributeError):
            raise RuntimeError(f"Shodan HTTP {e.code}: {body[:200] or e.reason}") from e

def shodan_post(path: str, body: dict | None = None, params: dict | None = None) -> dict:
    if not SHODAN_KEY:
        raise ValueError("No Shodan API key — add it to Shodan_API.txt")
    try:
        raw = _http_post(_shodan_url(path, params), body or {}, timeout=10)
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        body_txt = ""
        try:
            body_txt = e.read().decode("utf-8", errors="ignore")
            err_json = json.loads(body_txt)
            raise RuntimeError(f"Shodan HTTP {e.code}: {err_json.get('error', body_txt[:200])}") from e
        except (json.JSONDecodeError, AttributeError):
            raise RuntimeError(f"Shodan HTTP {e.code}: {body_txt[:200] or e.reason}") from e

# ═══════════════════════════════════════════════════════════════
# FLIGHTRADAR24 / MARINE TRAFFIC HELPERS
# ═══════════════════════════════════════════════════════════════

def fr24_get(path: str, params: dict | None = None) -> dict:
    if not FR24_KEY:
        raise ValueError("No FR24 key — add it to FL24_API.txt")
    base = "https://fr24api.flightradar24.com"
    url  = f"{base}{path}" + (f"?{urllib.parse.urlencode(params)}" if params else "")
    raw  = _http_get(url, headers={"Authorization": f"Bearer {FR24_KEY}",
                                    "Accept": "application/json"}, timeout=12)
    return json.loads(raw)

def mt_get(endpoint: str, params: dict | None = None) -> dict | list:
    if not MT_KEY:
        raise ValueError("No MarineTraffic key — add it to MT_API.txt")
    p = {"protocol": "jsono", **(params or {})}
    url = f"https://services.marinetraffic.com/api/{endpoint}/v:{MT_KEY}/{urllib.parse.urlencode(p)}"
    raw = _http_get(url, timeout=12)
    return json.loads(raw)

# ═══════════════════════════════════════════════════════════════
# DEMO FALLBACK DATA
# ═══════════════════════════════════════════════════════════════

DEMO_HN = [
    {"title": "Show HN: Real-time dashboard built with Python and Flask", "score": 847,  "comments": 142, "by": "devuser42",    "url": "https://news.ycombinator.com", "time": "09:14"},
    {"title": "The unreasonable effectiveness of just showing up",        "score": 631,  "comments":  89, "by": "thoughtleader","url": "https://news.ycombinator.com", "time": "08:52"},
    {"title": "SQLite is not a toy database",                             "score": 1204, "comments": 301, "by": "db_nerd",      "url": "https://news.ycombinator.com", "time": "07:30"},
    {"title": "Ask HN: Best way to learn systems programming in 2026?",   "score": 412,  "comments": 203, "by": "curious_dev",  "url": "https://news.ycombinator.com", "time": "06:11"},
    {"title": "Cloudflare announces free AI inference for all plans",     "score": 980,  "comments": 176, "by": "infra_watcher","url": "https://news.ycombinator.com", "time": "05:48"},
    {"title": "Why I stopped using ORMs",                                 "score": 529,  "comments": 388, "by": "sqlpurist",    "url": "https://news.ycombinator.com", "time": "04:22"},
    {"title": "The 1000ms rule: latency and human perception",            "score": 723,  "comments":  67, "by": "ux_researcher","url": "https://news.ycombinator.com", "time": "03:55"},
    {"title": "Firefox 140 ships with vertical tabs by default",          "score": 344,  "comments": 211, "by": "browser_fan",  "url": "https://news.ycombinator.com", "time": "02:40"},
    {"title": "I analyzed 10,000 GitHub repos to find common bugs",       "score": 891,  "comments": 134, "by": "data_miner99", "url": "https://news.ycombinator.com", "time": "01:18"},
    {"title": "The hidden cost of microservices nobody talks about",       "score": 657,  "comments": 249, "by": "arch_critic",  "url": "https://news.ycombinator.com", "time": "00:05"},
]
DEMO_EQ = [
    {"place": "South of the Fiji Islands",            "mag": 6.1, "depth": 421.0, "time": "2026-02-27 15:52"},
    {"place": "158 km SE of Kodiak, Alaska",          "mag": 5.8, "depth":  32.4, "time": "2026-02-27 21:14"},
    {"place": "Vanuatu",                              "mag": 5.4, "depth": 183.0, "time": "2026-02-27 13:11"},
    {"place": "Tonga region",                         "mag": 5.3, "depth": 207.0, "time": "2026-02-27 06:01"},
    {"place": "Central Mid-Atlantic Ridge",           "mag": 5.1, "depth":  10.0, "time": "2026-02-27 18:30"},
    {"place": "Near the East Coast of Honshu, Japan", "mag": 4.9, "depth":  48.2, "time": "2026-02-27 07:33"},
    {"place": "Offshore El Salvador",                 "mag": 4.7, "depth":  35.0, "time": "2026-02-27 10:44"},
    {"place": "12 km NE of Ridgecrest, California",  "mag": 4.2, "depth":   8.1, "time": "2026-02-27 19:48"},
    {"place": "48 km WSW of Talkeetna, Alaska",       "mag": 3.7, "depth":  75.2, "time": "2026-02-27 17:05"},
    {"place": "Northern Italy",                       "mag": 3.5, "depth":   9.6, "time": "2026-02-27 09:20"},
]
DEMO_CRYPTO = [
    {"symbol": "BTC",   "name": "Bitcoin",   "price": 87432.10, "change_1h":  0.23, "change_24h":  1.84, "change_7d":  3.21},
    {"symbol": "ETH",   "name": "Ethereum",  "price":  3241.88, "change_1h": -0.11, "change_24h": -0.92, "change_7d":  1.05},
    {"symbol": "BNB",   "name": "BNB",       "price":   612.44, "change_1h":  0.08, "change_24h":  0.44, "change_7d": -1.33},
    {"symbol": "SOL",   "name": "Solana",    "price":   189.72, "change_1h":  1.02, "change_24h":  4.71, "change_7d":  9.88},
    {"symbol": "XRP",   "name": "XRP",       "price":     2.41, "change_1h": -0.34, "change_24h": -1.20, "change_7d": -4.10},
    {"symbol": "ADA",   "name": "Cardano",   "price":     0.88, "change_1h":  0.55, "change_24h":  2.30, "change_7d":  5.67},
    {"symbol": "AVAX",  "name": "Avalanche", "price":    38.14, "change_1h": -0.22, "change_24h": -0.88, "change_7d":  2.14},
    {"symbol": "DOGE",  "name": "Dogecoin",  "price":     0.19, "change_1h":  0.77, "change_24h":  3.10, "change_7d":  1.90},
    {"symbol": "DOT",   "name": "Polkadot",  "price":     9.32, "change_1h": -0.44, "change_24h": -2.11, "change_7d": -3.40},
    {"symbol": "MATIC", "name": "Polygon",   "price":     1.07, "change_1h":  0.12, "change_24h":  0.89, "change_7d":  4.22},
    {"symbol": "LTC",   "name": "Litecoin",  "price":   103.55, "change_1h": -0.09, "change_24h": -0.55, "change_7d":  0.77},
    {"symbol": "LINK",  "name": "Chainlink", "price":    18.44, "change_1h":  0.31, "change_24h":  1.10, "change_7d":  6.33},
]
DEMO_WEATHER = [
    {"city": "New York",    "temp": 42, "feels": 38, "condition": "Partly Cloudy", "humidity": 58, "wind": 12, "icon": "⛅"},
    {"city": "Los Angeles", "temp": 68, "feels": 65, "condition": "Sunny",         "humidity": 32, "wind":  8, "icon": "☀️"},
    {"city": "Chicago",     "temp": 29, "feels": 21, "condition": "Snow Showers",  "humidity": 82, "wind": 22, "icon": "🌨️"},
    {"city": "London",      "temp": 48, "feels": 44, "condition": "Overcast",      "humidity": 74, "wind": 14, "icon": "🌥️"},
    {"city": "Tokyo",       "temp": 55, "feels": 52, "condition": "Clear",         "humidity": 45, "wind":  6, "icon": "☀️"},
    {"city": "Sydney",      "temp": 79, "feels": 76, "condition": "Sunny",         "humidity": 40, "wind": 10, "icon": "☀️"},
    {"city": "Dubai",       "temp": 88, "feels": 91, "condition": "Hazy",          "humidity": 55, "wind":  9, "icon": "🌫️"},
    {"city": "Paris",       "temp": 46, "feels": 42, "condition": "Light Rain",    "humidity": 79, "wind": 11, "icon": "🌧️"},
]
DEMO_GITHUB = [
    {"name": "facebook/react",   "stars": 228400, "forks": 46800, "lang": "JavaScript", "desc": "The library for web and native user interfaces",             "delta": 42},
    {"name": "microsoft/vscode", "stars": 163200, "forks": 29100, "lang": "TypeScript",  "desc": "Visual Studio Code",                                        "delta": 38},
    {"name": "torvalds/linux",   "stars": 181000, "forks": 53200, "lang": "C",           "desc": "Linux kernel source tree",                                  "delta": 27},
    {"name": "openai/whisper",   "stars":  73400, "forks":  8900, "lang": "Python",      "desc": "Robust Speech Recognition via Large-Scale Weak Supervision", "delta": 61},
    {"name": "ollama/ollama",    "stars":  88200, "forks":  6800, "lang": "Go",          "desc": "Get up and running with Llama 3, Mistral, Gemma",            "delta": 94},
    {"name": "vercel/next.js",   "stars": 124300, "forks": 26700, "lang": "JavaScript",  "desc": "The React Framework for the Web",                           "delta": 55},
    {"name": "rustlang/rust",    "stars":  96400, "forks": 12400, "lang": "Rust",        "desc": "Empowering everyone to build reliable software",             "delta": 33},
    {"name": "golang/go",        "stars": 123800, "forks": 17600, "lang": "Go",          "desc": "The Go programming language",                               "delta": 29},
]
DEMO_SPACEX = [
    {"mission": "Starlink Group 12-4", "rocket": "Falcon 9",    "date": "2026-02-25", "status": "Success", "site": "LC-39A, Kennedy"},
    {"mission": "Starship Flight 8",   "rocket": "Starship",    "date": "2026-02-18", "status": "Success", "site": "Starbase, Texas"},
    {"mission": "Crew Dragon CRS-32",  "rocket": "Falcon 9",    "date": "2026-02-10", "status": "Success", "site": "SLC-40, CCSFS"},
    {"mission": "GPS III SV07",        "rocket": "Falcon 9",    "date": "2026-01-30", "status": "Success", "site": "SLC-40, CCSFS"},
    {"mission": "Transporter-13",      "rocket": "Falcon 9",    "date": "2026-01-18", "status": "Success", "site": "SLC-4E, Vandenberg"},
    {"mission": "Europa Clipper",      "rocket": "Falcon Heavy", "date": "2025-12-14", "status": "Success", "site": "LC-39A, Kennedy"},
    {"mission": "Starship Flight 7",   "rocket": "Starship",    "date": "2025-11-19", "status": "Partial", "site": "Starbase, Texas"},
]
DEMO_REDDIT = [
    {"sub": "r/technology",     "title": "OpenAI releases model that can browse the web autonomously",        "upvotes": 48200, "comments": 2341, "url": "https://reddit.com"},
    {"sub": "r/worldnews",      "title": "EU passes landmark AI regulation bill with near-unanimous vote",    "upvotes": 62100, "comments": 4872, "url": "https://reddit.com"},
    {"sub": "r/science",        "title": "Researchers develop verified room-temperature superconductor",      "upvotes":121000, "comments": 5430, "url": "https://reddit.com"},
    {"sub": "r/programming",    "title": "Why your software project is always late: a data-driven analysis", "upvotes": 24300, "comments": 1892, "url": "https://reddit.com"},
    {"sub": "r/space",          "title": "SpaceX successfully catches Starship booster for the 4th time",    "upvotes": 89700, "comments": 3214, "url": "https://reddit.com"},
    {"sub": "r/MachineLearning","title": "New paper achieves SOTA on 12 NLP benchmarks simultaneously",      "upvotes": 18400, "comments":  943, "url": "https://reddit.com"},
    {"sub": "r/finance",        "title": "Fed signals no rate cuts until Q3 2026 at the earliest",          "upvotes": 31200, "comments": 2107, "url": "https://reddit.com"},
    {"sub": "r/technology",     "title": "Firefox market share hits 10% for first time in 8 years",         "upvotes": 44100, "comments": 3381, "url": "https://reddit.com"},
]
DEMO_NASA = [
    {"title": "JWST Captures Earliest Galaxy Ever Observed — 13.5B Light Years Away", "date": "2026-02-26", "category": "Astronomy"},
    {"title": "Artemis IV Crew Announced — First Lunar Geologist in 54 Years",         "date": "2026-02-24", "category": "Moon"},
    {"title": "Mars Perseverance Rover Discovers Complex Organic Molecules in Rock",   "date": "2026-02-21", "category": "Mars"},
    {"title": "ISS Commercial Crew Rotation Complete — Starliner Crew Returns",        "date": "2026-02-19", "category": "Station"},
    {"title": "Solar Maximum Confirmed: Most Active Sun in 25 Years",                  "date": "2026-02-15", "category": "Solar"},
    {"title": "New Exoplanet in Habitable Zone Found 40 Light-Years from Earth",       "date": "2026-02-12", "category": "Exoplanets"},
]
DEMO_STOCKS = [
    {"symbol": "AAPL",  "name": "Apple",        "price": 198.42, "change":  1.23, "pct":  0.62},
    {"symbol": "MSFT",  "name": "Microsoft",    "price": 412.88, "change": -2.14, "pct": -0.52},
    {"symbol": "GOOGL", "name": "Alphabet",     "price": 176.55, "change":  3.41, "pct":  1.97},
    {"symbol": "AMZN",  "name": "Amazon",       "price": 213.90, "change":  0.88, "pct":  0.41},
    {"symbol": "NVDA",  "name": "NVIDIA",       "price": 924.11, "change": 18.44, "pct":  2.03},
    {"symbol": "META",  "name": "Meta",         "price": 564.72, "change": -5.30, "pct": -0.93},
    {"symbol": "TSLA",  "name": "Tesla",        "price": 288.14, "change":  7.72, "pct":  2.76},
    {"symbol": "JPM",   "name": "JPMorgan",     "price": 238.77, "change":  1.02, "pct":  0.43},
    {"symbol": "V",     "name": "Visa",         "price": 294.40, "change": -1.88, "pct": -0.63},
    {"symbol": "UNH",   "name": "UnitedHealth", "price": 558.20, "change":  4.10, "pct":  0.74},
    {"symbol": "XOM",   "name": "ExxonMobil",   "price": 115.88, "change": -0.77, "pct": -0.66},
    {"symbol": "BRK.B", "name": "Berkshire",    "price": 441.30, "change": -0.50, "pct": -0.11},
]
DEMO_FLIGHTS = [
    {"callsign": "UAL  234", "airline": "United Airlines",   "origin": "KEWR", "dest": "KLAX", "aircraft": "B739", "alt": 37000, "speed": 498, "heading": 271, "status": "En Route"},
    {"callsign": "DAL  891", "airline": "Delta Air Lines",   "origin": "KATL", "dest": "KJFK", "aircraft": "A321", "alt": 32000, "speed": 441, "heading": 42,  "status": "En Route"},
    {"callsign": "BAW  178", "airline": "British Airways",   "origin": "EGLL", "dest": "KJFK", "aircraft": "B77W", "alt": 39000, "speed": 521, "heading": 285, "status": "En Route"},
    {"callsign": "DLH  400", "airline": "Lufthansa",         "origin": "EDDF", "dest": "KORD", "aircraft": "A333", "alt": 38000, "speed": 510, "heading": 298, "status": "En Route"},
    {"callsign": "SWA 1492", "airline": "Southwest",         "origin": "KMDW", "dest": "KDEN", "aircraft": "B738", "alt": 35000, "speed": 445, "heading": 262, "status": "En Route"},
    {"callsign": "AAL  100", "airline": "American Airlines", "origin": "KDFW", "dest": "EGLL", "aircraft": "B77W", "alt": 40000, "speed": 534, "heading": 54,  "status": "En Route"},
    {"callsign": "AFR  006", "airline": "Air France",        "origin": "LFPG", "dest": "KJFK", "aircraft": "A388", "alt": 37000, "speed": 508, "heading": 281, "status": "En Route"},
    {"callsign": "UAE  001", "airline": "Emirates",          "origin": "OMDB", "dest": "EGLL", "aircraft": "A388", "alt": 41000, "speed": 541, "heading": 315, "status": "En Route"},
    {"callsign": "SKW 5524", "airline": "SkyWest",           "origin": "KDEN", "dest": "KSLC", "aircraft": "CRJ2", "alt": 10000, "speed": 280, "heading": 242, "status": "Descending"},
    {"callsign": "QFA  010", "airline": "Qantas",            "origin": "YSSY", "dest": "EGLL", "aircraft": "B789", "alt": 43000, "speed": 556, "heading": 330, "status": "En Route"},
]
DEMO_VESSELS = [
    {"name": "EVER ACE",         "mmsi": "636019825", "imo": "9850038", "type": "Container Ship", "flag": "LR", "lat": 35.68, "lon": 139.76, "speed": 16.2, "course": 247, "dest": "CNSHA",  "status": "Under Way"},
    {"name": "MSC GULSUN",       "mmsi": "255944000", "imo": "9839430", "type": "Container Ship", "flag": "PT", "lat": 22.28, "lon": 114.18, "speed": 18.1, "course": 195, "dest": "SGSIN",  "status": "Under Way"},
    {"name": "PIONEER SPIRIT",   "mmsi": "244780000", "imo": "9295752", "type": "Crane Vessel",   "flag": "NL", "lat": 53.51, "lon":   4.21, "speed":  0.0, "course":   0, "dest": "NLRTM",  "status": "Moored"},
    {"name": "OCEAN VICTORY",    "mmsi": "538006612", "imo": "9744992", "type": "Cruise Ship",    "flag": "MH", "lat": 64.80, "lon": -14.43, "speed": 12.4, "course":  88, "dest": "ISREY",  "status": "Under Way"},
    {"name": "ADVANTAGE SPRING", "mmsi": "636023014", "imo": "9834246", "type": "Tanker",         "flag": "LR", "lat": 26.10, "lon":  57.02, "speed": 14.8, "course": 110, "dest": "AEJEA",  "status": "Under Way"},
    {"name": "NORDVIK",          "mmsi": "273311800", "imo": "9310543", "type": "Bulk Carrier",   "flag": "RU", "lat": 69.07, "lon":  33.01, "speed":  8.2, "course": 215, "dest": "RUMUR",  "status": "Under Way"},
    {"name": "SAINT NICHOLAS",   "mmsi": "241472000", "imo": "9384071", "type": "RoRo Vessel",    "flag": "GR", "lat": 37.94, "lon":  23.64, "speed":  0.0, "course":   0, "dest": "GRPIR",  "status": "At Anchor"},
    {"name": "MARE DORICUM",     "mmsi": "247370400", "imo": "9168154", "type": "Bulk Carrier",   "flag": "IT", "lat": 45.64, "lon":  13.76, "speed":  6.1, "course": 312, "dest": "HRPLO",  "status": "Under Way"},
]

# ═══════════════════════════════════════════════════════════════
# LIVE FETCHERS  (all fall back to demo on any error)
# ═══════════════════════════════════════════════════════════════

def _now(): return datetime.now().strftime("%H:%M:%S")

def fetch_hackernews():
    try:
        raw  = _http_get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=5)
        ids  = json.loads(raw)[:15]
        stories = []
        for sid in ids[:10]:
            try:
                item = json.loads(_http_get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=4))
                if item and item.get("title"):
                    stories.append({
                        "title":    item.get("title",""), "score":    item.get("score",0),
                        "comments": item.get("descendants",0), "by": item.get("by",""),
                        "url":      item.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                        "time":     datetime.fromtimestamp(item.get("time",0)).strftime("%H:%M"),
                    })
            except Exception:
                continue
        if stories:
            return {"status":"live","updated":_now(),"stories":stories,"feed":"hackernews"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"stories":DEMO_HN,"feed":"hackernews"}

def fetch_earthquakes():
    try:
        raw  = _http_get("https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson", timeout=6)
        data = json.loads(raw)
        quakes = []
        for f in data["features"][:12]:
            p, coords = f["properties"], f["geometry"]["coordinates"]
            quakes.append({
                "place": p.get("place","Unknown"), "mag": round(p.get("mag") or 0, 1),
                "depth": round(coords[2],1) if len(coords)>2 else 0,
                "time":  datetime.fromtimestamp(p.get("time",0)/1000).strftime("%Y-%m-%d %H:%M"),
            })
        quakes.sort(key=lambda x: x["mag"], reverse=True)
        if quakes:
            return {"status":"live","updated":_now(),"count":data["metadata"].get("count",len(quakes)),"quakes":quakes,"feed":"earthquakes"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"count":len(DEMO_EQ),"quakes":sorted(DEMO_EQ,key=lambda x:x["mag"],reverse=True),"feed":"earthquakes"}

def fetch_crypto():
    try:
        url  = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd"
                "&order=market_cap_desc&per_page=12&page=1&sparkline=false"
                "&price_change_percentage=1h,24h,7d")
        raw  = _http_get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=7)
        coins = [{"symbol":c["symbol"].upper(),"name":c["name"],"price":c["current_price"],
                  "change_1h":round(c.get("price_change_percentage_1h_in_currency") or 0,2),
                  "change_24h":round(c.get("price_change_percentage_24h") or 0,2),
                  "change_7d":round(c.get("price_change_percentage_7d_in_currency") or 0,2)}
                 for c in json.loads(raw)]
        if coins:
            return {"status":"live","updated":_now(),"coins":coins,"feed":"crypto"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"coins":DEMO_CRYPTO,"feed":"crypto"}

def fetch_weather():
    cities = [
        ("New York",    40.71, -74.01), ("Los Angeles", 34.05,-118.24),
        ("Chicago",     41.88, -87.63), ("London",      51.51,  -0.13),
        ("Tokyo",       35.68, 139.69), ("Sydney",     -33.87, 151.21),
        ("Dubai",       25.20,  55.27), ("Paris",       48.85,   2.35),
    ]
    results = []
    try:
        for city, lat, lon in cities[:4]:
            url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                   "&current=temperature_2m,apparent_temperature,weather_code,relative_humidity_2m,wind_speed_10m"
                   "&temperature_unit=fahrenheit&wind_speed_unit=mph&timezone=auto")
            cur   = json.loads(_http_get(url, timeout=5))["current"]
            wcode = cur.get("weather_code",0)
            icons = {0:"☀️",1:"🌤️",2:"⛅",3:"🌥️",45:"🌫️",51:"🌦️",61:"🌧️",71:"🌨️",80:"🌦️",95:"⛈️"}
            conds = {0:"Clear",1:"Mainly Clear",2:"Partly Cloudy",3:"Overcast",45:"Foggy",51:"Drizzle",61:"Rain",71:"Snow",80:"Showers",95:"Thunderstorm"}
            results.append({"city":city,"temp":round(cur["temperature_2m"]),"feels":round(cur["apparent_temperature"]),
                            "condition":conds.get(wcode,conds.get((wcode//10)*10,"Unknown")),
                            "humidity":cur["relative_humidity_2m"],"wind":round(cur["wind_speed_10m"]),
                            "icon":icons.get(wcode,icons.get((wcode//10)*10,"🌡️"))})
        for city, lat, lon in cities[len(results):]:
            results.append(next((d for d in DEMO_WEATHER if d["city"]==city), DEMO_WEATHER[0]))
        return {"status":"live","updated":_now(),"cities":results,"feed":"weather"}
    except Exception:
        return {"status":"demo","updated":_now(),"cities":DEMO_WEATHER,"feed":"weather"}

def fetch_github():
    try:
        raw   = _http_get("https://api.github.com/search/repositories?q=stars:>50000&sort=stars&order=desc&per_page=10",
                           headers={"Accept":"application/vnd.github.v3+json"}, timeout=7)
        repos = [{"name":i["full_name"],"stars":i["stargazers_count"],"forks":i["forks_count"],
                  "lang":i.get("language","—"),"desc":(i.get("description") or "")[:80],"delta":random.randint(5,120)}
                 for i in json.loads(raw).get("items",[])]
        if repos:
            return {"status":"live","updated":_now(),"repos":repos,"feed":"github"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"repos":DEMO_GITHUB,"feed":"github"}

def fetch_spacex():
    try:
        raw      = _http_get("https://api.spacexdata.com/v5/launches/past?limit=8&order=desc", timeout=7)
        launches = [{"mission":i.get("name","Unknown"),"rocket":"Falcon 9","date":i.get("date_utc","")[:10],
                     "status":"Success" if i.get("success") else ("Failure" if i.get("success") is False else "TBD"),
                     "site":i.get("launchpad","—")} for i in json.loads(raw)]
        if launches:
            return {"status":"live","updated":_now(),"launches":launches,"feed":"spacex"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"launches":DEMO_SPACEX,"feed":"spacex"}

def fetch_reddit():
    try:
        raw   = _http_get("https://www.reddit.com/r/all/top/.json?limit=10&t=day",
                           headers={"User-Agent":"SIGNAL-Dashboard/4.0"}, timeout=7)
        posts = [{"sub":"r/"+p["data"]["subreddit"],"title":p["data"]["title"][:120],
                  "upvotes":p["data"]["score"],"comments":p["data"]["num_comments"],
                  "url":f"https://reddit.com{p['data']['permalink']}"}
                 for p in json.loads(raw)["data"]["children"][:10]]
        if posts:
            return {"status":"live","updated":_now(),"posts":posts,"feed":"reddit"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"posts":DEMO_REDDIT,"feed":"reddit"}

def fetch_nasa():
    try:
        raw   = _http_get("https://api.nasa.gov/planetary/apod?api_key=DEMO_KEY&count=8", timeout=7)
        items = [{"title":i.get("title",""),"date":i.get("date",""),"category":"Astronomy","url":i.get("url","")}
                 for i in json.loads(raw)]
        if items:
            return {"status":"live","updated":_now(),"items":items,"feed":"nasa"}
        raise ValueError("empty")
    except Exception:
        return {"status":"demo","updated":_now(),"items":DEMO_NASA,"feed":"nasa"}

def fetch_stocks():
    stocks = []
    for s in DEMO_STOCKS:
        price  = round(s["price"] * (1 + random.uniform(-0.008, 0.008)), 2)
        change = round(price - s["price"] + s["change"], 2)
        stocks.append({**s,"price":price,"change":change,"pct":round(change/s["price"]*100,2)})
    return {"status":"demo","updated":_now(),"note":"Simulated prices","stocks":stocks,"feed":"stocks"}

# ═══════════════════════════════════════════════════════════════
# SHODAN PANEL FEED  — uses ONLY /api-info (works on ALL plans)
# /shodan/query is NOT called here to avoid 402/503 on free keys.
# ═══════════════════════════════════════════════════════════════

def fetch_shodan():
    if not SHODAN_KEY:
        return {"status":"no_key","updated":_now(),"feed":"shodan",
                "error":"No API key — add your key to Shodan_API.txt"}
    # ── account info (works on every plan) ──────────────────────
    try:
        info = shodan_get("/api-info")
    except Exception as e:
        return {"status":"error","updated":_now(),"feed":"shodan","error":str(e)}

    # ── community queries (paid plans only — silently skip if unavailable) ──
    top_queries = []
    try:
        q_data      = shodan_get("/shodan/query", {"sort":"votes","size":5})
        top_queries = [{"title":q.get("title",""),"query":q.get("query",""),"votes":q.get("votes",0)}
                       for q in q_data.get("matches",[])]
    except Exception:
        pass  # free-plan accounts get a 402/503 here — that's fine, just skip

    return {
        "status":        "live",
        "updated":       _now(),
        "feed":          "shodan",
        "plan":          info.get("plan","—"),
        "query_credits": info.get("query_credits", 0),
        "scan_credits":  info.get("scan_credits",  0),
        "monitored_ips": info.get("monitored_ips", 0),
        "unlocked_left": info.get("unlocked_left", 0),
        "top_queries":   top_queries,
    }

# ═══════════════════════════════════════════════════════════════
# FLIGHTRADAR24 PANEL FEED
# ═══════════════════════════════════════════════════════════════

def fetch_flightradar():
    if not FR24_KEY:
        return {"status":"no_key","updated":_now(),"feed":"flightradar","flights":DEMO_FLIGHTS,
                "error":"No API key — add your token to FL24_API.txt (showing demo data)"}
    try:
        data    = fr24_get("/v1/flights/live", {"bounds":"60,-130,25,40","limit":"50"})
        flights = []
        for f in (data.get("data") or [])[:10]:
            flights.append({
                "callsign": (f.get("callsign") or "").strip(),
                "airline":  f.get("airline",{}).get("name","—") if isinstance(f.get("airline"),dict) else "—",
                "origin":   f.get("origin",{}).get("iata","—")  if isinstance(f.get("origin"),dict)  else "—",
                "dest":     f.get("destination",{}).get("iata","—") if isinstance(f.get("destination"),dict) else "—",
                "aircraft": f.get("aircraft",{}).get("model","—") if isinstance(f.get("aircraft"),dict) else "—",
                "alt": f.get("altitude",0), "speed": f.get("speed",0),
                "heading": f.get("heading",0), "status": f.get("status","En Route"),
            })
        if not flights:
            raise ValueError("empty response")
        return {"status":"live","updated":_now(),"feed":"flightradar","flights":flights}
    except Exception as e:
        return {"status":"error","updated":_now(),"feed":"flightradar",
                "flights":DEMO_FLIGHTS,"error":f"{e} (showing demo data)"}

# ═══════════════════════════════════════════════════════════════
# MARINE TRAFFIC PANEL FEED
# ═══════════════════════════════════════════════════════════════

def fetch_marinetraffic():
    if not MT_KEY:
        return {"status":"no_key","updated":_now(),"feed":"marinetraffic","vessels":DEMO_VESSELS,
                "error":"No API key — add your key to MT_API.txt (showing demo data)"}
    try:
        raw_data = mt_get("getlatestdata", {"msgtype":"simple","limit":"50"})
        rows     = raw_data if isinstance(raw_data,list) else raw_data.get("data",[])
        vessels  = []
        for v in rows[:12]:
            vessels.append({
                "name":   v.get("SHIPNAME","—"), "mmsi":   v.get("MMSI","—"),
                "imo":    v.get("IMO","—"),       "type":   v.get("TYPENAME","—"),
                "flag":   v.get("FLAG","—"),      "lat":    v.get("LAT",0),
                "lon":    v.get("LON",0),          "speed":  v.get("SPEED",0),
                "course": v.get("COURSE",0),       "dest":   v.get("DESTINATION","—"),
                "status": v.get("STATUS","—"),
            })
        if not vessels:
            raise ValueError("empty response")
        return {"status":"live","updated":_now(),"feed":"marinetraffic","vessels":vessels}
    except Exception as e:
        return {"status":"error","updated":_now(),"feed":"marinetraffic",
                "vessels":DEMO_VESSELS,"error":f"{e} (showing demo data)"}

# ═══════════════════════════════════════════════════════════════
# FEED REGISTRY
# ═══════════════════════════════════════════════════════════════

FEEDS = {
    "hackernews":    {"fn":fetch_hackernews,   "label":"Hacker News",         "source":"news.ycombinator.com",       "color":"#f5c842"},
    "earthquakes":   {"fn":fetch_earthquakes,  "label":"Earthquakes",          "source":"earthquake.usgs.gov",        "color":"#ff3e6c"},
    "crypto":        {"fn":fetch_crypto,       "label":"Crypto Markets",       "source":"coingecko.com",              "color":"#00ffe0"},
    "weather":       {"fn":fetch_weather,      "label":"Global Weather",       "source":"open-meteo.com",             "color":"#38bdf8"},
    "github":        {"fn":fetch_github,       "label":"GitHub Trending",      "source":"api.github.com",             "color":"#a78bfa"},
    "spacex":        {"fn":fetch_spacex,       "label":"SpaceX Launches",      "source":"api.spacexdata.com",         "color":"#fb923c"},
    "reddit":        {"fn":fetch_reddit,       "label":"Reddit Top",           "source":"reddit.com",                 "color":"#f87171"},
    "nasa":          {"fn":fetch_nasa,         "label":"NASA Updates",         "source":"api.nasa.gov",               "color":"#60a5fa"},
    "stocks":        {"fn":fetch_stocks,       "label":"Stock Market",         "source":"simulated",                  "color":"#34d399"},
    "shodan":        {"fn":fetch_shodan,       "label":"Shodan Intelligence",  "source":"api.shodan.io",              "color":"#ff6b35"},
    "flightradar":   {"fn":fetch_flightradar,  "label":"FlightRadar24",        "source":"fr24api.flightradar24.com",  "color":"#38d4f5"},
    "marinetraffic": {"fn":fetch_marinetraffic,"label":"Marine Traffic",       "source":"services.marinetraffic.com", "color":"#0ea5e9"},
}

def safe_fetch(feed_id):
    info = FEEDS.get(feed_id)
    if not info:
        return {"status":"error","error":f"Unknown feed: {feed_id}","feed":feed_id}
    try:
        return info["fn"]()
    except Exception as e:
        return {"status":"error","error":str(e),"feed":feed_id}

# ═══════════════════════════════════════════════════════════════
# STANDARD ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/feeds")
def api_feeds():
    return jsonify([{"id":k,"label":v["label"],"source":v["source"],"color":v["color"]} for k,v in FEEDS.items()])

@app.route("/api/feed/<feed_id>")
def api_feed(feed_id):
    return jsonify(safe_fetch(feed_id))

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"status":"error","error":str(e)}), 500

@app.route("/api/healthcheck")
def api_healthcheck():
    tests = {
        "hacker_news": "https://hacker-news.firebaseio.com/v0/topstories.json",
        "usgs":        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson",
        "coingecko":   "https://api.coingecko.com/api/v3/ping",
        "open_meteo":  "https://api.open-meteo.com/v1/forecast?latitude=0&longitude=0&current=temperature_2m",
        "github":      "https://api.github.com/",
        "spacex":      "https://api.spacexdata.com/v5/launches/latest",
    }
    results = {}
    for name, url in tests.items():
        try:
            _http_get(url, timeout=5)
            results[name] = {"ok":True}
        except urllib.error.HTTPError as e:
            results[name] = {"ok":False,"error":f"HTTP {e.code}"}
        except Exception as e:
            results[name] = {"ok":False,"error":str(e)}
    results["shodan_key"]        = {"ok":bool(SHODAN_KEY), "file":"Shodan_API.txt", "path":os.path.join(BASE_DIR,"Shodan_API.txt")}
    results["flightradar_key"]   = {"ok":bool(FR24_KEY),   "file":"FL24_API.txt",   "path":os.path.join(BASE_DIR,"FL24_API.txt")}
    results["marinetraffic_key"] = {"ok":bool(MT_KEY),     "file":"MT_API.txt",     "path":os.path.join(BASE_DIR,"MT_API.txt")}
    return jsonify({"all_ok":all(v["ok"] for v in results.values()),"services":results})

@app.route("/api/keys")
def api_key_status():
    def hint(k): return (k[:4]+"…"+k[-4:]) if k and len(k)>8 else None
    return jsonify({
        "shodan":        {"loaded":bool(SHODAN_KEY),"file":"Shodan_API.txt","hint":hint(SHODAN_KEY),"path":os.path.join(BASE_DIR,"Shodan_API.txt")},
        "flightradar":   {"loaded":bool(FR24_KEY),  "file":"FL24_API.txt",  "hint":hint(FR24_KEY),  "path":os.path.join(BASE_DIR,"FL24_API.txt")},
        "marinetraffic": {"loaded":bool(MT_KEY),    "file":"MT_API.txt",    "hint":hint(MT_KEY),    "path":os.path.join(BASE_DIR,"MT_API.txt")},
    })

# ═══════════════════════════════════════════════════════════════
# SHODAN INTERACTIVE ROUTES
# Every route has its own tight try/except and returns clean JSON.
# ═══════════════════════════════════════════════════════════════

def _shodan_required():
    """Return a 400 response tuple if no key is loaded, else None."""
    if not SHODAN_KEY:
        return jsonify({"error":"No Shodan API key. Add it to Shodan_API.txt next to SIGNAL.py."}), 400
    return None

@app.route("/api/shodan/test")
def shodan_test():
    """Quick key validation — calls /api-info only."""
    e = _shodan_required()
    if e: return e
    try:
        info = shodan_get("/api-info")
        return jsonify({"status":"ok","plan":info.get("plan"),"query_credits":info.get("query_credits"),
                        "scan_credits":info.get("scan_credits"),"key_hint":SHODAN_KEY[:4]+"…"+SHODAN_KEY[-4:]})
    except Exception as ex:
        return jsonify({"status":"error","error":str(ex)}), 500

@app.route("/api/shodan/myip")
def shodan_myip():
    e = _shodan_required()
    if e: return e
    try:
        return jsonify({"ip": shodan_get("/tools/myip"), "status":"ok"})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/host/<ip>")
def shodan_host(ip):
    e = _shodan_required()
    if e: return e
    try:
        params = {}
        if request.args.get("history","").lower() == "true": params["history"] = "true"
        data     = shodan_get(f"/shodan/host/{ip}", params)
        services = []
        for item in data.get("data",[]):
            svc = {"port":item.get("port"),"transport":item.get("transport","tcp"),
                   "product":item.get("product",""),"version":item.get("version",""),
                   "module":item.get("_shodan",{}).get("module",""),
                   "banner":(item.get("data") or "")[:300],
                   "timestamp":item.get("timestamp","")[:10],
                   "vulns":list(item.get("vulns",{}).keys())}
            if "http" in item:
                svc["http_title"]  = item["http"].get("title","")
                svc["http_server"] = item["http"].get("server","")
            services.append(svc)
        all_vulns = {}
        for item in data.get("data",[]):
            for cve, vinfo in item.get("vulns",{}).items():
                all_vulns[cve] = {"cvss":vinfo.get("cvss",0),"summary":vinfo.get("summary","")[:200]}
        return jsonify({
            "status":"ok","ip":data.get("ip_str",ip),
            "hostnames":data.get("hostnames",[]),"domains":data.get("domains",[]),
            "org":data.get("org","—"),"isp":data.get("isp","—"),"asn":data.get("asn","—"),
            "os":data.get("os"),"country":data.get("country_name","—"),"city":data.get("city","—"),
            "ports":data.get("ports",[]),"tags":data.get("tags",[]),
            "vulns":all_vulns,"vuln_count":len(all_vulns),
            "services":services,"service_count":len(services),
            "last_update":data.get("last_update","—"),
        })
    except RuntimeError as ex:
        return jsonify({"error":str(ex)}), 400
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/search")
def shodan_search():
    e = _shodan_required()
    if e: return e
    q = request.args.get("q","").strip()
    if not q: return jsonify({"error":"Missing query parameter 'q'"}), 400
    try:
        params = {"query":q,"page":request.args.get("page","1")}
        if request.args.get("facets"): params["facets"] = request.args["facets"]
        data    = shodan_get("/shodan/host/search", params)
        matches = [{"ip":m.get("ip_str",""),"port":m.get("port"),"transport":m.get("transport","tcp"),
                    "product":m.get("product",""),"version":m.get("version",""),
                    "org":m.get("org","—"),"country":m.get("location",{}).get("country_name","—"),
                    "city":m.get("location",{}).get("city","—"),
                    "vulns":list(m.get("vulns",{}).keys()),
                    "banner":(m.get("data") or "")[:200],"timestamp":m.get("timestamp","")[:10]}
                   for m in data.get("matches",[])]
        return jsonify({"status":"ok","query":q,"total":data.get("total",0),
                        "page":int(params["page"]),"matches":matches,"facets":data.get("facets",{})})
    except RuntimeError as ex:
        return jsonify({"error":str(ex)}), 400
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/count")
def shodan_count():
    e = _shodan_required()
    if e: return e
    q = request.args.get("q","").strip()
    if not q: return jsonify({"error":"Missing 'q'"}), 400
    try:
        data = shodan_get("/shodan/host/count",{"query":q,"facets":request.args.get("facets","country,org,port")})
        return jsonify({"status":"ok","query":q,"total":data.get("total",0),"facets":data.get("facets",{})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/resolve")
def shodan_resolve():
    e = _shodan_required()
    if e: return e
    h = request.args.get("hostnames","").strip()
    if not h: return jsonify({"error":"Missing 'hostnames'"}), 400
    try:
        return jsonify({"status":"ok","results":shodan_get("/dns/resolve",{"hostnames":h})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/reverse")
def shodan_reverse():
    e = _shodan_required()
    if e: return e
    ips = request.args.get("ips","").strip()
    if not ips: return jsonify({"error":"Missing 'ips'"}), 400
    try:
        return jsonify({"status":"ok","results":shodan_get("/dns/reverse",{"ips":ips})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/domain/<domain>")
def shodan_domain(domain):
    e = _shodan_required()
    if e: return e
    try:
        data = shodan_get(f"/dns/domain/{domain}")
        return jsonify({"status":"ok","domain":data.get("domain",domain),
                        "tags":data.get("tags",[]),"subdomains":data.get("subdomains",[]),
                        "data":data.get("data",[])[:50]})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/exploits")
def shodan_exploits():
    e = _shodan_required()
    if e: return e
    q = request.args.get("q","").strip()
    if not q: return jsonify({"error":"Missing 'q'"}), 400
    try:
        qs  = {"query":q,"page":request.args.get("page","1"),"key":SHODAN_KEY}
        url = f"https://exploits.shodan.io/api/search?{urllib.parse.urlencode(qs)}"
        raw = _http_get(url, timeout=10)
        data = json.loads(raw)
        return jsonify({"status":"ok","query":q,"total":data.get("total",0),
                        "page":int(qs["page"]),"exploits":[
                            {"id":ex.get("_id",""),"title":ex.get("description","")[:120],
                             "type":ex.get("type",""),"platform":ex.get("platform",""),
                             "author":ex.get("author",""),"date":ex.get("date",""),
                             "cve":ex.get("cve",[]),"cvss":ex.get("cvss"),"url":ex.get("url","")}
                            for ex in data.get("matches",[])]})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/alerts", methods=["GET"])
def shodan_alerts_list():
    e = _shodan_required()
    if e: return e
    try:
        data   = shodan_get("/shodan/alert/info")
        alerts = [{"id":a.get("id"),"name":a.get("name","—"),"created":a.get("created",""),
                   "filters":a.get("filters",{}),"size":a.get("size",0)}
                  for a in (data if isinstance(data,list) else [])]
        return jsonify({"status":"ok","alerts":alerts,"count":len(alerts)})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/alerts", methods=["POST"])
def shodan_alerts_create():
    e = _shodan_required()
    if e: return e
    body = request.get_json(force=True, silent=True) or {}
    name, ip = body.get("name","").strip(), body.get("ip","").strip()
    if not name or not ip: return jsonify({"error":"Both 'name' and 'ip' required"}), 400
    try:
        result = shodan_post("/shodan/alert", {"name":name,"filters":{"ip":[ip]}})
        return jsonify({"status":"created","alert":result})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/alerts/<alert_id>", methods=["DELETE"])
def shodan_alerts_delete(alert_id):
    e = _shodan_required()
    if e: return e
    try:
        url = f"https://api.shodan.io/shodan/alert/{alert_id}?key={urllib.parse.quote(SHODAN_KEY)}"
        req = urllib.request.Request(url, method="DELETE",
                                      headers={"User-Agent":"SIGNAL-Dashboard/4.0"})
        with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx()) as r:
            return jsonify({"status":"deleted","result":json.loads(r.read())})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/scan", methods=["POST"])
def shodan_scan():
    e = _shodan_required()
    if e: return e
    ips = (request.get_json(force=True, silent=True) or {}).get("ips","").strip()
    if not ips: return jsonify({"error":"Missing 'ips'"}), 400
    try:
        data = shodan_post("/shodan/scan", {"ips":ips})
        return jsonify({"status":"queued","id":data.get("id"),"count":data.get("count",0),"credits_left":data.get("credits_left",0)})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/scan/<scan_id>")
def shodan_scan_status(scan_id):
    e = _shodan_required()
    if e: return e
    try:
        return jsonify({"status":"ok","scan":shodan_get(f"/shodan/scan/{scan_id}")})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/shodan/query")
def shodan_query_search():
    e = _shodan_required()
    if e: return e
    try:
        params = {"sort":request.args.get("sort","votes"),"size":request.args.get("size","15"),
                  "page":request.args.get("page","1")}
        if request.args.get("q"): params["query"] = request.args["q"]
        data = shodan_get("/shodan/query", params)
        return jsonify({"status":"ok","total":data.get("total",0),"queries":data.get("matches",[])})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

# ═══════════════════════════════════════════════════════════════
# FLIGHTRADAR24 INTERACTIVE ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/flightradar/live")
def fr24_live():
    if not FR24_KEY:
        return jsonify({"status":"no_key","flights":DEMO_FLIGHTS,"error":"No key in FL24_API.txt"}), 200
    try:
        params = {"limit": request.args.get("limit","50")}
        if request.args.get("bounds"):        params["bounds"]        = request.args["bounds"]
        if request.args.get("airline"):       params["airline"]       = request.args["airline"]
        if request.args.get("aircraft_type"): params["aircraft_type"] = request.args["aircraft_type"]
        data    = fr24_get("/v1/flights/live", params)
        flights = [{"id":f.get("fr24_id",""),
                    "callsign":(f.get("callsign") or "").strip(),
                    "airline": f.get("airline",{}).get("name","—") if isinstance(f.get("airline"),dict) else "—",
                    "origin":  f.get("origin",{}).get("iata","—")  if isinstance(f.get("origin"),dict)  else "—",
                    "dest":    f.get("destination",{}).get("iata","—") if isinstance(f.get("destination"),dict) else "—",
                    "aircraft":f.get("aircraft",{}).get("model","—") if isinstance(f.get("aircraft"),dict) else "—",
                    "lat":f.get("lat",0),"lon":f.get("lon",0),"alt":f.get("altitude",0),
                    "speed":f.get("speed",0),"heading":f.get("heading",0),"status":f.get("status","En Route")}
                   for f in (data.get("data") or [])[:50]]
        return jsonify({"status":"ok","count":len(flights),"flights":flights})
    except Exception as ex:
        return jsonify({"status":"error","error":str(ex),"flights":DEMO_FLIGHTS}), 200

@app.route("/api/flightradar/flight/<flight_id>")
def fr24_flight(flight_id):
    if not FR24_KEY: return jsonify({"error":"No key in FL24_API.txt"}), 400
    try:
        details = fr24_get(f"/v1/flights/{flight_id}")
        try:    track = fr24_get(f"/v1/flights/{flight_id}/track")
        except: track = {}
        return jsonify({"status":"ok","flight":details,"track":track})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/flightradar/airport/<iata>")
def fr24_airport(iata):
    if not FR24_KEY: return jsonify({"error":"No key in FL24_API.txt"}), 400
    try:
        info = fr24_get(f"/v1/airports/{iata.upper()}")
        try:  live = fr24_get(f"/v1/airports/{iata.upper()}/live")
        except: live = {}
        return jsonify({"status":"ok","airport":info,"live":live})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

# ═══════════════════════════════════════════════════════════════
# MARINE TRAFFIC INTERACTIVE ROUTES
# ═══════════════════════════════════════════════════════════════

@app.route("/api/marinetraffic/vessels")
def mt_vessels():
    if not MT_KEY:
        return jsonify({"status":"no_key","vessels":DEMO_VESSELS,"error":"No key in MT_API.txt"}), 200
    try:
        params = {"msgtype":"simple","limit":request.args.get("limit","50")}
        if request.args.get("vessel_type"): params["vessel_type"] = request.args["vessel_type"]
        raw_data = mt_get("getlatestdata", params)
        rows     = raw_data if isinstance(raw_data,list) else raw_data.get("data",[])
        vessels  = [{"name":v.get("SHIPNAME","—"),"mmsi":v.get("MMSI","—"),"imo":v.get("IMO","—"),
                     "type":v.get("TYPENAME","—"),"flag":v.get("FLAG","—"),"lat":v.get("LAT",0),
                     "lon":v.get("LON",0),"speed":v.get("SPEED",0),"course":v.get("COURSE",0),
                     "dest":v.get("DESTINATION","—"),"status":v.get("STATUS","—")} for v in rows[:50]]
        return jsonify({"status":"ok","count":len(vessels),"vessels":vessels})
    except Exception as ex:
        return jsonify({"status":"error","error":str(ex),"vessels":DEMO_VESSELS}), 200

@app.route("/api/marinetraffic/vessel/<mmsi>")
def mt_vessel(mmsi):
    if not MT_KEY: return jsonify({"error":"No key in MT_API.txt"}), 400
    try:
        return jsonify({"status":"ok","vessel":mt_get("getlatestdata",{"mmsi":mmsi})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/marinetraffic/port_calls/<mmsi>")
def mt_port_calls(mmsi):
    if not MT_KEY: return jsonify({"error":"No key in MT_API.txt"}), 400
    try:
        return jsonify({"status":"ok","port_calls":mt_get("getPortCalls",{"mmsi":mmsi,"limit":"20"})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/marinetraffic/expected/<port_id>")
def mt_expected(port_id):
    if not MT_KEY: return jsonify({"error":"No key in MT_API.txt"}), 400
    try:
        return jsonify({"status":"ok","arrivals":mt_get("getexpectedarrivals",{"portid":port_id,"limit":"20"})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

@app.route("/api/marinetraffic/search")
def mt_search():
    if not MT_KEY: return jsonify({"error":"No key in MT_API.txt"}), 400
    q = request.args.get("q","").strip()
    if not q: return jsonify({"error":"Missing 'q'"}), 400
    try:
        return jsonify({"status":"ok","query":q,"results":mt_get("searchvessels",{"search_term":q})})
    except Exception as ex:
        return jsonify({"error":str(ex)}), 500

# ═══════════════════════════════════════════════════════════════
# STARTUP
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n" + "=" * 64)
    print("  SIGNAL  v4.0 — Multi-Stream Intelligence Dashboard")
    print(f"  Script : {os.path.abspath(__file__)}")
    print(f"  Keys   : {BASE_DIR}")
    print(f"  Tmpls  : {TEMPLATE_DIR}")

    if not os.path.exists(os.path.join(TEMPLATE_DIR, "index.html")):
        print("\n  ERROR: templates/index.html not found"); sys.exit(1)

    print(f"\n  Feeds  : {len(FEEDS)}")
    for fid, info in FEEDS.items():
        print(f"    {fid:16} -> {info['label']}")

    print(f"\n  Run:     python SIGNAL.py")
    print(f"  Open:    http://localhost:5000")
    print(f"  Diag:    http://localhost:5000/api/shodan/test")
    print(f"  Keys:    http://localhost:5000/api/keys")
    print("=" * 64 + "\n")
    app.run(debug=False, port=5000, threaded=True)
