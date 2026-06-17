# Oro SP/AP Lead Dashboard

Live web app that merges **Metabase lead data** with **Google Sheet cluster/city mapping**
and displays summary cards + a searchable table. Auto-refreshes every 5 minutes.

---

## Files

```
app.py              ← Flask backend (fetches + merges data)
templates/index.html← Dashboard UI
requirements.txt    ← Python dependencies
render.yaml         ← Render.com deploy config
.env.example        ← Environment variable template
```

---

## Step 1 — Publish your Google Sheet as CSV

1. Open your Google Sheet
2. **File → Share → Publish to web**
3. Select your mapping sheet tab → choose **CSV** → click **Publish**
4. Copy the URL (looks like `https://docs.google.com/spreadsheets/d/ABC.../export?format=csv&gid=0`)

---

## Step 2 — Set your column names in app.py

Open `app.py` and update these 4 lines:

```python
METABASE_CARD_ID = 12868        # your Metabase card ID
MB_JOIN_COL = "sp_name"         # exact column name in Metabase card result
GS_JOIN_COL = "SP Name"         # exact column name in your G Sheet
```

Also update the display columns (~line 80) to match your actual data:
```python
display_cols = [c for c in [
    MB_JOIN_COL, "City", "Cluster", "lead_status", "lead_date", ...
] if c in df.columns]
```

---

## Step 3 — Deploy to Render.com (free)

1. Push this folder to a **GitHub repository** (public or private)
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Set these **Environment Variables** in Render dashboard:

| Variable          | Value                              |
|-------------------|------------------------------------|
| METABASE_URL      | https://metabase-mcp.orocorp.in    |
| METABASE_USER     | your_email@orocorp.in              |
| METABASE_PASSWORD | your_password                      |
| METABASE_CARD_ID  | 12868                              |
| GSHEET_CSV_URL    | (your published CSV URL)           |
| MB_JOIN_COL       | sp_name                            |
| GS_JOIN_COL       | SP Name                            |

5. Click **Deploy** — Render builds and starts the app automatically
6. Your live URL: `https://oro-sp-dashboard.onrender.com`

---

## Step 4 — Embed in Metabase Dashboard

1. Open your Metabase dashboard → **Edit**
2. Add a **Text card**
3. Paste this (replace the URL):

```html
<iframe src="https://oro-sp-dashboard.onrender.com"
        width="100%" height="520"
        style="border:none;border-radius:8px;">
</iframe>
```

4. Save — the live panel appears inside your Metabase dashboard

---

## Run locally (optional)

```bash
pip install -r requirements.txt

export METABASE_USER="your_email@orocorp.in"
export METABASE_PASSWORD="your_password"
export GSHEET_CSV_URL="https://docs.google.com/..."

python app.py
# open http://localhost:5000
```

---

## How the refresh works

- The Flask backend caches merged data for **5 minutes**
- The frontend polls `/api/data` every **5 minutes** automatically
- Click **↻ Refresh** button to force-clear the cache instantly
