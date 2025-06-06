# indeedb

This repository contains a sample Selenium script for automatically applying to "Easily apply" jobs on Indeed. The script reads configuration values from `config.json` and logs each application attempt to a CSV file.

## Usage
1. Install dependencies:
   ```bash
   pip install selenium
   ```
2. Edit `config.json` with your Indeed credentials and job search preferences.
3. Run the script:
   ```bash
   python indeed_easy_apply.py
   ```
