```
███████╗██╗ ██████╗ ███╗   ██╗ █████╗ ██╗
██╔════╝██║██╔════╝ ████╗  ██║██╔══██╗██║
███████╗██║██║  ███╗██╔██╗ ██║███████║██║
╚════██║██║██║   ██║██║╚██╗██║██╔══██║██║
███████║██║╚██████╔╝██║ ╚████║██║  ██║███████╗
╚══════╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝  ╚═╝╚══════╝
```

> **Multi-Stream Intelligence Dashboard** — live feeds, threat intelligence, global tracking, market data.  
> Built with Python · Flask · vanilla JS. No build step. No dependencies beyond `flask`.

---

## OVERVIEW

SIGNAL is a self-hosted, real-time intelligence dashboard that aggregates twelve live data streams into a single terminal-aesthetic interface. Three configurable panel slots display any feed on demand. Below the grid, three full-featured intelligence sections — **Shodan**, **FlightRadar24**, and **Marine Traffic** — provide deep interactive tooling for each API.

```
┌─────────────────────────────────────────────────────────────────┐
│  SIGNAL  ● LIVE                                    03 MAR 2026  │
├─────────────────┬─────────────────┬───────────────────────────  │
│  HACKER NEWS    │  EARTHQUAKES    │  CRYPTO MARKETS             │
│  ───────────    │  ───────────    │  ─────────────              │
│  ...            │  ...            │  ...                        │
│                 │                 │                             │
├─────────────────┴─────────────────┴───────────────────────────  │
│  SHODAN INTELLIGENCE  ·  FLIGHTRADAR24  ·  MARINE TRAFFIC       │
└─────────────────────────────────────────────────────────────────┘
```

---

## QUICK START

```bash
# 1. Clone or copy files into a working directory
mkdir signal && cd signal
cp SIGNAL.py .
mkdir templates && cp index.html templates/

# 2. Install the only dependency
pip install flask

# 3. Add API keys (optional — dashboard runs without them)
echo "your_shodan_key"        > Shodan_API.txt
echo "your_fr24_bearer_token" > FL24_API.txt
echo "your_marinetraffic_key" > MT_API.txt

# 4. Run
python SIGNAL.py

# 5. Open
# http://localhost:5000
```

> **Key rule:** all three `.txt` key files must live in the **same folder as `SIGNAL.py`**.  
> The script resolves paths from its own location, not from wherever you run Python.

---

## FILE STRUCTURE

```
signal/
├── SIGNAL.py            ← Flask application + all API routes
├── Shodan_API.txt        ← Shodan API key          (you create this)
├── FL24_API.txt          ← FlightRadar24 token      (you create this)
├── MT_API.txt            ← Marine Traffic key       (you create this)
└── templates/
    └── index.html        ← Single-file frontend (HTML + CSS + JS)
```

No database. No build tools. No `.env` files. Keys live in plain text files next to the script.

---

## LIVE DATA FEEDS

All feeds auto-refresh every 90 seconds. Each panel slot can display any feed via the dropdown selector. Feeds with no API key fall back to realistic demo data silently — the dashboard never crashes on a missing key.

| Feed | Source | Key Required | Notes |
|---|---|---|---|
| **Hacker News** | `hacker-news.firebaseio.com` | No | Top 10 stories, live scores |
| **Earthquakes** | `earthquake.usgs.gov` | No | M2.5+ events, past 24h |
| **Crypto Markets** | `api.coingecko.com` | No | 12 coins, 1h/24h/7d change |
| **Global Weather** | `api.open-meteo.com` | No | 8 cities, temp/humidity/wind |
| **GitHub Trending** | `api.github.com` | No | Top starred repos |
| **SpaceX Launches** | `api.spacexdata.com` | No | Past 8 launches + status |
| **Reddit Top** | `reddit.com` | No | r/all top posts of the day |
| **NASA Updates** | `api.nasa.gov` | No | APOD and mission news |
| **Stock Market** | Simulated | No | 12 equities, randomised drift |
| **Shodan Intelligence** | `api.shodan.io` | **Yes** | Account stats + query panel |
| **FlightRadar24** | `fr24api.flightradar24.com` | **Yes** | Live flight positions |
| **Marine Traffic** | `services.marinetraffic.com` | **Yes** | Live vessel positions |

