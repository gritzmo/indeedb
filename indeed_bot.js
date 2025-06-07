// Ethical Indeed automation bot using Puppeteer.
// This Node.js version mirrors the Python script's logic.

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const csv = require('csv');
const axios = require('axios');
const notifier = require('node-notifier');
const puppeteer = require('puppeteer-extra');
const StealthPlugin = require('puppeteer-extra-plugin-stealth');
puppeteer.use(StealthPlugin());

const CONFIG_PATH = path.resolve(__dirname, 'config.json');
const COOKIES_PATH = path.resolve(__dirname, 'cookies.json');
const APPLIED_JOBS_PATH = path.resolve(__dirname, 'applied_jobs.txt');

// Utility to prompt the user from the console
function prompt(question) {
  const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
  return new Promise((resolve) => rl.question(question, (ans) => { rl.close(); resolve(ans); }));
}

// Randomized delay to mimic human pauses
async function humanDelay(min = 1000, max = 3000) {
  const time = Math.random() * (max - min) + min;
  await new Promise((r) => setTimeout(r, time));
}

function sendNotification(title, message) {
  try {
    notifier.notify({ title, message, timeout: 5 });
  } catch (e) {
    // best effort, non-fatal
  }
}

function loadConfig() {
  if (!fs.existsSync(CONFIG_PATH)) throw new Error('config.json missing');
  return JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
}

async function saveCookies(page) {
  const cookies = await page.cookies();
  fs.writeFileSync(COOKIES_PATH, JSON.stringify(cookies, null, 2));
}

async function loadCookies(page) {
  if (!fs.existsSync(COOKIES_PATH)) return false;
  const cookies = JSON.parse(fs.readFileSync(COOKIES_PATH, 'utf8'));
  await page.setCookie(...cookies);
  await page.reload({ waitUntil: 'networkidle2' });
  return true;
}

function loadAppliedJobs() {
  if (!fs.existsSync(APPLIED_JOBS_PATH)) return new Set();
  const lines = fs.readFileSync(APPLIED_JOBS_PATH, 'utf8').split(/\n/).filter(Boolean);
  return new Set(lines);
}

function saveAppliedJob(id) {
  fs.appendFileSync(APPLIED_JOBS_PATH, `${id}\n`);
}

async function logApplication(cfg, data) {
  const fileExists = fs.existsSync(cfg.logPath);
  const records = [data];
  const csvString = await new Promise((resolve, reject) => {
    csv.stringify(records, { header: !fileExists, columns: Object.keys(data) }, (err, out) => {
      if (err) reject(err); else resolve(out);
    });
  });
  fs.appendFileSync(cfg.logPath, csvString);
}

// Use Google Maps Distance Matrix API to calculate distance.
async function calculateDistance(from, to, apiKey) {
  if (!apiKey) return null; // skip if no API key
  try {
    const url = 'https://maps.googleapis.com/maps/api/distancematrix/json';
    const { data } = await axios.get(url, {
      params: { origins: from, destinations: to, key: apiKey, units: 'imperial' },
    });
    const dist = data.rows[0].elements[0].distance;
    if (dist) return parseFloat(dist.text.replace(/ mi$/, ''));
  } catch (e) {
    console.error('Distance API error:', e.message);
  }
  return null;
}

// Parse salary snippet like "$18 - $20 an hour" and return the lower bound
function parseSalary(text) {
  if (!text) return null;
  const match = text.match(/\$([\d,.]+)/);
  return match ? parseFloat(match[1].replace(/,/g, '')) : null;
}

async function parseJobType(page) {
  // attempt to extract job type label
  const text = await page.evaluate(() => {
    const labels = Array.from(document.querySelectorAll('*')).filter((el) =>
      /Job Type/i.test(el.textContent || '')
    );
    for (const label of labels) {
      const sib = label.nextElementSibling;
      if (sib) return sib.textContent;
    }
    return document.body.innerText;
  });
  if (!text) return null;
  const lower = text.toLowerCase();
  if (lower.includes('full-time')) return 'full-time';
  if (lower.includes('part-time')) return 'part-time';
  if (lower.includes('contract')) return 'contract';
  if (lower.includes('temporary')) return 'temporary';
  if (lower.includes('internship')) return 'internship';
  return null;
}

