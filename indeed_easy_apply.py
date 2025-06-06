import csv
import json
import os
import re
import time
from datetime import datetime


import logging
import undetected_chromedriver as uc
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

try:
    from win10toast import ToastNotifier
except ImportError:  # pragma: no cover - optional dependency
    ToastNotifier = None

CONFIG_PATH = "config.json"
APPLIED_JOBS_PATH = "applied_jobs.txt"
WAIT_TIME = 20
LOGIN_CHECK_WAIT = 120
# Path to your Chrome user data directory and profile
USER_DATA_DIR = "C:/Users/Jesse/AppData/Local/Google/Chrome/User Data"
PROFILE_DIR = "Profile 1"

GEOLOCATOR = Nominatim(user_agent="indeed-bot")


def save_config(cfg: dict, path: str = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def prompt_for_config() -> dict:
    print("[Config setup]")
    cfg = {
        "resume_path": input("Path to resume PDF: ").strip(),
        "min_salary": float(input("Minimum hourly wage (e.g. 17): ").strip() or "17"),
        "locations": [loc.strip() for loc in input("Locations (comma separated): ").split(",") if loc.strip()],
        "user_address": input("Your home address: ").strip(),

        "max_applications": int(input("Maximum applications: ").strip() or "50"),
        "log_path": input("Log CSV path: ").strip() or "applied_jobs_log.csv",
    }
    return cfg


def load_config(path: str = CONFIG_PATH) -> dict:
    """Load configuration or interactively prompt on first run."""
    if not os.path.exists(path):
        cfg = prompt_for_config()
        save_config(cfg, path)
        return cfg
    with open(path, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    choice = input("Use existing configuration? (Y/n): ").strip().lower()
    if choice == "n":
        cfg = prompt_for_config()
        save_config(cfg, path)
    return cfg


def setup_driver() -> uc.Chrome:
    """Return a Chrome WebDriver using the existing user profile."""
    options = uc.ChromeOptions()
    options.add_argument(f"--user-data-dir={USER_DATA_DIR}")
    options.add_argument(f"--profile-directory={PROFILE_DIR}")
    options.add_argument("--start-maximized")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options)
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)
    return driver


def ensure_logged_in(driver: uc.Chrome) -> None:
    """Open Indeed using the existing Chrome session and wait for login."""
    driver.get("https://www.indeed.com")
    print("[Using Chrome profile. Please confirm you're logged in.]")
    WebDriverWait(driver, LOGIN_CHECK_WAIT).until(
        EC.presence_of_element_located((By.ID, "text-input-what"))
    )
    print("[Login successful - continuing bot]")




def search_jobs_for_city(driver: uc.Chrome, city: str) -> None:
    """Search Indeed for any jobs in a specific city."""
    print(f"[Searching in {city}]")
    driver.get("https://www.indeed.com")
    wait = WebDriverWait(driver, WAIT_TIME)
    what = wait.until(EC.element_to_be_clickable((By.ID, "text-input-what")))
    where = driver.find_element(By.ID, "text-input-where")
    what.clear()

    where.clear()
    where.send_keys(city)
    where.send_keys(Keys.RETURN)
    wait.until(EC.presence_of_element_located((By.ID, "resultsCol")))


def load_applied_jobs(path: str = APPLIED_JOBS_PATH) -> set[str]:
    if not os.path.exists(path):
        return set()
    with open(path, "r", encoding="utf-8") as f:
        return set(line.strip() for line in f if line.strip())


def save_applied_job(job_id: str, path: str = APPLIED_JOBS_PATH) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(job_id + "\n")


def save_log(path: str, data: dict) -> None:
    file_exists = os.path.isfile(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "timestamp",
                "job_title",
                "company",
                "city",
                "distance",
                "status",
            ],
        )
        if not file_exists:
            writer.writeheader()
        writer.writerow(data)




def parse_salary(text: str) -> float | None:
    """Return the numeric lower bound of a salary string."""
    numbers = re.findall(r"\$([\d,.]+)", text)
    if not numbers:
        return None
    try:
        return float(numbers[0].replace(",", ""))
    except ValueError:
        return None


def is_valid_job_type(page_text: str) -> bool:
    text = page_text.lower()
    if any(word in text for word in ["contract", "temporary", "internship"]):
        return False
    return "full-time" in text or "part-time" in text


def meets_salary_requirement(text: str, minimum: float) -> bool:
    salary = parse_salary(text)
    return salary is not None and salary >= minimum


