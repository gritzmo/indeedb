This repository contains a Selenium script that automatically applies to \
"Easily apply" jobs on Indeed. Configuration values such as login details, \
search keywords, allowed locations, and email notifications are stored in \
`config.json`.
2. Edit `config.json` with your Indeed credentials, SMTP details, search \
   keywords, and other settings.
3. Run the script:
   ```bash
   python indeed_easy_apply.py
   ```
   Windows users can run `run_easy_apply.bat` instead.
Each application attempt is logged to the CSV file specified by `log_path`.
+This repository contains a sample Selenium script for automatically applying to "Easily apply" jobs on Indeed. The script uses a configuration file (`config.json`) that is created on first run to store your credentials and search preferences. Each application attempt is logged to a CSV file.
+
+## Usage
+1. Install dependencies:
+   ```bash
+   pip install selenium
+   ```
+2. Run the script:
+    ```bash
+    python indeed_easy_apply.py
+    ```
+   On the first run you will be prompted to enter your Indeed credentials, personal details, and search parameters. These settings are saved to `config.json`. On subsequent runs you can choose to update them before the automation begins.
+
+   Windows users can launch the script via `run_easy_apply.bat`.
+
+   The configuration file will include paths for the application log and for the list of already applied jobs (`applied_jobs_path`).
 
EOF
)