function isValidJobType(type) {
  if (!type) return false;
  const t = type.toLowerCase();
  if (t.includes('full-time') || t.includes('part-time')) return true;
  if (t.includes('contract') || t.includes('temporary') || t.includes('internship')) return false;
  return false;
}

async function ensureLogin(page) {
  try {
    await page.waitForSelector('a[href*="login"]', { timeout: 5000 });
    console.log('Please log into Indeed manually.');
    await prompt('Press Enter after logging in...');
    await saveCookies(page);
  } catch (e) {
    console.log('Already logged in.');
  }
}

async function getEasyApplyJobs(page, seen, cfg, city) {
  // Evaluate the search results page in the browser context
  const jobs = await page.evaluate(() => {
    const nodes = Array.from(document.querySelectorAll('a[data-jk]'));
    return nodes
      .filter((el) => el.innerText.includes('Easily apply'))
      .map((el) => ({
        id: el.getAttribute('data-jk'),
        link: el.href,
        title: el.querySelector('.jobTitle')?.innerText.trim() || el.innerText.trim(),
        company: el.querySelector('.companyName')?.innerText.trim() || '',
        location: el.querySelector('.companyLocation')?.innerText.trim() || '',
      }));
  });
  return jobs.filter((job) => {
    if (!job.id || seen.has(job.id)) return false;
    if (job.location && cfg.locations && !job.location.includes(city)) return false;
    return true;
  });
}

async function fillBasicFields(page) {
  // Fill text fields, selects, radios, checkboxes with default values
  const inputs = await page.$$('input[type=text], input[type=tel], textarea, input:not([type])');
  for (const input of inputs) {
    const val = await (await input.getProperty('value')).jsonValue();
    const visible = await input.isIntersectingViewport();
    if (!visible || val) continue;
    const type = await (await input.getProperty('type')).jsonValue();
    await input.click({ clickCount: 3 });
    await humanDelay();
    if (type === 'tel') await input.type('555-555-5555');
    else await input.type('N/A');
  }

  const selects = await page.$$('select');
  for (const sel of selects) {
    const disabled = await (await sel.getProperty('disabled')).jsonValue();
    if (disabled) continue;
    const opts = await sel.$$('option');
    for (const o of opts) {
      const val = await (await o.getProperty('value')).jsonValue();
      const dis = await (await o.getProperty('disabled')).jsonValue();
      if (val && !dis) { await sel.select(val); break; }
    }
  }

  const radios = await page.$$('input[type=radio]');
  const groups = {};
  for (const r of radios) {
    const name = await (await r.getProperty('name')).jsonValue();
    if (!groups[name]) groups[name] = [];
    groups[name].push(r);
  }
  for (const group of Object.values(groups)) {
    let choice = group[0];
    for (const r of group) {
      const aria = await (await r.getProperty('ariaLabel')).jsonValue();
      if (aria && aria.toLowerCase().includes('yes')) { choice = r; break; }
    }
    await choice.click();
  }

  const checks = await page.$$('input[type=checkbox]');
  for (const c of checks) {
    const checked = await (await c.getProperty('checked')).jsonValue();
    if (!checked) await c.click();
  }
}