---

## API KEYS

### Shodan — `Shodan_API.txt`

**What it does:** Shodan continuously scans the public internet and indexes every device it finds — servers, routers, webcams, industrial control systems, anything with an open port. Your API key unlocks the full intelligence section of SIGNAL.

**Get a key:** https://account.shodan.io — free accounts work. Paid plans unlock community search queries and higher credit limits.

```bash
echo "abc123yourkeyhere" > Shodan_API.txt
```

**Features unlocked:**

| Tool | What it does |
|---|---|
| **Quick Search** | Auto-detects input: IP → Host Lookup, CVE → Exploit DB, anything else → Search |
| **Host Lookup** | Full port/service/banner/CVE breakdown for any IP address |
| **Search** | Full Shodan query language with facets (country, org, port, ASN) |
| **Count** | Count matching hosts without spending query credits |
| **DNS Tools** | Forward resolve, reverse DNS, subdomain enumeration |
| **Exploit DB** | Search `exploits.shodan.io` by CVE, product, or keyword |
| **Network Alerts** | Monitor IP ranges for new open ports or vulnerabilities |
| **On-Demand Scan** | Request a rescan of specific IPs (costs scan credits) |
| **Community Queries** | Browse the shared query directory (paid plans) |

> **Free vs paid:** The dashboard detects your plan automatically. Features unavailable on your tier are silently skipped — no errors, no crashes.

**Diagnostic endpoint:** `http://localhost:5000/api/shodan/test`  
Returns your plan, credit balance, and confirms the key loaded correctly.

---

### FlightRadar24 — `FL24_API.txt`

**What it does:** FlightRadar24 tracks commercial and private aircraft in real time via ADS-B receivers worldwide. The SIGNAL integration uses the official FR24 API (not scraping) to pull live flight positions, route data, and aircraft details.

**Get a key:** https://fr24api.flightradar24.com — requires a paid FR24 subscription with API access.  
The token is a **Bearer token**, not a simple API key — paste the full token string into the file.

```bash
echo "your_bearer_token_here" > FL24_API.txt
```

**Features unlocked:**

| Tool | What it does |
|---|---|
| **Live Flights panel** | Up to 50 live flights with callsign, route, altitude, speed, heading |
| **Filter by airline** | Filter live view by airline ICAO code (UAL, DAL, BAW…) |
| **Filter by aircraft** | Filter live view by aircraft type (B738, A320, B77W…) |
| **Flight Lookup** | Full details + track for a specific FR24 flight ID or callsign |
| **Airport View** | Live arrivals and departures for any airport by IATA code |

> Without a key, the panel displays realistic demo data with a `DEMO` indicator. All other dashboard feeds continue to work normally.

---

### Marine Traffic — `MT_API.txt`

**What it does:** MarineTraffic tracks vessels worldwide via AIS (Automatic Identification System) receivers on shore stations and satellites. The integration surfaces live vessel positions, port arrivals, and voyage history.

**Get a key:** https://www.marinetraffic.com/en/users/api — paid API plans required.  
The key goes directly in the URL path per MarineTraffic's API convention — just paste the raw key string.

```bash
echo "your_marinetraffic_key" > MT_API.txt
```

**Features unlocked:**

| Tool | What it does |
|---|---|
| **Live Vessels panel** | Active vessel positions with name, type, flag, destination, speed |
| **Filter by type** | Filter by vessel class: Cargo, Tanker, Passenger, Fishing, Tug, Military |
| **Vessel Lookup** | Full vessel record by MMSI number |
| **Port Call History** | Full port call history for a vessel (by MMSI) |
| **Expected Arrivals** | Vessels expected at a port by UNLOCODE (e.g. `NLRTM`, `USLAX`) |
| **Vessel Search** | Search by vessel name, MMSI, or IMO number |

