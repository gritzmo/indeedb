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
   
3. When the browser opens, click **Continue with Google** and log in manually.
   Solve any CAPTCHA that appears. The bot prints
   `[Please log in manually with your Google account and solve the CAPTCHA]` and
   waits up to two minutes. Once the job search field is detected, it prints
   `[Login successful - continuing bot]`. Cookies are saved so future runs can
   skip this step.
4. Run the script:

