import json
import csv
import urllib.request
import sys
from datetime import datetime

# Column headers for barttorvik getadvstats.php
# Based on known field ordering from the Barttorvik data format
HEADERS = [
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

def fetch_and_convert(year: int, output_path: str):
    url = f"https://barttorvik.com/getadvstats.php?year={year}"
    print(f"Fetching {url} ...")

    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")

    data = json.loads(raw)
    print(f"  → {len(data)} rows fetched")

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Write header — use as many column names as there are fields in first row
        num_cols = len(data[0]) if data else len(HEADERS)
        if num_cols <= len(HEADERS):
            header_row = HEADERS[:num_cols]
        else:
            # More columns than we have names for — pad with col_N
            header_row = HEADERS + [f"col_{i}" for i in range(len(HEADERS), num_cols)]

        writer.writerow(header_row)
        writer.writerows(data)

    print(f"  → Written to {output_path}")


if __name__ == "__main__":
    year = int(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().year
    output = sys.argv[2] if len(sys.argv) > 2 else f"barttorvik_{year}.csv"
    fetch_and_convert(year, output)
