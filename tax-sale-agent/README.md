# Tax Sale Deal Finder Agent (Texas / Harris County)

This kit helps you **find and score deals** in the Harris County (TX) tax sale list, check **liens that may survive**, and calculate a simple **Deal Score**.

## 🧰 What you get
- **fetch-harris**: Scrapes the official Harris County tax sale list and adds value estimates (Zillow via RapidAPI optional; falls back to adjudged value).
- **scrape-clerk**: Headless browser scraper for **Harris County Clerk** Real Property Records by owner/address query (no API needed).
- **scrape-muni**: Config‑driven scraper for **municipal/code-enforcement** liens (you tweak CSS selectors).
- **enrich**: Classifies likely surviving liens (municipal, Chapter 61, property tax loan, DOJ, IRS*), sums exposure, and outputs a **Deal Score**.

> ⚠️ **Always verify** with the county/city/title company before bidding. This tool is for **research only**.

---

## 🪜 Step-by-step (zero experience)

### 0) Install Python
- Windows/Mac: Install **Python 3.10+** from python.org. During install, check “Add Python to PATH”.

### 1) Download the project
- Download this folder: **[tax-sale-agent]** (I’ve saved all files in this package).  
- Or grab all files from the chat download links.

### 2) Open a terminal in the project folder
- Windows: Press Win key, type **cmd**, open Command Prompt. Then:
  ```bat
  cd %HOMEPATH%\Downloads\tax-sale-agent
  ```
- Mac:
  ```bash
  cd ~/Downloads/tax-sale-agent
  ```

### 3) Create a virtual environment & install requirements
```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Mac/Linux
source venv/bin/activate

pip install -r requirements.txt
python -m playwright install
```

### 4) (Optional) Add Zillow RapidAPI key
- Copy `.env.template` to `.env` and put your key:
  ```
  ZILLOW_RAPIDAPI_KEY=YOUR_KEY
  ZILLOW_RAPIDAPI_HOST=zillow-com1.p.rapidapi.com
  ```
- No key? The script will **fallback** to adjudged value when possible.

### 5) Fetch the Harris County tax sale list + estimates
```bash
python -m src.agent fetch-harris --out harris_tax_sale.csv
```
- Output: `harris_tax_sale.csv`

### 6) Scrape Clerk records (owner/address) – no API
- This opens a **headless browser** and pages results. We’ll query by **address** from the Step 5 CSV.
```bash
python -m src.agent scrape-clerk --from-csv harris_tax_sale.csv --query-field address --out clerk_results.csv --limit 40
```
- Tip: Increase `--limit` carefully. Start small to avoid rate limits.

### 7) Scrape Municipal/City liens (config)
- Open `config/houston_example.json` and tweak to your city’s site (correct selectors + URL).
```bash
python -m src.agent scrape-muni --config config/houston_example.json --out municipal_liens.csv
```

### 8) Enrich + score deals
```bash
python -m src.agent enrich --step2 harris_tax_sale.csv --clerk clerk_results.csv --municipal municipal_liens.csv --out harris_tax_sale_enriched.csv
```
- Open `harris_tax_sale_enriched.csv` in Excel/Sheets and sort by `deal_score` (higher is better).

### 9) One-command end-to-end
```bash
python -m src.agent run-all --out harris_tax_sale_enriched.csv --municipal-config config/houston_example.json
```

---

## 🧪 What counts as “surviving” (rules baked in)
- **Survive**: municipal/city liens, **Texas State Chapter 61** liens, **property tax loans (Tx Tax Code §32.06)**, **DOJ** liens.  
- **IRS**: “conditional” — wiped if IRS was notified 25 days prior; IRS has **120‑day redemption**. We flag as a risk.  
- **Usually wiped**: HOA, mechanics, judgments, other state liens (Ch.113/201/213).  
- You can change rules in `src/liens.py` (SURVIVES + penalties).

## 🛠️ Troubleshooting
- **HCTax page changed?** Edit selectors in `src/adapters.py` → `HCTaxNetAdapter`.
- **Clerk site changed?** Edit the input/button selectors in `src/scrapers.py > ClerkScraper`.
- **Municipal site**: Update `config/houston_example.json` with correct CSS selectors.
- **Playwright**: If blocked, reduce query `--limit`, add pauses (we can add a delay if needed).

---

## 📦 Files in this project
- `requirements.txt` – Python dependencies
- `.env.template` – optional Zillow RapidAPI key
- `config/houston_example.json` – municipal scraper config (edit this!)
- `src/utils.py` – small helpers
- `src/adapters.py` – Harris tax sale fetch + Zillow estimator
- `src/liens.py` – lien classification + scoring
- `src/scrapers.py` – Playwright scrapers (Clerk + Municipal)
- `src/agent.py` – command-line orchestrator

---

If you want, tell me your **exact city/municipal lien site URL** and I’ll fill the JSON selectors for you so it works out‑of‑the‑box.