async function applyToJob(browser, job, cfg, seen) {
  const page = await browser.newPage();
  await page.goto(job.link, { waitUntil: 'domcontentloaded' });
  await humanDelay();
  // small random mouse move
  await page.mouse.move(100 + Math.random() * 50, 200 + Math.random() * 50);
  const result = { status: 'Skipped', distance: null };

  try {
    // parse salary and job type
    const salaryText = await page.$eval('.salary-snippet', (el) => el.textContent).catch(() => null);
    const minSalary = parseSalary(salaryText);
    if (!minSalary || minSalary < cfg.minSalary) {
      console.log('Skipping job - salary too low or missing');
      await page.close();
      return result;
    }

    const jobType = await parseJobType(page);
    if (!isValidJobType(jobType)) {
      console.log(`Skipping job - type is ${jobType || 'unknown'}`);
      await page.close();
      return result;
    }

    // check job location
    const jobLocation = await page.$eval('.companyLocation', (el) => el.textContent).catch(() => job.location);
    if (cfg.userAddress) {
      result.distance = await calculateDistance(cfg.userAddress, jobLocation, cfg.googleApiKey);
      if (result.distance) console.log(`Distance to job: ${result.distance} mi`);
    }

    console.log('Applying now...');
    const applyBtn = await page.waitForSelector('button:has-text("Apply"), button:has-text("Submit")', { timeout: 10000 });
    await applyBtn.click();
    await humanDelay();

    // resume upload
    const fileInput = await page.$('input[type=file]');
    if (fileInput) {
      await fileInput.uploadFile(cfg.resumePath);
      await humanDelay();
    }

    await fillBasicFields(page);

    const submit = await page.waitForSelector('button:has-text("Submit")', { timeout: 10000 }).catch(() => null);
    if (submit) {
      await submit.click();
      await page.waitForNavigation({ waitUntil: 'domcontentloaded', timeout: 15000 }).catch(() => {});
      result.status = 'Applied';
      console.log(`Application sent for ${job.title}`);
    }
  } catch (e) {
    console.error('Error applying:', e.message);
    result.status = 'Error';
  }

  await page.close();
  if (result.status === 'Applied') {
    seen.add(job.id);
    saveAppliedJob(job.id);
    const msg = `${job.title} at ${job.company}${result.distance ? ` - ${result.distance} mi away` : ''}`;
    sendNotification('Indeed Bot: Application Sent', msg);
  }
  return result;
}

async function searchCity(page, city) {
  await page.goto('https://www.indeed.com', { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('#text-input-where');
  await page.type('#text-input-where', city, { delay: 50 });
  await page.keyboard.press('Enter');
  await page.waitForSelector('#resultsCol', { timeout: 15000 }).catch(() => {});
  await humanDelay();
}

async function main() {
  const cfg = loadConfig();
  cfg.logPath = cfg.log_path || cfg.logPath || 'applied_jobs_log.csv';

  const browser = await puppeteer.launch({ headless: false, args: ['--start-maximized'], defaultViewport: null });
  const page = await browser.newPage();
  await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117 Safari/537.36');

  let loaded = false;
  if (fs.existsSync(COOKIES_PATH)) {
    const ans = await prompt('Press Enter to load saved cookies or type login to sign in manually: ');
    if (ans.trim() === '') {
      loaded = await loadCookies(page);
    }
  }
  if (!loaded) {
    await page.goto('https://www.indeed.com', { waitUntil: 'domcontentloaded' });
    await ensureLogin(page);
    await saveCookies(page);
  }

  const applied = loadAppliedJobs();
  let count = 0;
  for (const city of cfg.locations) {
    if (count >= cfg.max_applications) break;
    console.log(`Searching jobs in ${city}`);
    await searchCity(page, city);

    let jobs = await getEasyApplyJobs(page, applied, cfg, city);
    for (const job of jobs) {
      if (count >= cfg.max_applications) break;
      const { status, distance } = await applyToJob(browser, job, cfg, applied);
      await logApplication(cfg, {
        timestamp: new Date().toISOString(),
        job_title: job.title,
        company: job.company,
        city,
        distance,
        status,
      });
      if (status === 'Applied') count += 1;
      console.log(`Remaining applications: ${cfg.max_applications - count}/${cfg.max_applications}`);
    }
  }

  await browser.close();
}

main().catch((e) => { console.error(e); process.exit(1); });
