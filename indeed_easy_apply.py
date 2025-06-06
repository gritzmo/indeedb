 (cd "$(git rev-parse --show-toplevel)" && git apply --3way <<'EOF' 
diff --git a//dev/null b/indeed_easy_apply.py
index 0000000000000000000000000000000000000000..14c9ca681ca75da13967d15b1b44ebaa03fb41dc 100644
--- a//dev/null
+++ b/indeed_easy_apply.py
@@ -0,0 +1,295 @@
+import json
+import csv
+import os
+import time
+from datetime import datetime
+
+from selenium import webdriver
+from selenium.webdriver.common.by import By
+from selenium.webdriver.common.keys import Keys
+from selenium.webdriver.support.ui import WebDriverWait
+from selenium.webdriver.support import expected_conditions as EC
+
+
+CONFIG_PATH = 'config.json'
+DEFAULT_APPLIED_JOBS_PATH = 'applied_jobs.txt'
+# Default timeout for waiting on elements
+WAIT_TIME = 20
+
+
+def save_config(cfg: dict, path: str = CONFIG_PATH) -> None:
+    """Save configuration to a JSON file."""
+    with open(path, 'w', encoding='utf-8') as f:
+        json.dump(cfg, f, indent=2)
+
+
+def _prompt(current: dict, key: str, message: str, default: str | None = None) -> str:
+    default_val = current.get(key, default)
+    prompt_msg = f"{message}"
+    if default_val not in [None, '']:
+        prompt_msg += f" [{default_val}]"
+    prompt_msg += ": "
+    response = input(prompt_msg).strip()
+    return response if response else str(default_val or '')
+
+
+def prompt_for_config(existing: dict | None = None) -> dict:
+    """Interactively ask the user for configuration values."""
+    if existing is None:
+        existing = {}
+    cfg: dict = {}
+
+    cfg['indeed_email'] = _prompt(existing, 'indeed_email', 'Indeed email')
+    cfg['indeed_password'] = _prompt(existing, 'indeed_password', 'Indeed password')
+    cfg['resume_path'] = _prompt(existing, 'resume_path', 'Path to resume file')
+    cfg['name'] = _prompt(existing, 'name', 'Full name')
+    cfg['phone'] = _prompt(existing, 'phone', 'Phone number')
+
+    search_existing = existing.get('search', {})
+    search: dict = {}
+    search['keywords'] = _prompt(search_existing, 'keywords', 'Job keywords')
+    search['location'] = _prompt(search_existing, 'location', 'Job location')
+    search['radius'] = _prompt(search_existing, 'radius', 'Radius miles', '25')
+    ft = _prompt(search_existing, 'full_time', 'Full time only? (y/n)', 'y')
+    search['full_time'] = ft.lower().startswith('y')
+    rm = _prompt(search_existing, 'remote', 'Remote only? (y/n)', 'n')
+    search['remote'] = rm.lower().startswith('y')
+    cfg['search'] = search
+
+    cfg['max_applications'] = int(_prompt(existing, 'max_applications',
+                                          'Max applications per run', '50'))
+    cfg['log_path'] = _prompt(existing, 'log_path', 'Log file path',
+                              'applied_jobs_log.csv')
+    cfg['applied_jobs_path'] = _prompt(
+        existing, 'applied_jobs_path', 'Applied jobs file',
+        DEFAULT_APPLIED_JOBS_PATH)
+
+    return cfg
+
+
+def load_config(path: str = CONFIG_PATH) -> dict:
+    """Load configuration, prompting the user if necessary."""
+    if os.path.exists(path):
+        with open(path, 'r', encoding='utf-8') as f:
+            cfg = json.load(f)
+        print(f"Loaded configuration from {path}.")
+        change = input("Do you want to edit these settings? (y/N): ").strip().lower()
+        if change == 'y':
+            cfg = prompt_for_config(cfg)
+            save_config(cfg, path)
+    else:
+        print(f"Configuration file '{path}' not found. Let's create one.")
+        cfg = prompt_for_config()
+        save_config(cfg, path)
+    return cfg
+
+
+def setup_driver() -> webdriver.Chrome:
+    """Setup Chrome WebDriver."""
+    options = webdriver.ChromeOptions()
+    options.add_argument('--start-maximized')
+    driver = webdriver.Chrome(options=options)
+    return driver
+
+
+def login(driver: webdriver.Chrome, email: str, password: str) -> None:
+    """Login to Indeed with given credentials."""
+    driver.get('https://secure.indeed.com/account/login')
+    wait = WebDriverWait(driver, WAIT_TIME)
+    # Wait for email field
+    email_field = wait.until(
+        EC.presence_of_element_located((By.ID, 'login-email-input'))
+    )
+    email_field.clear()
+    email_field.send_keys(email)
+
+    password_field = driver.find_element(By.ID, 'login-password-input')
+    password_field.clear()
+    password_field.send_keys(password)
+
+    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()
+
+    # Wait until login completes (e.g., profile avatar visible)
+    wait.until(EC.presence_of_element_located((By.ID, 'gnav-header-inner')))
+
+
+def search_jobs(driver: webdriver.Chrome, search_params: dict) -> None:
+    """Perform a job search using Indeed's search form."""
+    driver.get('https://www.indeed.com')
+    wait = WebDriverWait(driver, WAIT_TIME)
+
+    what_field = wait.until(
+        EC.presence_of_element_located((By.ID, 'text-input-what'))
+    )
+    where_field = driver.find_element(By.ID, 'text-input-where')
+
+    what_field.clear()
+    what_field.send_keys(search_params.get('keywords', ''))
+
+    where_field.clear()
+    where_field.send_keys(search_params.get('location', ''))
+    where_field.send_keys(Keys.RETURN)
+
+    # Wait for results to load
+    wait.until(EC.presence_of_element_located((By.ID, 'resultsCol')))
+
+    # Additional filters can be applied here if needed
+
+
+def load_applied_jobs(path: str = DEFAULT_APPLIED_JOBS_PATH) -> set:
+    if not os.path.exists(path):
+        return set()
+    with open(path, 'r', encoding='utf-8') as f:
+        return set(line.strip() for line in f if line.strip())
+
+
+def save_applied_job(job_id: str, path: str = DEFAULT_APPLIED_JOBS_PATH) -> None:
+    with open(path, 'a', encoding='utf-8') as f:
+        f.write(job_id + '\n')
+
+
+def save_log(log_path: str, data: dict) -> None:
+    """Append a row to the CSV log file."""
+    file_exists = os.path.isfile(log_path)
+    with open(log_path, 'a', newline='', encoding='utf-8') as csvfile:
+        fieldnames = ['timestamp', 'job_title', 'company', 'status']
+        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
+        if not file_exists:
+            writer.writeheader()
+        writer.writerow(data)
+
+
+def get_easy_apply_jobs(driver: webdriver.Chrome, seen_ids: set) -> list[dict]:
+    """Return list of new Easy Apply job info dictionaries."""
+    jobs = []
+    # Locate job cards that contain the "Easily apply" badge
+    elements = driver.find_elements(
+        By.XPATH,
+        "//span[contains(text(),'Easily apply')]/ancestor::a[@data-jk]",
+    )
+    for el in elements:
+        job_id = el.get_attribute('data-jk')
+        # Skip jobs we've already applied to
+        if not job_id or job_id in seen_ids:
+            continue
+        jobs.append({
+            'id': job_id,
+            'link': el.get_attribute('href'),
+            'title': el.text.strip().split('\n')[0],
+            'company': ''
+        })
+    return jobs
+
+
+def apply_to_job(driver: webdriver.Chrome, job_link: str, config: dict) -> bool:
+    """Open a job link and attempt to apply if possible."""
+    # Open job in a new tab so we can return to the results page later
+    driver.execute_script("window.open(arguments[0], '_blank');", job_link)
+    driver.switch_to.window(driver.window_handles[-1])
+    wait = WebDriverWait(driver, WAIT_TIME)
+    applied = False
+    try:
+        # Wait for a button that either says Apply or Submit
+        apply_btn = wait.until(
+            EC.element_to_be_clickable(
+                (By.XPATH, "//button[contains(., 'Apply') or contains(., 'Submit')]")
+            )
+        )
+        apply_btn.click()
+
+        # Upload resume if a file input is present
+        try:
+            file_input = wait.until(
+                EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
+            )
+            file_input.send_keys(config['resume_path'])
+        except Exception:
+            # Not all applications require a resume upload
+            pass
+
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