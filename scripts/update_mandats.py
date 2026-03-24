import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
from datetime import date
import unicodedata
import time

# ============================
# CONFIG
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Départements Pays de la Loire (CORRECTS)
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

# ============================
# CSV
# ============================
def load_csv():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = list(reader.fieldnames)
    return rows, fields

def save_csv(rows, fields):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

# ============================
# NORMALISATION
# ============================
def normalize(s):
    """Supprime accents, met en minuscule"""
    s = (s or "").lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

# ============================
# CONSTRUCTION URL FFTA
# ============================
def build_target_url(page=0):
    today = date.today().isoformat()
    end = "2027-03-24"
    # Construction manuelle pour gérer les dep[] correctement
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
    for page in range(20):  # jusqu'à 20 pages
        target = build_target_url(page)
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        print(f"\n[PAGE {page}] {proxy_url}")

        try:
            r = requests.get(proxy_url, timeout=20)
        except Exception as e:
            print(f"  ❌ Erreur réseau : {e}")
            continue

        if r.status_code != 200:
            print(f"  ❌ HTTP {r.status_code}")
            continue

        soup = BeautifulSoup(r.text, "html.parser")
        epreuves = [a for a in soup.find_all("a", href=True) if "/epreuve/" in a["href"]]
        print(f"  → {len(epreuves)} épreuves trouvées")

        if len(epreuves) == 0:
            print("  → Page vide, arrêt du scraping.")
            break

        for a in epreuves:
            title = a.get_text(strip=True)
            # Remonter dans le DOM pour avoir plus de contexte
            block = a.parent
            for _ in range(3):  # remonter jusqu'à 3 niveaux
                if block.parent:
                    block = block.parent

            text = block.get_text(" ", strip=True)
            epreuve_url = urljoin(BASE, a["href"])

            # Chercher le lien mandat
            mandat = ""
            for link in block.find_all("a", href=True):
                href = link["href"]
                link_text = link.get_text(strip=True).lower()
                href_lower = href.lower()
                if (
                    "mandat" in href_lower
                    or "mandat" in link_text
                    or "/medias/documents_epreuves/" in href_lower
                ):
                    mandat = urljoin(BASE, href)
                    break

            cards.append({
                "title": normalize(title),
                "text": normalize(text),
                "mandat": mandat,
                "epreuve_url": epreuve_url,
                "title_raw": title,
            })

        time.sleep(0.5)  # pause pour ne pas surcharger le proxy

    print(f"\n✅ Total cards scrapées : {len(cards)}")
    return cards

# ============================
# CORRESPONDANCE
# ============================
def match(row, card):
    titre_csv = normalize(row.get("Titre compétition") or "")
    ville_csv = normalize(row.get("Ville") or "")

    if not titre_csv and not ville_csv:
        return False

    titre_match = titre_csv and titre_csv in card["title"]
    ville_match = ville_csv and ville_csv in card["text"]

    return titre_match and ville_match

# ============================
# MISE À JOUR
# ============================
def update_mandats(rows, cards):
    added = []
    skipped_no_mandat = []

    for row in rows:
        # Ignorer les lignes qui ont déjà un mandat
        if row.get("Mandat", "").strip():
            continue

        for card in cards:
            if match(row, card):
                if card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    label = f"{row.get('Titre compétition')} - {row.get('Ville')} ({row.get('Departement')})"
                    added.append(label)
                    print(f"  ✓ {label}")
                else:
                    label = f"{row.get('Titre compétition')} - {row.get('Ville')} → {card['epreuve_url']}"
                    skipped_no_mandat.append(label)
                    print(f"  ⚠ Match mais pas de mandat PDF : {label}")
                break

    return added, skipped_no_mandat

# ============================
# MAIN
# ============================
def main():
    rows, fields = load_csv()
    print(f"📄 {len(rows)} lignes dans le CSV")

    # S'assurer que la colonne Mandat existe
    if "Mandat" not in fields:
        fields.append("Mandat")
        for row in rows:
            row.setdefault("Mandat", "")

    # Compter les lignes sans mandat
    sans_mandat = [r for r in rows if not r.get("Mandat", "").strip()]
    print(f"🔍 {len(sans_mandat)} lignes sans mandat à traiter\n")

    cards = get_cards()

    print("\n=== MISE À JOUR ===")
    added, skipped = update_mandats(rows, cards)

    save_csv(rows, fields)

    print("\n=== RAPPORT FINAL ===")
    print(f"✅ Mandats ajoutés : {len(added)}")
    for a in added:
        print(f"   - {a}")

    if skipped:
        print(f"\n⚠ Matchs trouvés sans PDF mandat : {len(skipped)}")
        for s in skipped:
            print(f"   - {s}")

    print(f"\n📊 Résumé : {len(added)} mis à jour, {len(skipped)} sans PDF")

if __name__ == "__main__":
    main()