def geocode(address: str):
    """Return (lat, lon) for an address if possible."""
    try:
        loc = GEOLOCATOR.geocode(address)
        if loc:
            return (loc.latitude, loc.longitude)
    except Exception as exc:  # pragma: no cover - network issues
        print(f"[Geocoding error: {exc}]")
    return None


def calculate_distance(addr1: str, addr2: str) -> float | None:
    """Return distance in miles between two addresses."""
    loc1 = geocode(addr1)
    loc2 = geocode(addr2)
    if not loc1 or not loc2:
        return None
    return round(geodesic(loc1, loc2).miles, 1)



def extract_salary(driver: uc.Chrome) -> str | None:
    try:
        el = driver.find_element(By.CSS_SELECTOR, ".salary-snippet")
        return el.text
    except Exception:
        return None



def extract_job_type(driver: uc.Chrome) -> str | None:
    """Return the job type text if available."""
    try:
        key = driver.find_element(
            By.XPATH,
            "//*[contains(text(),'Job Type') or contains(text(),'Job type')]/following-sibling::*",
        )
        return key.text
    except Exception:
        # fallback to scanning page text
        page = driver.page_source.lower()
        for word in ["full-time", "part-time", "contract", "temporary", "internship"]:
            if word in page:
                return word
        return None


def extract_location(driver: uc.Chrome) -> str | None:
    """Return job location text if possible."""
    selectors = [
        ".jobsearch-JobInfoHeader-subtitle div",
        ".jobsearch-DesktopStickyContainer-subtitle div",
        ".companyLocation",
    ]
    for sel in selectors:
        try:
            loc = driver.find_element(By.CSS_SELECTOR, sel).text
            if loc:
                return loc
        except Exception:
            continue
    return None



def fill_additional_fields(driver: uc.Chrome) -> None:
    """Handle common form fields during applications."""
    # Text inputs and textareas
    fields = driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='tel'], textarea, input:not([type])")
    for field in fields:
        try:
            if not field.is_displayed() or not field.is_enabled() or field.get_attribute("value"):
                continue
            placeholder = field.get_attribute("aria-label") or field.get_attribute("placeholder") or field.get_attribute("name") or "input"
            print(f"[Filling input: {placeholder}]")
            field.clear()
            if field.get_attribute("type") == "tel":
                field.send_keys("555-555-5555")
            else:
                field.send_keys("N/A")
        except Exception:
            print("[Unknown form element skipped]")

    # Dropdowns
    selects = driver.find_elements(By.TAG_NAME, "select")
    for select in selects:
        try:
            if not select.is_displayed() or not select.is_enabled():
                continue
            label = select.get_attribute("aria-label") or select.get_attribute("name") or "dropdown"
            print(f"[Selecting from dropdown: {label}]")
            options = select.find_elements(By.TAG_NAME, "option")
            for option in options:
                if option.get_attribute("value") and not option.get_attribute("disabled"):
                    option.click()
                    break
        except Exception:
            print("[Unknown form element skipped]")

    # Radio buttons
    radios = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
    grouped: dict[str, list] = {}
    for radio in radios:
        if not radio.is_displayed() or not radio.is_enabled():
            continue
        grouped.setdefault(radio.get_attribute("name"), []).append(radio)
    for name, group in grouped.items():
        try:
            label = name or "radio"
            choice = None
            for r in group:
                lab = (r.get_attribute("aria-label") or "").lower()
                if "yes" in lab:
                    choice = r
                    break
            if not choice:
                choice = group[0]
            print(f"[Selecting radio option: {label}]")
            choice.click()
        except Exception:
            print("[Unknown form element skipped]")

    # Required checkboxes
    checkboxes = driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
    for box in checkboxes:
        try:
            if not box.is_displayed() or not box.is_enabled() or box.is_selected():
                continue
            if box.get_attribute("required") or box.get_attribute("aria-required"):
                label = box.get_attribute("aria-label") or box.get_attribute("name") or "checkbox"
                print(f"[Checking checkbox: {label}]")
                box.click()
        except Exception:
            print("[Unknown form element skipped]")


