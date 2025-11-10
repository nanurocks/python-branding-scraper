Python Branding Scraper
======================

What it does:
- Renders the page using Playwright (Chromium), extracts logo (img, svg, og:image, favicon)
- Downloads logo image and extracts dominant color + palette using ColorThief
- Returns JSON and a simple preview UI

Setup (recommended Python 3.9+)
1. Create a virtual environment (optional but recommended):
   python -m venv venv
   source venv/bin/activate   (on Windows: venv\Scripts\activate)

2. Install dependencies:
   pip install -r requirements.txt

3. Install Playwright browsers:
   playwright install

4. Run the server:
   python server.py

5. Open http://localhost:5000 in your browser and enter a domain (e.g. airbnb.co.in)

Notes:
- If you run into permission or sandbox issues on Linux, try launching Chromium with args ['--no-sandbox','--disable-setuid-sandbox'] (already included).
- If Playwright installation fails on restricted machines, consider using the requests + BeautifulSoup-only path (no JS rendering) but results will be less accurate.
