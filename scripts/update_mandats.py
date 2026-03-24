import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from datetime import date
import unicodedata
import time
import os

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Départements Pays de la Loire (ajustés selon ton URL)
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

# ============================
# FONCTIONS UTILITAIRES
# ============================
def load_csv():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Erreur : {CSV_PATH} introuvable.")
        return [], []
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    return rows, fields

def save_csv(rows, fields):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

def build_target_url(page=0):
    # Utilisation exacte des paramètres de ton URL
    today = "2026-03-24"
    end = "2027-03-24"
    dep_params = "&".join(f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS))
    return (f"/competitions?search=&start={today}&end={end}&{dep_params}"
            f"&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC&page={page}")

# ============================
# SCRAPER AMÉLIORÉ
# ============================
def get_cards():
    cards = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

    for page in range(5): 
        target = build_target_url(page)
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        print(f"[PAGE {page}] Analyse de la page FFTA...")

        try:
            r = requests.get(proxy_url, headers=headers, timeout=30)
            if r.status_code != 200: break
        except: break

        soup = BeautifulSoup(r.text, "html.parser")
        
        # Sur la nouvelle version, les compétitions sont souvent dans des balises 'article' 
        # ou des div contenant le texte de la compétition.
        items = soup.find_all(["article", "div"], class_=["views-row", "competition-item"])
        
        # Si la recherche par classe échoue, on cherche par structure de texte (cas fréquent)
        if not items:
            # On cherche les conteneurs qui ont un lien "Détail"
            details = soup.find_all("a", string=lambda x: x and "Détail" in x)
            items = [d.find_parent(["div", "article"]) for d in details if d.find_parent(["div", "article"])]

        for item in items:
            text_full = item.get_text(" ", strip=True)
            links = item.find_all("a", href=True)
            
            mandat_url = ""
            for l in links:
                txt = l.get_text(strip=True).lower()
                hrf = l["href"].lower()
                if "mandat" in txt or "mandat" in hrf or ".pdf" in hrf:
                    mandat_url = urljoin(BASE, l["href"])
                    break
            
            # On essaie d'extraire un titre propre (souvent le premier lien ou texte en gras)
            title_tag = item.find(["h2", "h3", "strong"])
            title = title_tag.get_text(strip=True) if title_tag else text_full[:50]

            cards.append({
                "title": normalize(title),
                "text": normalize(text_full),
                "mandat": mandat_url
            })

    print(f"✅ {len(cards)} compétitions trouvées sur la FFTA.")
    return cards

# ============================
# LOGIQUE DE MISE À JOUR
# ============================
def main():
    rows, fields = load_csv()
    if "Mandat" not in fields: fields.append("Mandat")

    cards = get_cards()
    updated = 0

    for row in rows:
        # On ne traite que les lignes sans mandat (ou mandat vide)
        if len(str(row.get("Mandat", "")).strip()) > 10: continue

        v_csv = normalize(row.get("Ville", ""))
        t_csv = normalize(row.get("Titre de la compétition", ""))
        d_csv = str(row.get("Département", "")).strip()

        for card in cards:
            # MATCH : La ville doit être dans le texte FFTA ET (le titre match OU le département match)
            if v_csv in card["text"] and (t_csv in card["title"] or d_csv in card["text"]):
                if card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    print(f"  ⭐ Mandat ajouté : {row['Ville']} - {row['Titre de la compétition']}")
                    updated += 1
                break

    if updated > 0:
        save_csv(rows, fields)
        print(f"\n🚀 Terminé : {updated} mandats mis à jour dans le CSV.")
    else:
        print("\nℹ️ Aucun nouveau mandat trouvé correspondant aux épreuves vides.")

if __name__ == "__main__":
    main()
