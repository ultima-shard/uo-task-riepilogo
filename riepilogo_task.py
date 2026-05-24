import os
import json
import requests
from datetime import datetime
import pytz

# ── Configurazione (da GitHub Secrets) ──────────────────────
NOTION_TOKEN       = os.environ["NOTION_TOKEN"]
NOTION_DATABASE_ID = os.environ["NOTION_DATABASE_ID"]
DISCORD_WEBHOOK_ID    = os.environ["DISCORD_WEBHOOK_ID"]
DISCORD_WEBHOOK_TOKEN = os.environ["DISCORD_WEBHOOK_TOKEN"]
DISCORD_MESSAGE_ID    = os.environ["DISCORD_MESSAGE_ID"]

# ── Membri del team (notion name → display name) ─────────────
TEAM_MEMBERS = [
    {"notion": "Alessandro",                          "display": "Alessandro"},
    {"notion": "Grego",                               "display": "Grego"},
    {"notion": "Parassita",                           "display": "Parassita"},
    {"notion": "Marco",                               "display": "Marco"},
    {"notion": "aurelio.fregonesebrunello@gmail.com", "display": "Aurelio"},
]

# ── Notion: recupera tutti i task con paginazione ────────────
def fetch_all_tasks():
    url = f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    results, has_more, start_cursor = [], True, None

    while has_more:
        body = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        res = requests.post(url, headers=headers, json=body)
        if res.status_code != 200:
            print(f"❌ Errore Notion ({res.status_code}): {res.text}")
            return None

        data = res.json()
        results.extend(data.get("results", []))
        has_more     = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return results

# ── Statistiche per membro ───────────────────────────────────
def calcola_statistiche(tasks):
    stats = {m["notion"]: {"count": 0, "total_pct": 0, "with_pct": 0}
             for m in TEAM_MEMBERS}

    for task in tasks:
        if not task or not task.get("properties"):
            continue

        props = task["properties"]

        # Assegnatario (person field)
        assegnatari = props.get("Assegnatario", {}).get("people", [])

        # Completamento (select field: "0%", "25%", "50%", "75%", "100%")
        sel = props.get("Completamento", {}).get("select")
        pct = int(sel["name"].replace("%", "")) if sel else None

        for user in assegnatari:
            name = user.get("name", "")
            if name in stats:
                stats[name]["count"] += 1
                if pct is not None:
                    stats[name]["total_pct"] += pct
                    stats[name]["with_pct"]  += 1

    return stats

# ── Costruisce embed Discord ─────────────────────────────────
def costruisci_embed(stats):
    rome = pytz.timezone("Europe/Rome")
    now  = datetime.now(rome).strftime("%d/%m/%Y alle %H:%M")

    fields = []
    for m in TEAM_MEMBERS:
        s   = stats[m["notion"]]
        avg = (f"{round(s['total_pct'] / s['with_pct'])}%"
               if s["with_pct"] > 0 else "—")
        fields.append({
            "name":   m["display"],
            "value":  f"📋 Task: **{s['count']}**\n⚡ Completamento medio: **{avg}**",
            "inline": True,
        })

    return {
        "embeds": [{
            "title":       "📊 Riepilogo Task — Unità Operativa",
            "description": f"_Aggiornato il {now}_",
            "color":       0x5865F2,
            "fields":      fields,
            "footer":      {"text": "Aggiornamento automatico ogni 5 minuti"},
        }]
    }

# ── Discord: PATCH del messaggio esistente ───────────────────
def patch_discord(payload):
    url = (f"https://discord.com/api/webhooks/"
           f"{DISCORD_WEBHOOK_ID}/{DISCORD_WEBHOOK_TOKEN}"
           f"/messages/{DISCORD_MESSAGE_ID}")

    res = requests.patch(url, json=payload)
    if res.status_code == 200:
        print("✅ Messaggio Discord aggiornato")
    else:
        print(f"❌ Errore Discord ({res.status_code}): {res.text}")
        res.raise_for_status()

# ── Entry point ──────────────────────────────────────────────
if __name__ == "__main__":
    tasks = fetch_all_tasks()
    if tasks is None:
        raise SystemExit("Notion non raggiungibile — uscita")

    stats   = calcola_statistiche(tasks)
    payload = costruisci_embed(stats)
    patch_discord(payload)
