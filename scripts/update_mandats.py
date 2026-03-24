import csv, os, time, requests, unicodedata, re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Ton URL source PDL qui fonctionne
URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&sort_by=start"

def main():
    if not os.path.exists(CSV_PATH): return print("❌ Fichier CSV introuvable.")

    # 1. Lire ton CSV tel quel
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    # 2. Scanner les pages de la FFTA pour lister les concours dispos
    print("📡 Récupération de la liste FFTA...")
    ffta_events = []
    for p_idx in range(4): # On scanne 4 pages
        try:
            r = requests.get(f"{PROXY}?target={quote(URL_ROOT + '&page=' + str(p_idx))}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "/competition/" in a['href'] or "/epreuve/" in a['href']:
                    ffta_events.append(urljoin("/", a['href']))
        except: continue
    
    ffta_events = list(set(ffta_events))
    print(f"✅ {len(ffta_events)} concours trouvés sur le site. Analyse des mandats...")

    # 3. Pour chaque concours FFTA, extraire Mandat, Date et Code Club
    updated_count = 0
    for link in ffta_events:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            
            # Extraction du mandat (on ignore le médical)
            mandat = ""
            for a in soup.find_all("a", href=True):
                href = a['href'].lower()
                if any(x in href for x in ["sante", "medical", "reglement"]): continue
                if "mandat" in a.get_text().lower() or href.endswith(".pdf"):
                    mandat = urljoin(BASE, a['href'])
                    break
            
            if not mandat: continue

            # Extraction Code Structure (7 chiffres) et Date (format JJ/MM/AAAA) dans la page
            page_text = soup.get_text()
            code_found = re.search(r'\d{7}', page_text)
            date_found = re.search(r'\d{2}/\d{2}/\d{4}', page_text)
            
            if not code_found: continue
            
            f_code = code_found.group(0)
            f_date = date_found.group(0) if date_found else ""

            # 4. MATCHING DIRECT AVEC TON CSV
            for row in rows:
                csv_code = str(row.get("Code structure", "")).strip()
                csv_date = str(row.get("Date debut", "")).strip()
                
                # SI LE CODE CLUB ET LA DATE CORRESPONDENT
                if csv_code == f_code and (not f_date or csv_date == f_date):
                    if not row.get("Mandat") or "sante" in str(row.get("Mandat")):
                        row["Mandat"] = mandat
                        print(f"⭐ Mandat trouvé pour : {row['Ville']} ({csv_date})")
                        updated_count += 1
                        break
        except: continue

    # 5. Sauvegarde (L'ordre des lignes est préservé car on ne trie pas et on n'ajoute rien)
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated_count} mandats ont été ajoutés à ton fichier original.")

if __name__ == "__main__":
    main()
