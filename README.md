# indeedb

This repository contains a Selenium script that automatically applies to
"Easily apply" jobs on Indeed. Configuration values such as resume path,
allowed locations, and logging are stored in `config.json`.

## Usage
1. Install dependencies:
   ```bash
   pip install selenium win10toast geopy
   ```
2. Run the script for the first time to create `config.json`. The program will
   prompt you for your settings and save them for future runs. You can choose to
   update them each time the script starts.
3. The script launches Chrome using a dedicated profile directory defined by
   `USER_DATA_DIR` in `indeed_easy_apply.py`. When the browser opens, the bot
   checks for a "Sign in" link. If it's present, you'll see a prompt to log in
   manually, and the bot waits until the link disappears before continuing.
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
  "min_salary": 17,
  "locations": ["Pawtucket, RI", "Providence, RI", "Cranston, RI", "Lincoln, RI"],
  "user_address": "123 Main Street, Pawtucket, RI",
  "max_applications": 50,
  "log_path": "applied_jobs_log.csv"
}
```

The script stores its own Chrome user data in the folder defined by
`USER_DATA_DIR` at the top of `indeed_easy_apply.py`. If Chrome is installed in
a different location, edit that constant accordingly.
