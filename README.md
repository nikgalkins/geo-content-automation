# 🗺️ Geo Content Automation Scripts
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Selenium](https://img.shields.io/badge/Selenium-4.x-brightgreen)
![GCP](https://img.shields.io/badge/GCP-Sheets%20API-orange)
![OSM](https://img.shields.io/badge/OpenStreetMap-API-success)

Automation toolkit for managing **geo-related content** – ski lifts, regions, POIs – using data from **Google Sheets** and **OpenStreetMap**.  
The scripts are used to enrich and validate hotel / region data and to automate actions in **Django Admin**.

> **Stack:** Python • Selenium • Google Sheets API (GCP) • Nominatim / OSM • Google Maps Geocoding • dotenv

---

## 📁 Repository structure
```text
automatization-scripts/
│
├── GCP JSON/                      # Service account JSON (NOT in Git)
│   └── geo-content-automatization-*.json
│
├── no_polygons/                   # Scripts for regions without polygons
│   ├── .env.polygons             # Local env (ignored)
│   ├── .env.polygons.example     # Example env for this folder
│   ├── id_searches.py            # Fetch region meta from Django Admin → Sheets
│   └── OSM_fetching.py           # Geocode regions via Nominatim + Google Maps
│
├── ski_lifts/                     # Ski lifts & Django Admin automation
│   ├── .env.ski_lifts            # Local env (ignored)
│   ├── .env.ski_lifts.example    # Example env for ski_lifts scripts
│   ├── admin_upload_from_sheet.py    # Upload POIs / lifts to Django Admin
│   ├── catedral_lifts_from_osm.py    # Catedral Alta Patagonia (AR)
│   ├── garmisch_lifts_from_osm.py    # Garmisch-Partenkirchen (DE)
│   ├── gudauri_lifts_from_osm.py     # Gudauri (GE)
│   └── shymbulak_lifts_from_osm.py   # Shymbulak (KZ)
│
├── slugs/
│   └── slugs_regions_parsing.py  # Resolve region slugs → IDs / names → Sheets
│
├── venv/                         # Local virtualenv (ignored)
├── requirements.txt
└── README.md
```

---

## 🔧 Requirements

- **Python 3.10+**
- **Google Cloud project with:**
  - Google Sheets API enabled
  - service account JSON with edit access
- **Chrome + chromedriver** (for Selenium-based scripts)

## ⚙️ Installation
```bash
git clone git@github.com:nikgalkins/automatization-scripts.git
cd automatization-scripts

python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux / macOS:
# source venv/bin/activate

pip install -r requirements.txt
```

---

## 🔐 Environment configuration

This project uses folder-specific env files.
Real env files are NOT committed; only `*.example` templates are in Git.

1. ski_lifts/.env.ski_lifts

Used by Selenium scripts in ski_lifts/ (Chrome + Django Admin).

Create from template:

```bash
cd ski_lifts
cp .env.ski_lifts.example .env.ski_lifts
```

Fill in values:

```bash
# === ski_lifts Selenium automation ===

# ---- Chrome / Selenium ----
CHROME_BINARY=C:/chrome-win64/chrome.exe
USER_DATA_DIR=C:/Users/USERNAME/AppData/Local/Google/Chrome for Testing/User Data
CHROMEDRIVER=C:/chromedriver-win64/chromedriver.exe

# ---- Google Service Account ----
SERVICE_ACCOUNT_FILE=GCP JSON/geo-content-automatization-XXXXX.json

# ---- Django Admin ----
ADMIN_URL_ADD=https://content.ostrovok.in/admin/geo/region/add/
PARENT_SEARCH_TEXT=
PARENT_VISIBLE_TEXT=
TYPE_VISIBLE_TEXT=

# ---- Optional toggles ----
DRY_RUN=0
HEADLESS=0
KEEP_BROWSER_OPEN=1
```

Each Selenium-based script in ski_lifts/ calls:

```python
load_dotenv(BASE_DIR / ".env.ski_lifts")
```

so these variables become available via os.getenv(...).

2. no_polygons/.env.polygons

Used by scripts that work with regions without polygons.

Create from template:
```bash
cd no_polygons
cp .env.polygons.example .env.polygons
```

Fill in your credentials:

```bash
# === no_polygons configuration ===

# Google Maps Geocoding API key
GOOGLE_MAPS_API_KEY=YOUR_GOOGLE_MAPS_API_KEY

# Google Service Account JSON path
SERVICE_ACCOUNT_FILE=GCP JSON/geo-content-automatization-XXXXX.json
```

OSM_fetching.py loads it via:

```bash
load_dotenv(BASE_DIR / ".env.polygons")
```

## 🏔️ ski_lifts scripts

### 1. Fetch lifts from OSM

Each script (*_lifts_from_osm.py) reads lift names / metadata from Google Sheets, calls Nominatim / Overpass, and writes back lat/lon & OSM IDs.

Run (example):

```bash
python ski_lifts/gudauri_lifts_from_osm.py
python ski_lifts/catedral_lifts_from_osm.py
python ski_lifts/garmisch_lifts_from_osm.py
python ski_lifts/shymbulak_lifts_from_osm.py
```

**Requires:**
- configured Google Sheet (spreadsheet & worksheet name set inside script)
- service account JSON with edit access

### 2. Upload POIs / lifts to Django Admin

admin_upload_from_sheet.py reads data from Google Sheets and creates regions / POIs in Django Admin using Selenium.

Basic usage:

```bash
python ski_lifts/admin_upload_from_sheet.py
```

The behavior is controlled mostly by .env.ski_lifts:

ADMIN_URL_ADD – URL of the "Add region" page

PARENT_* – info about parent region

TYPE_VISIBLE_TEXT – region type (e.g. Point of Interest)

DRY_RUN=1 – simulate, no actual form submission

HEADLESS=1 – run Chrome in headless mode

### 🧩 no_polygons scripts

Scripts for regions that have no polygon in OSM and need manual / point-based geometry.

### 1. id_searches.py

Reads region IDs from a Google Sheet (A column)

For each ID opens Django Admin /admin/geo/region/<id>/change/

Extracts:
- Region name
- Parent name & parent ID
- Country code
- Manual latitude / longitude

Writes a table back to Google Sheets, starting at A1.

Run:

```bash
python no_polygons/id_searches.py
```

### 2. OSM_fetching.py

Reads city and parent region from columns B and C

For each row:

Geocodes city, parent via Nominatim

Optionally gets Russian name via Google Maps Geocoding API

Writes:
- Latitude / longitude
- OSM ID / type / class / geometry
- Bounding box (west/south/east/north)
- Russian name

Output is written to columns H–S.

Run:

```bash
python no_polygons/OSM_fetching.py
```

### 🔤 slugs scripts

#### slugs_regions_parsing.py

Resolves region slugs stored in Google Sheets into concrete region data:

slug → region ID

region name

country code

any other metadata defined in the script

Usage:

```bash
python slugs/slugs_regions_parsing.py
```

This script is helpful for:
- validating slugs
- migrating content between systems
- debugging missing / broken mappings

## 🧪 Development tips

Prefer running inside virtualenv:

```bash
.\venv\Scripts\activate
```

To keep Selenium windows open for debugging, set:

```bash
KEEP_BROWSER_OPEN=1
HEADLESS=0
```

To avoid accidental form submissions while testing:
```bash
DRY_RUN=1
```

---

## 🧠 Tech Stack

- **Python 3.10+**  
- **Selenium 4.x**  
- **gspread, oauth2client – Google Sheets API**
- **geopy (Nominatim), googlemaps – geocoding & reverse geocoding**  
- **python-dotenv – per-folder environment configuration**

---

## 👤 Author

**Nikita Galkin**  
Geo Content Automation Specialist  
📍 Batumi, Georgia  
🔗 [GitHub: nikgalkins](https://github.com/nikgalkins)

---

## 🪪 License

MIT License – for educational and portfolio use.
Production usage requires appropriate API credentials and legal access to admin systems.