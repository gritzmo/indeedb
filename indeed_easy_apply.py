import csv
import json
import os
import re
import time
from datetime import datetime

import logging
import undetected_chromedriver as uc
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
LOGIN_WAIT = 120
COOKIES_PATH = "cookies.json"


def save_config(cfg: dict, path: str = CONFIG_PATH) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


def prompt_for_config() -> dict:
    print("[Config setup]")
    cfg = {
        "resume_path": input("Path to resume PDF: ").strip(),
        "search_keywords": input("Search keywords: ").strip() or "Software Engineer",
        "min_salary": float(input("Minimum hourly wage (e.g. 17): ").strip() or "17"),
        "locations": [loc.strip() for loc in input("Locations (comma separated): ").split(",") if loc.strip()],
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
    """Return a maximized undetected Chrome WebDriver."""
    options = uc.ChromeOptions()
    options.add_argument("--start-maximized")
    driver = uc.Chrome(options=options)
    logging.getLogger("undetected_chromedriver").setLevel(logging.WARNING)
    return driver


def save_cookies(driver: uc.Chrome, path: str = COOKIES_PATH) -> None:
    """Persist browser cookies to a JSON file."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(driver.get_cookies(), f)
    except Exception:
        pass


def load_cookies(driver: uc.Chrome, path: str = COOKIES_PATH) -> bool:
    """Load cookies if available. Returns True when login is restored."""
    if not os.path.exists(path):
        return False
    try:
        driver.get("https://www.indeed.com")
        with open(path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        for cookie in cookies:
            driver.add_cookie(cookie)
        driver.refresh()
        WebDriverWait(driver, WAIT_TIME).until(
            EC.presence_of_element_located((By.ID, "text-input-what"))
        )
        print("[Login successful - continuing bot]")
        return True
    except Exception:
        return False


def manual_google_login(driver: uc.Chrome) -> None:
    """Prompt user to sign in with Google manually."""
    if load_cookies(driver):
        return

    driver.get("https://www.indeed.com")
    wait = WebDriverWait(driver, WAIT_TIME)
    try:
        sign_in = wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
        sign_in.click()
    except Exception:
        pass
    try:
        google_btn = WebDriverWait(driver, WAIT_TIME).until(
            EC.element_to_be_clickable(
                (
                    By.XPATH,
                    "//span[contains(text(),'Continue with Google')]/parent::button",
                )
            )
        )
        google_btn.click()
    except Exception:
        pass

    print("[Please log in manually with your Google account and solve the CAPTCHA]")
    WebDriverWait(driver, LOGIN_WAIT).until(
        EC.presence_of_element_located((By.ID, "text-input-what"))
    )
    print("[Login successful - continuing bot]")
    save_cookies(driver)




def search_jobs_for_city(driver: uc.Chrome, keywords: str, city: str) -> None:
    """Search Indeed for keywords in a specific city."""
    print(f"[Searching for '{keywords}' in {city}]")
    driver.get("https://www.indeed.com")
    wait = WebDriverWait(driver, WAIT_TIME)
    what = wait.until(EC.element_to_be_clickable((By.ID, "text-input-what")))
    where = driver.find_element(By.ID, "text-input-where")
    what.clear()
    what.send_keys(keywords)
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
            fieldnames=["timestamp", "job_title", "company", "city", "status"],
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
        if not jid or jid in seen:
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
) -> str:
    """Attempt to apply to a job and return status string."""
    link = job["link"]
    print(f"[Evaluating: {job['title']} at {job['company']}]")
    driver.execute_script("window.open(arguments[0], '_blank');", link)
    driver.switch_to.window(driver.window_handles[-1])
    wait = WebDriverWait(driver, WAIT_TIME)
    status = "Skipped"
    try:
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        job_type = extract_job_type(driver)
        if job_type is None or job_type.lower() not in {"full-time", "part-time"}:
            skip_type = job_type if job_type else "Unknown"
            print(f"[Skipping job - type is {skip_type}]")
            status = "Skipped"
            return status
        salary_text = extract_salary(driver)
        if not salary_text:
            print("[Skipping job - salary not listed]")
            status = "Skipped"
            return status
        if not meets_salary_requirement(salary_text, cfg["min_salary"]):
            print("[Skipping job - salary too low]")
            status = "Skipped"
            return status
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
            if ToastNotifier:
                ToastNotifier().show_toast(
                    "Indeed Bot: Application Sent",
                    f"{job['title']} at {job['company']} in {city}",
                    duration=5,
                    threaded=True,
                )
            print(f"[Application sent: {job['title']} at {job['company']} in {city}]")
            print("[Application complete]")
    except Exception as exc:
        status = "Error"
        print(f"[Error: {exc}]")
    finally:
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    return status


def main() -> None:
    print("[Starting Indeed bot]")
    cfg = load_config()
    applied_jobs = load_applied_jobs()
    driver = setup_driver()
    log_path = cfg.get("log_path", "applied_jobs_log.csv")
    max_apps = cfg.get("max_applications", 50)
    count = 0
    try:
        manual_google_login(driver)
        for city in cfg["locations"]:
            if count >= max_apps:
                break
            search_jobs_for_city(driver, cfg["search_keywords"], city)
            while count < max_apps:
                jobs = get_easy_apply_jobs(driver, applied_jobs, cfg)
                if not jobs:
                    break
                for job in jobs:
                    if count >= max_apps:
                        break
                    status = apply_to_job(driver, job, city, cfg)
                    if status == "Applied":
                        applied_jobs.add(job["id"])
                        save_applied_job(job["id"])
                        count += 1
                    save_log(
                        log_path,
                        {
                            "timestamp": datetime.utcnow().isoformat(),
                            "job_title": job["title"],
                            "company": job["company"],
                            "city": city,
                            "status": status,
                        },
                    )
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
