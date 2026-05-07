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
    url = f"https://barttorvik.com/getadvstats.php?year={year}"
    print(f"[Barttorvik] Fetching {url} ...")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)
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

def get_firebase_id_token(api_key: str, refresh_token: str) -> str:
    """Exchange a Firebase refresh token for a fresh ID token (valid 1 hour)."""
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
    id_token = data.get("id_token")
    if not id_token:
        raise RuntimeError(f"Failed to get id_token. Response: {data}")
    print("[EvanMiya] Firebase id_token obtained.")
    return id_token


def fetch_evanmiya(api_key: str, refresh_token: str, output_path: str):
    """Log into EvanMiya via Firebase token and download the Player Ratings CSV."""
    from playwright.sync_api import sync_playwright

    id_token = get_firebase_id_token(api_key, refresh_token)

    print("[EvanMiya] Launching browser ...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        # Load the page first so localStorage is accessible
        page.goto("https://evanmiya.com", timeout=30000)
        page.wait_for_load_state("domcontentloaded")

        # Inject fresh access token into the existing Firebase localStorage entry
        page.evaluate(f"""() => {{
            const key = Object.keys(localStorage).find(k => k.startsWith('firebase:authUser'));
            if (key) {{
                const existing = JSON.parse(localStorage.getItem(key));
                existing.stsTokenManager.accessToken = "{id_token}";
                existing.stsTokenManager.expirationTime = Date.now() + 3600000;
                localStorage.setItem(key, JSON.stringify(existing));
            }}
        }}""")

        # Navigate to Player Ratings and wait for the download button to appear
        print("[EvanMiya] Navigating to Player Ratings ...")
        page.goto("https://evanmiya.com/?player_ratings", timeout=30000)
        page.wait_for_load_state("networkidle")

        # Wait for the specific download button to be visible
        page.wait_for_selector("#player_ratings_page_download_player_ratings", timeout=20000)
        print("[EvanMiya] Download button found, clicking ...")

        # Click and capture the download
        with page.expect_download(timeout=30000) as download_info:
            page.click("#player_ratings_page_download_player_ratings")

        download = download_info.value
        download.save_as(output_path)
        print(f"[EvanMiya] Written to {output_path}")

        browser.close()


# ── Main ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year

    # Barttorvik (no auth needed)
    fetch_barttorvik(year, f"barttorvik_{year}.csv")

    # EvanMiya (uses Firebase refresh token — never expires)
    api_key       = os.environ.get("EVANMIYA_FIREBASE_API_KEY")
    refresh_token = os.environ.get("EVANMIYA_REFRESH_TOKEN")

    if not api_key or not refresh_token:
        print("[EvanMiya] Skipping — EVANMIYA_FIREBASE_API_KEY or EVANMIYA_REFRESH_TOKEN not set.")
    else:
        fetch_evanmiya(api_key, refresh_token, f"evanmiya_{year}.csv")
