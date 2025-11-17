from dotenv import load_dotenv
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env.polygons")

import time
import logging
import gspread
import googlemaps
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
from oauth2client.service_account import ServiceAccountCredentials

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------------------------------------------------------------------------
# Google Sheets configuration
# ---------------------------------------------------------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

# Path to service account JSON (take from env or use default path)
CREDENTIALS_FILE = os.environ.get(
    "GCP_SERVICE_ACCOUNT_FILE",
    "GCP JSON/geo-content-automatization-7039378bbe60.json",
)

SPREADSHEET_NAME = "no_polygon"
SHEET_NAME = "17-11"  # change if you need another sheet name

# ---------------------------------------------------------------------------
# Geocoders configuration
# ---------------------------------------------------------------------------
USER_AGENT = "geo_data_collector_nc (nikita.galkin@hotmail.com)"
geolocator = Nominatim(user_agent=USER_AGENT)

GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY")
if not GOOGLE_MAPS_API_KEY:
    raise RuntimeError(
        "Environment variable GOOGLE_MAPS_API_KEY is not set. "
        "Set it before running the script."
    )

gmaps = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

# ---------------------------------------------------------------------------
# Headers for output columns (starting from column H)
# ---------------------------------------------------------------------------
HEADERS = [
    "Latitude",
    "Longitude",
    "OSM_ID",
    "OSM_Type",
    "Class",
    "Type",
    "Geometry",
    "BBOX_West",
    "BBOX_South",
    "BBOX_East",
    "BBOX_North",
    "Russian_Name",
]

# H is column 8, so H..S = 12 columns
OUTPUT_RANGE_HEADER = "H1:S1"


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def geocode_with_retry(query: str, retries: int = 3, delay: int = 5):
    """
    Geocode a query using Nominatim with retry logic.
    """
    for attempt in range(retries):
        try:
            return geolocator.geocode(
                query,
                exactly_one=True,
                addressdetails=True,
                extratags=True,
                timeout=10,
            )
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            logging.warning(f"Retry {attempt + 1}/{retries} for '{query}' due to: {e}")
            time.sleep(delay)
        except Exception as e:
            logging.error(f"Unhandled error for '{query}': {e}")
            break
    return None


def get_russian_name(city_name: str) -> str:
    """
    Get Russian name for a city using Google Maps Geocoding API.
    """
    try:
        result = gmaps.geocode(city_name, language="ru")
        if result and "address_components" in result[0]:
            return result[0]["address_components"][0]["long_name"]
    except Exception as e:
        logging.error(f"Error getting Russian name for '{city_name}': {e}")
    return ""


def process_cities(sheet, cities, start_row: int):
    """
    Process a list of (city, province) pairs and write results to the sheet,
    starting from column H.
    """
    existing_headers = sheet.row_values(1)

    # If row 1 doesn't yet have enough columns for our headers, write them
    expected_min_columns = 7 + len(HEADERS)  # A..G existing + H..S our headers
    if len(existing_headers) < expected_min_columns:
        logging.info(f"Adding headers to columns {OUTPUT_RANGE_HEADER}")
        sheet.update(OUTPUT_RANGE_HEADER, [HEADERS])

    for i, (city, province) in enumerate(cities):
        row_num = start_row + i

        if province:
            search_query = f"{city}, {province}"
        else:
            search_query = city

        logging.info(f"Processing row {row_num}: {search_query}")

        # --- Nominatim geocoding ---
        location = geocode_with_retry(search_query)

        if location:
            try:
                raw = location.raw
                osm_id = raw.get("osm_id", "Not Found")
                osm_type = raw.get("osm_type", "Not Found")
                geo_class = raw.get("class", "Not Found")
                geo_type = raw.get("type", "Not Found")
                lat = str(location.latitude).replace(",", ".")
                lon = str(location.longitude).replace(",", ".")
                geometry = raw.get("geojson", {}).get("type", "Not Found")
                bbox = raw.get("boundingbox", ["Not Found"] * 4)
            except Exception as e:
                logging.error(f"Error parsing Nominatim response for '{search_query}': {e}")
                lat = lon = osm_id = osm_type = geo_class = geo_type = geometry = "Error"
                bbox = ["Error"] * 4
        else:
            lat = lon = osm_id = osm_type = geo_class = geo_type = geometry = "Not Found"
            bbox = ["Not Found"] * 4

        # --- Russian name via Google Maps ---
        russian_name = get_russian_name(city)
        logging.info(f"Russian name for '{city}': {russian_name}")

        # Prepare row for update (H..S = 12 columns)
        updated_row = [
            lat,
            lon,
            osm_id,
            osm_type,
            geo_class,
            geo_type,
            geometry,
            bbox[0],
            bbox[1],
            bbox[2],
            bbox[3],
            russian_name,
        ]

        # Update Google Sheet
        try:
            output_range_row = f"H{row_num}:S{row_num}"
            sheet.update(output_range_row, [updated_row])
            logging.info(f"Row {row_num} updated successfully.")
        except Exception as e:
            logging.error(f"Failed to update row {row_num}: {e}")

        # Be nice to Nominatim
        time.sleep(5)


def main():
    # --- Connect to Google Sheets ---
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            CREDENTIALS_FILE, SCOPE
        )
        client = gspread.authorize(creds)
        spreadsheet = client.open(SPREADSHEET_NAME)
        sheet = spreadsheet.worksheet(SHEET_NAME)
    except Exception as e:
        logging.critical(f"Google Sheets connection error: {e}")
        return

    # --- Read data from columns B and C ---
    try:
        rows = sheet.get_all_values()
        data_rows = rows[1:]  # skip header

        cities = []
        for row in data_rows:
            # Need at least columns A..C -> indices 0,1,2
            if len(row) >= 3:
                city = row[1].strip()      # column B: Region name
                province = row[2].strip()  # column C: Parent name
                if city:  # skip empty rows
                    cities.append((city, province))

        logging.info(f"Loaded {len(cities)} city/province pairs from columns B and C.")
    except Exception as e:
        logging.error(f"Error reading sheet data: {e}")
        return

    # --- Process and write results starting from column H ---
    process_cities(sheet, cities, start_row=2)

    logging.info("Google Sheet updated successfully!")


if __name__ == "__main__":
    main()
