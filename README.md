# indeedb

This repository contains a Selenium script that automatically applies to

3. The script launches Chrome using your existing profile (edit the `USER_DATA_DIR`
   and `PROFILE_DIR` constants in `indeed_easy_apply.py` if needed). Ensure
   you're already logged in to Indeed in that profile. When the browser opens the
   bot prints `[Using existing Chrome session. Please ensure you're logged in.]`
   and waits until the search field appears before continuing.

The script uses your existing Chrome profile for authentication. If Chrome is
installed in a different location or you use another profile, update the
`USER_DATA_DIR` and `PROFILE_DIR` constants at the top of `indeed_easy_apply.py`.
1. Install dependencies:
   ```bash

   pip install selenium undetected-chromedriver win10toast

   ```
2. Run the script for the first time to create `config.json`. The program will
   prompt you for your settings and save them for future runs. You can choose to
   update them each time the script starts.

3. When the browser opens, click **Continue with Google** and log in manually.
   Solve any CAPTCHA that appears. The bot prints
   `[Please log in manually with your Google account and solve the CAPTCHA]` and
   waits up to two minutes. Once the job search field is detected, it prints
   `[Login successful - continuing bot]`. Cookies are saved so future runs can
   skip this step.
4. Run the script:

   ```bash
   python indeed_easy_apply.py
   ```
  Windows users can run `run_easy_apply.bat` instead.

Each application attempt is logged to the CSV file specified by `log_path`.
During the application process the bot makes a best effort to complete extra
form fields such as text inputs, dropdowns, radios and checkboxes with default
values. Unsupported fields are skipped safely.

Example `config.json`:
```json
{
  "resume_path": "C:/Users/You/Documents/resume.pdf",
  "search_keywords": "Software Engineer",
  "min_salary": 17,
  "locations": ["Pawtucket, RI", "Providence, RI", "Cranston, RI", "Lincoln, RI"],
  "max_applications": 50,
  "log_path": "applied_jobs_log.csv"
}
```

