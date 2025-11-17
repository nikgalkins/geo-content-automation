import os
import time
import logging
from pathlib import Path

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------------------------------------------------------------------
# Google Sheets configuration
# ---------------------------------------------------------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

CREDENTIALS_FILE = Path("GCP JSON") / "geo-content-automatization-7039378bbe60.json"

SPREADSHEET_NAME = "no_polygon"
SHEET_NAME = "17-11"

# ---------------------------------------------------------------------------
# Selenium / WebDriver configuration
# ---------------------------------------------------------------------------
CHROMEDRIVER_PATH = r"C:\chromedriver-win64\chromedriver.exe"
CHROME_BINARY_PATH = r"C:\chrome-win64\chrome.exe"
CHROME_USER_DATA_DIR = r"C:/Users/nikit/AppData/Local/Google/Chrome for Testing/User Data"

REMOTE_DEBUGGING_PORT = 9222
REGION_ADMIN_BASE_URL = "https://content.ostrovok.in/admin/geo/region/"

GOOGLE_PASSWORD = os.environ.get("GOOGLE_ACCOUNT_PASSWORD")
GOOGLE_IDENTIFIER = os.environ.get("GOOGLE_ACCOUNT_IDENTIFIER", "your-email@example.com")

KEEP_BROWSER_OPEN = True


def create_driver() -> webdriver.Chrome:
    """Create and configure a Chrome WebDriver instance."""
    options = webdriver.ChromeOptions()
    options.add_argument(f"--remote-debugging-port={REMOTE_DEBUGGING_PORT}")
    options.add_argument(f"--user-data-dir={CHROME_USER_DATA_DIR}")
    options.binary_location = CHROME_BINARY_PATH

    service = ChromeService(CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver


def login(driver: webdriver.Chrome) -> None:
    """
    Open the region admin page and perform login if required.
    Login is done via Keycloak + Google.
    """
    driver.get(f"{REGION_ADMIN_BASE_URL}")
    time.sleep(3)

    if "login" not in driver.current_url:
        logging.info("Already authenticated; login page not detected.")
        return

    logging.info("Authentication required. Starting login flow...")

    # Keycloak button
    keycloak_button = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable(
            (By.CSS_SELECTOR, "button.social_btn_2.keycloak_btn_2")
        )
    )
    keycloak_button.click()
    time.sleep(2)

    # Google account
    google_account_selector = f"div[data-identifier='{GOOGLE_IDENTIFIER}']"
    google_account = WebDriverWait(driver, 10).until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, google_account_selector))
    )
    google_account.click()
    time.sleep(2)

    # Password
    if not GOOGLE_PASSWORD:
        raise RuntimeError(
            "Environment variable GOOGLE_ACCOUNT_PASSWORD is not set. "
            "Please set it before running the script."
        )

    password_input = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.NAME, "Passwd"))
    )
    password_input.send_keys(GOOGLE_PASSWORD)

    next_button = driver.find_element(By.ID, "passwordNext")
    next_button.click()
    time.sleep(5)

    logging.info("Login flow finished.")


def get_ids_from_google_sheets():
    """
    Fetch region IDs from the first column of the configured Google Sheet.
    Only numeric strings are kept (digits only).
    """
    logging.info("Authorizing Google Sheets client...")
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        str(CREDENTIALS_FILE), SCOPE
    )
    client = gspread.authorize(creds)

    logging.info(f"Opening spreadsheet '{SPREADSHEET_NAME}' / sheet '{SHEET_NAME}'...")
    spreadsheet = client.open(SPREADSHEET_NAME)
    sheet = spreadsheet.worksheet(SHEET_NAME)

    raw_ids = sheet.col_values(1)
    ids = [value.strip() for value in raw_ids if value.strip().isdigit()]

    logging.info(f"Loaded {len(ids)} region IDs from Google Sheets.")
    return sheet, ids


def extract_region_data(driver: webdriver.Chrome, region_id: str):
    """
    Open the region admin page for a specific region ID and extract data.
    Returns:
        [region_id, region_name, parent_name, parent_id, country_code, latitude, longitude]
        or "Error" list if something goes wrong.
    """
    try:
        url = f"{REGION_ADMIN_BASE_URL}{region_id}/change/"
        logging.info(f"Opening region page: {url}")
        driver.get(url)

        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "id_translations-0-name"))
        )

        # Region name
        region_name = driver.find_element(
            By.ID, "id_translations-0-name"
        ).get_attribute("value")

        # ---------------- PARENT BLOCK ----------------
        parent_elem = driver.find_element(
            By.CSS_SELECTOR, "span.select2-selection__rendered"
        )

        parent_full_text = parent_elem.get_attribute("title") or parent_elem.text
        # Remove the leading "×" line and newlines
        parent_full_text = (
            parent_full_text.replace("×", "").replace("\n", " ").strip()
        )

        if parent_full_text:
            parent_parts = parent_full_text.split(", ")
            parent_id = parent_parts[0] if len(parent_parts) > 0 else ""
            parent_name = parent_parts[1] if len(parent_parts) > 1 else ""
        else:
            parent_id = ""
            parent_name = ""
        # -------------- END PARENT BLOCK --------------

        # ---------------- COUNTRY BLOCK ---------------
        # Grab the whole "Country" form-row and extract the last non-label line
        country_block = driver.find_element(
            By.CSS_SELECTOR, "div.form-row.field-country"
        )
        lines = [l.strip() for l in country_block.text.splitlines() if l.strip()]

        country_code = ""
        for line in reversed(lines):
            # Skip label-like lines (e.g. "Country:")
            if line.lower().startswith("country"):
                continue
            country_code = line
            break
        # -------------- END COUNTRY BLOCK -------------

        # Coordinates
        latitude = driver.find_element(
            By.ID, "id_manual_lat_center"
        ).get_attribute("value")
        longitude = driver.find_element(
            By.ID, "id_manual_lon_center"
        ).get_attribute("value")

        logging.info(
            f"Successfully processed region {region_id}: "
            f"{region_name}, {country_code}, parent={parent_name} ({parent_id})"
        )

        return [
            region_id,
            region_name,
            parent_name,
            parent_id,
            country_code,
            latitude,
            longitude,
        ]

    except Exception:
        logging.exception(f"Error while processing region ID {region_id}")
        return [region_id, "Error", "Error", "Error", "Error", "Error", "Error"]


def main():
    driver = create_driver()

    try:
        login(driver)
        sheet, ids = get_ids_from_google_sheets()

        data = [
            [
                "ID",
                "Region name",
                "Parent name",
                "Parent ID",
                "Country code",
                "Latitude",
                "Longitude",
            ]
        ]

        total = len(ids)
        for index, region_id in enumerate(ids, start=1):
            logging.info(f"Processing {index}/{total}: region ID {region_id}")
            row = extract_region_data(driver, region_id)
            data.append(row)

        logging.info("Updating Google Sheet with collected data...")
        # New API order: values first, then range_name
        sheet.update(values=data, range_name="A1")
        logging.info("Sheet update completed successfully.")

    finally:
        if KEEP_BROWSER_OPEN:
            input("Press Enter to close the script and keep the browser open...")
        else:
            driver.quit()


if __name__ == "__main__":
    main()
