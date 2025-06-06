# indeedb

This repository contains a Selenium script that automatically applies to
"Easily apply" jobs on Indeed. Configuration values such as login details,
search keywords, allowed locations, and email notifications are stored in
`config.json`.

## Usage
1. Install dependencies:
   ```bash
   pip install selenium win10toast
   ```
2. Run the script for the first time to create `config.json`. The program will
   prompt you for your settings and save them for future runs. You can choose to
   update them each time the script starts.
3. When the browser opens, click **Continue with Google** and complete the login
   manually. The bot waits up to two minutes for you to finish and then
   continues automatically. Cookies are saved so future runs can skip this step.
4. Run the script:
   ```bash
   python indeed_easy_apply.py
   ```
  Windows users can run `run_easy_apply.bat` instead.

Each application attempt is logged to the CSV file specified by `log_path`.

Example `config.json`:
```json
{
  "indeed_email": "user@example.com",
  "indeed_password": "YourSecurePassword123",
  "resume_path": "C:/Users/You/Documents/resume.pdf",
  "search_keywords": "Software Engineer",
  "min_salary": 17,
  "locations": ["Pawtucket, RI", "Providence, RI", "Cranston, RI", "Lincoln, RI"],
  "max_applications": 50,
  "log_path": "applied_jobs_log.csv"
}
```