def get_easy_apply_jobs(driver: uc.Chrome, seen: set[str], cfg: dict) -> list[dict]:
    jobs: list[dict] = []
    elements = driver.find_elements(
        By.XPATH, "//span[contains(text(),'Easily apply')]/ancestor::a[@data-jk]"
    )
    for el in elements:
        jid = el.get_attribute("data-jk")
        if not jid:
            continue
        if jid in seen:
            print(f"[Skipping previously applied job: {jid}]")
            continue
        try:
            company = el.find_element(By.CSS_SELECTOR, ".companyName").text
        except Exception:
            company = ""
        try:
            loc = el.find_element(By.CSS_SELECTOR, ".companyLocation").text
        except Exception:
            loc = ""
        if loc and loc not in cfg["locations"]:
            print("[Skipping job - outside target cities]")
            continue
        jobs.append(
            {
                "id": jid,
                "link": el.get_attribute("href"),
                "title": el.text.strip().split("\n")[0],
                "company": company,
                "location": loc,
            }
        )
    return jobs


def apply_to_job(
    driver: uc.Chrome, job: dict, city: str, cfg: dict
) -> tuple[str, float | None]:
    """Attempt to apply to a job and return (status, distance)."""
    link = job["link"]
    print(f"[Evaluating: {job['title']} at {job['company']}]")
    driver.execute_script("window.open(arguments[0], '_blank');", link)
    driver.switch_to.window(driver.window_handles[-1])
    wait = WebDriverWait(driver, WAIT_TIME)
    status = "Skipped"
    distance = None

    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        job_type = extract_job_type(driver)
        if job_type is None or job_type.lower() not in {"full-time", "part-time"}:
            skip_type = job_type if job_type else "Unknown"
            print(f"[Skipping job - type is {skip_type}]")
            return status, distance
        salary_text = extract_salary(driver)
        if not salary_text:
            print("[Skipping job - salary not listed]")
            return status, distance
        if not meets_salary_requirement(salary_text, cfg["min_salary"]):
            print("[Skipping job - salary too low]")
            return status, distance
        job_location = extract_location(driver) or job["location"]
        if job_location:
            distance = calculate_distance(cfg.get("user_address", ""), job_location)
            if distance is not None:
                print(f"[Distance to job: {distance} miles]")

        print("[Criteria met - applying now]")
        apply_button = wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//button[contains(., 'Apply') or contains(., 'Submit')]")
            )
        )
        apply_button.click()
        try:
            file_input = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
            )
            print("[Uploading resume...]")
            file_input.send_keys(cfg["resume_path"])
        except Exception:
            pass

        # Handle common form elements before final submission
        fill_additional_fields(driver)

        try:
            submit_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Submit')]")
            ))
            submit_btn.click()
            wait.until(
                EC.presence_of_element_located(
                    (
                        By.XPATH,
                        "//*[contains(text(),'application has been submitted') or contains(text(),'applied') or contains(text(),'Thank you')]",
                    )
                )
            )
            status = "Applied"
        except Exception as exc:  # noqa: PERF203
            status = "Error"
            print(f"Error submitting application: {exc}")
        if status == "Applied":
            dist_msg = f" ({distance} miles)" if distance is not None else ""
            if ToastNotifier:
                ToastNotifier().show_toast(
                    "Indeed Bot: Application Sent",
                    f"{job['title']} at {job['company']} - {distance} mi away" if distance is not None else f"{job['title']} at {job['company']}",
                    duration=5,
                    threaded=True,
                )
            print(f"[Application sent: {job['title']} at {job['company']}{dist_msg}]")

            print("[Application complete]")
    except Exception as exc:
        status = "Error"
        print(f"[Error: {exc}]")
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    return status, distance



def main() -> None:
    print("[Starting Indeed bot]")
    cfg = load_config()
    applied_jobs = load_applied_jobs()
    driver = setup_driver()
    log_path = cfg.get("log_path", "applied_jobs_log.csv")
    max_apps = cfg.get("max_applications", 50)
    count = 0
    print(f"[Remaining applications: {max_apps - count}/{max_apps}]")
    try:
        ensure_logged_in(driver)
        for city in cfg["locations"]:
            if count >= max_apps:
                break
            search_jobs_for_city(driver, city)

            while count < max_apps:
                jobs = get_easy_apply_jobs(driver, applied_jobs, cfg)
                if not jobs:
                    break
                for job in jobs:
                    if count >= max_apps:
                        break
                    status, dist = apply_to_job(driver, job, city, cfg)

                    if status == "Applied":
                        applied_jobs.add(job["id"])
                        save_applied_job(job["id"])
                        count += 1
                    print(f"[Remaining applications: {max_apps - count}/{max_apps}]")

                    save_log(
                        log_path,
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "job_title": job["title"],
                            "company": job["company"],
                            "city": city,
                            "distance": dist,

                            "status": status,
                        },
                    )
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
