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
CSV_PATH = "concours26-3.csv"
# Ton Worker Cloudflare pour contourner la protection
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Départements Pays de la Loire
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

# ============================
# GESTION CSV
# ============================
def load_csv():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Erreur : Le fichier {CSV_PATH} est introuvable.")
        return [], []
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        # On utilise le point-virgule comme dans ton fichier
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    return rows, fields

def save_csv(rows, fields):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

# ============================
# UTILITAIRES
# ============================
def normalize(s):
    """Supprime les accents, met en minuscule et nettoie les espaces"""
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

def build_target_url(page=0):
    today = date.today().isoformat()
    # On cherche sur une large période pour couvrir la saison 2026
    end = "2026-09-30"
    dep_params = "&".join(f"dep%5B%5D={d}" for d in DEPARTEMENTS)
    url = (
        f"/competitions?search=&start={today}&end={end}"
        f"&{dep_params}"
        f"&discipline=All&univers=All&inter=All"
        f"&sort_by=start&sort_order=ASC&page={page}"
    )
    return url

# ============================
# SCRAPING FFTA
# ============================
def get_cards():
    cards = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for page in range(10):  # On scanne les 10 premières pages de résultats
        target = build_target_url(page)
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        print(f"[PAGE {page}] Scraping via Proxy...")

        try:
            r = requests.get(proxy_url, headers=headers, timeout=25)
            if r.status_code != 200:
                print(f"  ❌ HTTP {r.status_code} sur la page {page}")
                break
        except Exception as e:
            print(f"  ❌ Erreur réseau : {e}")
            break

        soup = BeautifulSoup(r.text, "html.parser")
        
        # On cherche les liens vers les fiches épreuves
        links = [a for a in soup.find_all("a", href=True) if "/competitions/" in a["href"]]
        
        if not links:
            print("  → Plus de compétitions trouvées.")
            break

        for a in links:
            title_raw = a.get_text(strip=True)
            if not title_raw or len(title_raw) < 5: continue

            # On remonte au parent pour trouver le mandat PDF dans le même bloc
            # La FFTA utilise souvent des div 'views-row' ou 'card'
            block = a.find_parent("div", class_="views-row") or a.parent.parent.parent
            
            text_context = normalize(block.get_text(" "))
            epreuve_url = urljoin(BASE, a["href"])

            # Extraction du mandat (PDF)
            mandat_url = ""
            for link in block.find_all("a", href=True):
                href = link["href"].lower()
                l_text = link.get_text(strip=True).lower()
                if "mandat" in l_text or "mandat" in href or "/documents/" in href:
                    mandat_url = urljoin(BASE, link["href"])
                    break

            cards.append({
                "title": normalize(title_raw),
                "text": text_context,
                "mandat": mandat_url,
                "url": epreuve_url,
                "raw_name": title_raw
            })

        time.sleep(1) # Sécurité pour le proxy
    
    print(f"✅ {len(cards)} compétitions récupérées sur la FFTA.\n")
    return cards

# ============================
# LOGIQUE DE CORRESPONDANCE
# ============================
def is_match(row, card):
    # Noms des colonnes exacts de ton CSV
    titre_csv = normalize(row.get("Titre de la compétition", ""))
    ville_csv = normalize(row.get("Ville", ""))
    dep_csv = str(row.get("Département", "")).strip()

    # Si on n'a ni titre ni ville, on ne peut pas comparer
    if not titre_csv and not ville_csv:
        return False

    # 1. Vérification par ville (très fiable)
    ville_match = ville_csv != "" and ville_csv in card["text"]
    
    # 2. Vérification par titre (contient souvent le nom du club)
    # On vérifie si une partie du titre CSV est dans le titre FFTA
    titre_match = titre_csv != "" and (titre_csv in card["title"] or card["title"] in titre_csv)

    # 3. Vérification du département pour éviter les homonymes de villes
    dep_match = dep_csv != "" and dep_csv in card["text"]

    # On valide si (Ville ou Titre) match ET que le département correspond
    return (ville_match or titre_match) and dep_match

# ============================
# MAIN
# ============================
def main():
    rows, fields = load_csv()
    if not rows: return

    # S'assurer que la colonne Mandat existe
    if "Mandat" not in fields:
        fields.append("Mandat")

    # On ne traite que ceux qui n'ont pas de mandat (vide ou lien trop court)
    lignes_a_traiter = [r for r in rows if len(str(r.get("Mandat", "")).strip()) < 5]
    print(f"🚀 Analyse de {len(lignes_a_traiter)} lignes sans mandat...")

    cards = get_cards()
    count_updated = 0

    for row in rows:
        # Skip si déjà un mandat
        if len(str(row.get("Mandat", "")).strip()) > 5:
            continue

        for card in cards:
            if is_match(row, card):
                if card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    print(f"  ✅ TROUVÉ : {row.get('Ville')} ({row.get('Titre de la compétition')})")
                    count_updated += 1
                else:
                    # On peut stocker l'URL de l'épreuve si le PDF n'est pas encore là
                    print(f"  ⚠️ MATCH SANS PDF : {row.get('Ville')} -> Voir {card['url']}")
                break

    if count_updated > 0:
        save_csv(rows, fields)
        print(f"\n🎉 Terminé ! {count_updated} mandats ajoutés au CSV.")
    else:
        print("\n¯\_(ツ)_/¯ Aucun nouveau mandat trouvé cette fois-ci.")

if __name__ == "__main__":
    main()
