import os
import requests
import pandas as pd
from flask import Flask, render_template, jsonify
import time

app = Flask(__name__)

# ─── CONFIG ───────────────────────────────────────────────────────────────────
METABASE_URL      = os.getenv("METABASE_URL",      "https://metabase-mcp.orocorp.in")
METABASE_USER     = os.getenv("METABASE_USER",     "your_email@orocorp.in")
METABASE_PASSWORD = os.getenv("METABASE_PASSWORD", "your_password")
METABASE_CARD_ID  = int(os.getenv("METABASE_CARD_ID", "12868"))

GSHEET_CSV_URL = os.getenv(
    "GSHEET_CSV_URL",
    "https://docs.google.com/spreadsheets/d/e/2PACX-1vQtiRbYV5DOKXuB2K6OU2H0P85ums8C6Rm6ZRo39wrXCQjWZOqNyGrUxFLP3EIk8vFhU74WtPsPRryK/pub?gid=774636387&single=true&output=csv"
)

# ─── Join keys (exact column names) ──────────────────────────────────────────
MB_JOIN_COL = "emply_id"    # column in Metabase card
GS_JOIN_COL = "Emp ID"      # column in G Sheet
# ─────────────────────────────────────────────────────────────────────────────

_token_cache = {"token": None, "expires": 0}

def get_metabase_token():
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires"]:
        return _token_cache["token"]
    resp = requests.post(
        f"{METABASE_URL}/api/session",
        json={"username": METABASE_USER, "password": METABASE_PASSWORD},
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json()["id"]
    _token_cache["token"]   = token
    _token_cache["expires"] = now + 3600
    return token


def fetch_metabase_card(card_id: int) -> pd.DataFrame:
    token = get_metabase_token()
    resp = requests.post(
        f"{METABASE_URL}/api/card/{card_id}/query/json",
        headers={"X-Metabase-Session": token},
        json={},
        timeout=30,
    )
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def fetch_gsheet() -> pd.DataFrame:
    df = pd.read_csv(GSHEET_CSV_URL)
    df.columns = df.columns.str.strip()
    # Keep only the columns we need for mapping
    keep = [GS_JOIN_COL, "City", "Cluster mapping", "Team", "Status"]
    df = df[[c for c in keep if c in df.columns]]
    # Drop duplicate Emp IDs — keep first Active, else first row
    df["_sort"] = df["Status"].apply(lambda x: 0 if str(x).strip() == "Active" else 1)
    df = df.sort_values("_sort").drop_duplicates(subset=[GS_JOIN_COL]).drop(columns="_sort")
    return df


_cache = {"data": None, "ts": 0}
CACHE_TTL = 300  # 5 minutes

def get_merged_data():
    now = time.time()
    if _cache["data"] is not None and now - _cache["ts"] < CACHE_TTL:
        return _cache["data"]

    leads_df  = fetch_metabase_card(METABASE_CARD_ID)
    gsheet_df = fetch_gsheet()

    # Normalise join keys — strip whitespace only (preserve case for IDs like ORO00064)
    leads_df[MB_JOIN_COL]  = leads_df[MB_JOIN_COL].astype(str).str.strip()
    gsheet_df[GS_JOIN_COL] = gsheet_df[GS_JOIN_COL].astype(str).str.strip()

    merged = leads_df.merge(
        gsheet_df,
        left_on=MB_JOIN_COL,
        right_on=GS_JOIN_COL,
        how="left",
        suffixes=("_mb", "_gs"),
    )

    # Use G Sheet City as the final city (override Metabase city)
    if "City_gs" in merged.columns:
        merged["Final City"] = merged["City_gs"].fillna(merged.get("City_mb", ""))
    elif "City" in merged.columns:
        merged["Final City"] = merged["City"]

    _cache["data"] = merged
    _cache["ts"]   = now
    return merged


# ─── ROUTES ──────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/data")
def api_data():
    try:
        df = get_merged_data()

        total_leads = len(df)

        # City summary (from G Sheet final city)
        city_col = "Final City"
        city_summary = (
            df[df[city_col].notna() & (df[city_col] != "")]
            .groupby(city_col).size()
            .reset_index(name="leads")
            .sort_values("leads", ascending=False)
            .to_dict(orient="records")
        ) if city_col in df.columns else []

        # Cluster summary
        cluster_col = "Cluster mapping"
        cluster_summary = (
            df[df[cluster_col].notna() & (df[cluster_col] != "")]
            .groupby(cluster_col).size()
            .reset_index(name="leads")
            .sort_values("leads", ascending=False)
            .to_dict(orient="records")
        ) if cluster_col in df.columns else []

        # Team summary (Sales vs Appraisal)
        team_col = "Team"
        team_summary = (
            df[df[team_col].notna()]
            .groupby(team_col).size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .to_dict(orient="records")
        ) if team_col in df.columns else []

        # Status summary (Active / Relieved etc.)
        status_col = "Status"
        status_summary = (
            df[df[status_col].notna()]
            .groupby(status_col).size()
            .reset_index(name="count")
            .sort_values("count", ascending=False)
            .to_dict(orient="records")
        ) if status_col in df.columns else []

        # Table — pick display columns that exist
        display_cols = [c for c in [
            "Created @",
            "Sp/Ap Name",
            MB_JOIN_COL,
            "Final City",
            "Cluster mapping",
            "Team",
            "Status",
        ] if c in df.columns]

        table_data = (
            df[display_cols]
            .fillna("")
            .head(500)
            .to_dict(orient="records")
        )

        return jsonify({
            "ok":              True,
            "total_leads":     total_leads,
            "city_summary":    city_summary,
            "cluster_summary": cluster_summary,
            "team_summary":    team_summary,
            "status_summary":  status_summary,
            "table":           table_data,
            "columns":         display_cols,
            "refreshed_at":    time.strftime("%d %b %Y %H:%M:%S"),
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/refresh", methods=["POST"])
def force_refresh():
    _cache["ts"] = 0
    _token_cache["expires"] = 0
    return jsonify({"ok": True})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
