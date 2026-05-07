import json
import csv
import urllib.request
import urllib.parse
import sys
import os
from datetime import datetime

# ── Barttorvik column headers ──────────────────────────────────────────────────
BARTTORVIK_HEADERS = [
    "player", "team", "conf", "games", "min_pct", "ortg", "usg",
    "efg", "ts_pct", "or_pct", "dr_pct", "ast_pct", "to_pct",
    "ftm", "fta", "ft_pct", "two_m", "two_a", "two_pct",
    "three_m", "three_a", "three_pct", "blk_pct", "stl_pct", "ftr",
    "yr", "ht", "num", "porpag", "adj_oe", "drtg", "year",
    "pid", "hometowncity", "rpi", "stars", "bpm", "obpm", "dbpm",
    "gbpm", "mp", "ogbpm", "dgbpm",
    "oreb", "dreb", "treb", "ast", "stl", "blk", "pts",
    "ast_to", "rk_ortg", "rk_usg", "rk_efg", "rk_ts",
    "rk_or", "rk_dr", "rk_ast", "rk_to", "rk_blk", "rk_stl",
    "rk_ftr", "rk_porpag", "rk_adj_oe", "rk_bpm", "rk_obpm",
    "rk_dbpm", "rk_gbpm",
    "team_ortg", "team_drtg", "rec", "badshots", "box_creation",
    "loc_quint", "dunk_pct", "rim_pct", "mid_pct",
    "pos", "adrtg", "dob",
]

# ── Barttorvik ─────────────────────────────────────────────────────────────────

def fetch_barttorvik(year: int, output_path: str):
    """Use Playwright to fetch Barttorvik JSON as a real browser request."""
    from playwright.sync_api import sync_playwright

    url = f"https://barttorvik.com/getadvstats.php?year={year}"
    print(f"[Barttorvik] Fetching {url} ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Intercept the JSON response
        raw_json = {}

        def handle_response(response):
            if "getadvstats.php" in response.url:
                try:
                    raw_json["data"] = response.json()
                except Exception:
                    raw_json["data"] = json.loads(response.text())

        page.on("response", handle_response)
        page.goto(url, timeout=30000, wait_until="networkidle")
        browser.close()

    data = raw_json.get("data")
    if not data:
        # Fallback: parse the page body directly
        raise RuntimeError("[Barttorvik] No data captured from response.")

    print(f"[Barttorvik] {len(data)} rows fetched")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        num_cols = len(data[0]) if data else len(BARTTORVIK_HEADERS)
        if num_cols <= len(BARTTORVIK_HEADERS):
            header_row = BARTTORVIK_HEADERS[:num_cols]
        else:
            header_row = BARTTORVIK_HEADERS + [f"col_{i}" for i in range(len(BARTTORVIK_HEADERS), num_cols)]
        writer.writerow(header_row)
        writer.writerows(data)

    print(f"[Barttorvik] Written to {output_path}")


# ── EvanMiya ───────────────────────────────────────────────────────────────────

def get_firebase_id_token(api_key: str, refresh_token: str) -> dict:
    """Exchange a Firebase refresh token for a fresh ID token."""
    url = f"https://securetoken.googleapis.com/v1/token?key={api_key}"
    body = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }).encode("utf-8")
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    if not data.get("id_token"):
        raise RuntimeError(f"Failed to get id_token. Response: {data}")
    print("[EvanMiya] Firebase id_token obtained.")
    return data


def fetch_evanmiya(api_key: str, refresh_token: str, firebase_key: str, output_path: str):
    """Log into EvanMiya by building a full Firebase auth object in localStorage."""
    from playwright.sync_api import sync_playwright

    token_data = get_firebase_id_token(api_key, refresh_token)
    id_token = token_data["id_token"]
    new_refresh_token = token_data.get("refresh_token", refresh_token)
    user_id = token_data.get("user_id", "")
    expiration_time = int(datetime.now().timestamp() * 1000) + 3600000

    # Build the full Firebase auth object that evanmiya.com expects in localStorage
    auth_object = {
        "uid": user_id,
        "email": "sackjj2@gmail.com",
        "emailVerified": True,
        "displayName": "Jeff Sack",
        "isAnonymous": False,
        "providerData": [{"providerId": "google.com", "uid": user_id, "email": "sackjj2@gmail.com"}],
        "stsTokenManager": {
            "refreshToken": new_refresh_token,
            "accessToken": id_token,
            "expirationTime": expiration_time,
        },
        "createdAt": "1712172499187",
        "lastLoginAt": "1776871942979",
        "apiKey": api_key,
        "appName": "[DEFAULT]",
    }

    print("[EvanMiya] Launching browser ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Load the page first so localStorage is accessible
        page.goto("https://evanmiya.com", timeout=30000)
        page.wait_for_load_state("domcontentloaded")

        # Write the full Firebase auth object into localStorage
        auth_json = json.dumps(auth_object)
        page.evaluate(f"""() => {{
            localStorage.setItem({json.dumps(firebase_key)}, {json.dumps(auth_json)});
        }}""")
        print("[EvanMiya] Auth object written to localStorage.")

        # Navigate to Player Ratings and wait for the download button
        print("[EvanMiya] Navigating to Player Ratings ...")
        page.goto("https://evanmiya.com/?player_ratings", timeout=30000)
        page.wait_for_load_state("networkidle")

        page.wait_for_selector("#player_ratings_page_download_player_ratings", timeout=20000)
        print("[EvanMiya] Download button found, clicking ...")

        with page.expect_download(timeout=30000) as download_info:
            page.click("#player_ratings_page_download_player_ratings")

        download = download_info.value
        download.save_as(output_path)
        print(f"[EvanMiya] Written to {output_path}")

        browser.close()


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year

    # Barttorvik (uses Playwright to bypass 403)
    fetch_barttorvik(year, f"barttorvik_{year}.csv")

    # EvanMiya (uses Firebase refresh token)
    api_key       = os.environ.get("EVANMIYA_FIREBASE_API_KEY")
    refresh_token = os.environ.get("EVANMIYA_REFRESH_TOKEN")
    firebase_key  = os.environ.get("EVANMIYA_FIREBASE_KEY")

    if not api_key or not refresh_token or not firebase_key:
        print("[EvanMiya] Skipping — one or more secrets not set: EVANMIYA_FIREBASE_API_KEY, EVANMIYA_REFRESH_TOKEN, EVANMIYA_FIREBASE_KEY")
    else:
        fetch_evanmiya(api_key, refresh_token, firebase_key, f"evanmiya_{year}.csv")
