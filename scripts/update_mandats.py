import csv, os, time, requests, unicodedata, re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup
from datetime import datetime

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC"

def clean_simple(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', s)

def parse_date(date_str):
    """Convertit JJ/MM/AAAA en objet date pour le tri"""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y")
    except:
        return datetime(9999, 12, 31) # Envoie les dates invalides à la fin

def main():
    if not os.path.exists(CSV_PATH): return print("❌ Fichier CSV introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    # 1. Collecte FFTA
    detail_links = []
    for p_idx in range(3): 
        target = f"{URL_ROOT}&page={p_idx}"
        print(f"📡 Scan FFTA Page {p_idx+1}...", end="\r")
        try:
            r = requests.get(f"{PROXY}?target={quote(target)}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "/competition/" in a['href'] or "/epreuve/" in a['href']:
                    detail_links.append(urljoin("/", a['href']))
        except: continue

    links = list(set(detail_links))
    print(f"\n✅ {len(links)} épreuves trouvées.")

    added = 0
    updated = 0

    # 2. Analyse et Ajout
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            titre_ffta = detail_soup.find("h1").get_text(strip=True) if detail_soup.find("h1") else ""
            page_text = clean_simple(detail_soup.get_text())
            
            # Extraction Date (souvent dans un bloc spécifique sur FFTA)
            date_ffta = ""
            date_box = detail_soup.find("div", class_="date-display-single")
            if date_box: date_ffta = date_box.get_text(strip=True)
            # Si format FFTA est "25/03/2026", on le garde, sinon on peut tenter de l'extraire du texte

            # Mandat
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                if any(x in href for x in ["sante", "medical"]): continue
                if "mandat" in a.get_text().lower() or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break

            found = False
            for row in rows:
                if clean_simple(row.get("Code structure", "")) in page_text:
                    if mandat_url and not row.get("Mandat"):
                        row["Mandat"] = mandat_url
                        updated += 1
                    found = True
                    break

            if not found:
                new_row = {f: "" for f in fields}
                new_row["Titre compétition"] = titre_ffta
                new_row["Mandat"] = mandat_url
                new_row["Saison"] = "2026"
                # On essaie de récupérer la date si possible (format attendu JJ/MM/AAAA)
                # Note: Si FFTA affiche "25 Mars", il faudra un petit convertisseur
                rows.append(new_row)
                added += 1
                print(f"➕ Ajouté : {titre_ffta}")

        except: continue

    # ==========================================
    # 3. LE TRI (C'est ici que l'ordre se répare)
    # ==========================================
    # On trie la liste de dictionnaires par la colonne 'Date debut'
    print("⚖️ Tri du fichier par date...")
    rows.sort(key=lambda x: parse_date(x.get("Date debut", "")))

    # 4. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Fichier sauvegardé et trié ! ({updated} mandats, {added} nouveaux)")

if __name__ == "__main__":
    main()
