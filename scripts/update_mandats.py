import csv, os, time, requests, unicodedata, re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# URL PDL (Pages 0 à 4)
URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&sort_by=start"

def normalize(s):
    """Nettoie le texte pour la comparaison (minuscules, sans accents)"""
    if not s: return ""
    return unicodedata.normalize("NFD", str(s).lower().strip()).encode("ascii", "ignore").decode("utf-8")

def main():
    if not os.path.exists(CSV_PATH): return print("❌ Fichier CSV introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    # 1. Collecte des liens
    links = []
    for p in range(5):
        print(f"📡 Scan FFTA Page {p+1}...", end="\r")
        try:
            r = requests.get(f"{PROXY}?target={quote(URL_ROOT + '&page=' + str(p))}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "/competition/" in a['href'] or "/epreuve/" in a['href']:
                    links.append(urljoin("/", a['href']))
        except: continue
    
    links = list(set(links))
    print(f"\n✅ {len(links)} concours trouvés. Analyse en cours...")

    # 2. Analyse et Injection
    updated = 0
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            soup = BeautifulSoup(res.text, "html.parser")
            page_text = normalize(soup.get_text())

            # Chercher le mandat
            mandat_url = ""
            for a in soup.find_all("a", href=True):
                h = a['href'].lower()
                if any(x in h for x in ["sante", "medical", "reglement"]): continue
                if "mandat" in a.get_text().lower() or h.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url: continue

            # MATCHING : On compare la Ville et la Date du CSV avec la page
            for row in rows:
                # Si le mandat est déjà là, on passe
                if len(str(row.get("Mandat", ""))) > 10: continue
                
                ville_csv = normalize(row.get("Ville", ""))
                date_csv = str(row.get("Date debut", "")).strip() # Ex: 21/03/2026
                
                # CONDITION : La ville ET la date doivent être dans la page
                if date_csv in page_text and ville_csv in page_text:
                    row["Mandat"] = mandat_url
                    print(f"⭐ MATCH : {row['Ville']} le {date_csv}")
                    updated += 1
                    break
        except: continue
        time.sleep(0.1)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats ajoutés.")

if __name__ == "__main__":
    main()
