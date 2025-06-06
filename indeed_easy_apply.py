import json
import re
import smtplib
from email.message import EmailMessage
from selenium.webdriver.support.ui import WebDriverWait
CONFIG_PATH = "config.json"
APPLIED_JOBS_PATH = "applied_jobs.txt"
LOGIN_RETRIES = 3
    """Load configuration from JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
    """Return a maximized Chrome WebDriver."""
    options.add_argument("--start-maximized")
    return webdriver.Chrome(options=options)
    """Perform a single login attempt."""
    driver.get("https://secure.indeed.com/account/login")
    email_field = wait.until(EC.element_to_be_clickable((By.ID, "login-email-input")))
    pw_field = driver.find_element(By.ID, "login-password-input")
    pw_field.clear()
    pw_field.send_keys(password)
    driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
    # success when the global nav header loads
    wait.until(EC.presence_of_element_located((By.ID, "gnav-header-inner")))


def login_with_retry(driver: webdriver.Chrome, email: str, password: str, retries: int = LOGIN_RETRIES) -> None:
    """Attempt to log in multiple times before failing."""
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            login(driver, email, password)
            return
        except Exception as exc:  # noqa: PERF203
            last_error = exc
            print(f"Login attempt {attempt} failed: {exc}")
            time.sleep(2)
    raise RuntimeError("Unable to log in after multiple attempts") from last_error
def search_jobs_for_city(driver: webdriver.Chrome, keywords: str, city: str) -> None:
    """Search Indeed for keywords in a specific city."""
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
def send_email_notification(cfg: dict, title: str, company: str, city: str) -> None:
    msg = EmailMessage()
    msg["Subject"] = f"Indeed Bot: Applied to {title} at {company}"
    msg["From"] = cfg["smtp_username"]
    msg["To"] = cfg["notification_email"]
    msg.set_content(
        f"Your automated bot has successfully applied to {title} at {company} in {city} on {datetime.utcnow().isoformat()}."
    )
    try:
        with smtplib.SMTP(cfg["smtp_server"], cfg["smtp_port"]) as server:
            server.starttls()
            server.login(cfg["smtp_username"], cfg["smtp_password"])
            server.send_message(msg)
    except Exception as exc:
        print(f"Failed to send notification email: {exc}")


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
def extract_salary(driver: webdriver.Chrome) -> str | None:
    try:
        el = driver.find_element(By.CSS_SELECTOR, ".salary-snippet")
        return el.text
    except Exception:
        return None
def get_easy_apply_jobs(driver: webdriver.Chrome, seen: set[str]) -> list[dict]:
    jobs: list[dict] = []
        By.XPATH, "//span[contains(text(),'Easily apply')]/ancestor::a[@data-jk]"
        jid = el.get_attribute("data-jk")
        if not jid or jid in seen:
            "id": jid,
            "link": el.get_attribute("href"),
            "title": el.text.strip().split("\n")[0],
            "company": "",
def apply_to_job(
    driver: webdriver.Chrome, job: dict, city: str, cfg: dict
) -> str:
    """Attempt to apply to a job and return status string."""
    link = job["link"]
    driver.execute_script("window.open(arguments[0], '_blank');", link)
    status = "Skipped"
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        page_text = driver.page_source
        if not is_valid_job_type(page_text):
            status = "Skipped"
            return status
        salary_text = extract_salary(driver)
        if not salary_text or not meets_salary_requirement(salary_text, cfg["min_salary"]):
            status = "Skipped"
            return status
        apply_button = wait.until(
        apply_button.click()
            file_input.send_keys(cfg["resume_path"])
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
            status = "Applied"
        except Exception as exc:  # noqa: PERF203
            status = "Error"
            print(f"Error submitting application: {exc}")
        if status == "Applied":
            send_email_notification(cfg, job["title"], job["company"], city)
    except Exception as exc:
        status = "Error"
        print(f"Failed processing job {link}: {exc}")
    return status
def main() -> None:
    cfg = load_config()
    applied_jobs = load_applied_jobs()
    log_path = cfg.get("log_path", "applied_jobs_log.csv")
    max_apps = cfg.get("max_applications", 50)
    count = 0
        login_with_retry(driver, cfg["indeed_email"], cfg["indeed_password"])
        for city in cfg["locations"]:
            if count >= max_apps:
            search_jobs_for_city(driver, cfg["search_keywords"], city)
            while count < max_apps:
                jobs = get_easy_apply_jobs(driver, applied_jobs)
                if not jobs:
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
if __name__ == "__main__":
+        # Fill common application fields if present
+        for field_id, value in {
+            'applicant.name': config.get('name', ''),
+            'applicant.email': config.get('indeed_email', ''),
+            'applicant.phoneNumber': config.get('phone', ''),
+        }.items():
+            try:
+                input_el = driver.find_element(By.ID, field_id)
+                input_el.clear()
+                input_el.send_keys(value)
+            except Exception:
+                continue
+
+        # Submit the application
+        submit_btn = driver.find_element(By.XPATH, "//button[contains(., 'Submit')]")
+        submit_btn.click()
+
+        # Confirm the application was submitted before closing the tab
+        wait.until(
+            EC.presence_of_element_located(
+                (
+                    By.XPATH,
+                    "//*[contains(text(),'application has been submitted') or "
+                    "contains(text(),'applied') or contains(text(),'Thank you')]",
+                )
+            )
+        )
+        applied = True
+    except Exception as e:
+        print(f"Failed to apply for {job_link}: {e}")
+    finally:
+        driver.close()
+        # Return focus to the original search results tab
+        driver.switch_to.window(driver.window_handles[0])
+    return applied
+
+
+def main():
+    config = load_config()
+    applied_jobs_path = config.get('applied_jobs_path', DEFAULT_APPLIED_JOBS_PATH)
+    applied_jobs = load_applied_jobs(applied_jobs_path)
+    driver = setup_driver()
+    try:
+        login(driver, config['indeed_email'], config['indeed_password'])
+        search_jobs(driver, config['search'])
+
+        applied_count = 0
+        log_path = config.get('log_path', 'applied_jobs_log.csv')
+        max_applications = config.get('max_applications', 50)
+
+        while applied_count < max_applications:
+            # Collect new 'Easily apply' jobs on the current page
+            jobs = get_easy_apply_jobs(driver, applied_jobs)
+
+            if not jobs:
+                break
+
+            for job in jobs:
+                status = 'failed'
+                if apply_to_job(driver, job['link'], config):
+                    applied_jobs.add(job['id'])
+                    save_applied_job(job['id'], applied_jobs_path)
+                    status = 'applied'
+                    applied_count += 1
+
+                save_log(log_path, {
+                    'timestamp': datetime.utcnow().isoformat(),
+                    'job_title': job['title'],
+                    'company': job['company'],
+                    'status': status
+                })
+
+                if applied_count >= max_applications:
+                    break
+
+            # Scroll to load the next set of job cards
+            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
+            time.sleep(2)
+
+    finally:
+        # Close the browser when finished or on error
+        driver.quit()
+
+
+if __name__ == '__main__':
+    main()
 
EOF
)