from flask import Flask, render_template, request, jsonify
from scraper import scrape_brand_data
import traceback
import sys
import os

app = Flask(__name__)

# Configure Flask reloader to ignore Playwright directories
# This prevents EPIPE errors when Playwright's internal files change
if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
    # Only set this in the main process, not the reloader
    pass

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/scrape", methods=["POST"])
def scrape():
    try:
        domain = request.form.get("domain", "").strip()
        if not domain:
            return jsonify({"error": "No domain provided"}), 400

        data = scrape_brand_data(domain)
        return jsonify(data)
    except Exception as e:
        # Log the full traceback for debugging
        print(f"Error in scrape endpoint: {str(e)}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    # Use use_reloader=False to prevent EPIPE errors with Playwright
    # Or set reloader_type='stat' instead of 'watchdog' (if available)
    # For production, set debug=False
    app.run(debug=True, use_reloader=False)