> Without a key, the panel displays realistic demo data with a `DEMO` indicator.

---

## DIAGNOSTICS

```bash
# Check all API key status + file paths
curl http://localhost:5000/api/keys

# Test Shodan key specifically (shows plan + credits)
curl http://localhost:5000/api/shodan/test

# Full health check (all external APIs + key status)
curl http://localhost:5000/api/healthcheck

# Browse all registered feeds
curl http://localhost:5000/api/feeds

# Fetch a specific feed directly
curl http://localhost:5000/api/feed/shodan
curl http://localhost:5000/api/feed/flightradar
curl http://localhost:5000/api/feed/earthquakes
```

---

## TROUBLESHOOTING

**503 from Shodan after adding key**  
The most common cause is the `/shodan/query` community endpoint returning `402 Payment Required` on free-tier keys. SIGNAL v4.0 silently skips this call — if you're still seeing 503s, run the diagnostic endpoint and check the error field:
```bash
curl http://localhost:5000/api/shodan/test
```

**Key loaded but SIGNAL shows "KEY NOT LOADED"**  
The key file may have been saved with a Windows line ending (`\r\n`) or a UTF-8 BOM. SIGNAL strips these automatically on load, but verify the startup log in your terminal:
```
[SIGNAL] Shodan_API.txt: key loaded (abcd…wxyz)
```
If you see `file exists but is empty`, the file was saved blank. Re-paste the key and ensure no extra whitespace.

**Key file not found**  
SIGNAL resolves key files relative to `SIGNAL.py` — not to your current working directory. If you launch from a different folder:
```bash
# Wrong — keys won't resolve
cd /some/other/folder && python /path/to/signal/SIGNAL.py

# Correct
cd /path/to/signal && python SIGNAL.py
```

**Port 5000 already in use**  
Edit the last line of `SIGNAL.py`:
```python
app.run(debug=False, port=5001, threaded=True)  # change port here
```

**Flask not installed**  
```bash
pip install flask
# or, if you have multiple Python versions:
pip3 install flask
python3 SIGNAL.py
```

---

## ARCHITECTURE

```
SIGNAL.py
├── load_key()            # BOM-safe key loader, resolves to script dir
├── _http_get/post()      # Shared HTTP layer with SSL fallback + error decoding
├── shodan_get/post()     # Shodan-authenticated wrappers, surfaces JSON errors
├── fr24_get()            # FR24 Bearer-auth wrapper
├── mt_get()              # MarineTraffic key-in-path wrapper
│
├── fetch_*()             # One per feed — always returns valid JSON, never throws
│
├── FEEDS{}               # Registry: id → {fn, label, source, color}
│
├── /                     # Serves templates/index.html
├── /api/feeds            # Feed registry (used to populate dropdowns)
├── /api/feed/<id>        # Generic feed fetcher
├── /api/keys             # Key status + file paths
├── /api/healthcheck      # External API reachability + key status
│
├── /api/shodan/*         # 12 Shodan interactive routes
├── /api/flightradar/*    # 3 FR24 interactive routes
└── /api/marinetraffic/*  # 5 MarineTraffic interactive routes
```

The frontend (`index.html`) is a single file with embedded CSS and JS. It fetches from the routes above and renders everything client-side. No framework, no bundler.

---

## NOTES

- **No data is stored.** SIGNAL fetches, renders, and discards. There is no database, no logging of results, no caching layer.
- **Auto-refresh** fires every 90 seconds for all three panel feeds. The Shodan, FR24, and Marine sections refresh on demand only (manual button).
- **Demo mode** is always available. Every feed with a missing or invalid key falls back to realistic static data. The ticker, panels, and summary bar all populate normally.
- **Threaded Flask** (`threaded=True`) means multiple panel refreshes won't block each other. For production use, put a proper WSGI server (gunicorn, waitress) in front.

---

```
SIGNAL v4.0  ·  python SIGNAL.py  ·  http://localhost:5000
```
