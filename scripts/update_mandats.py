import csv, os, time, requests, unicodedata
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Ton URL source (Page 1 à 5)
URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC"

def normalize(s):
    if not s: return ""
    return unicodedata.normalize("NFD", str(s).lower().strip()).encode("ascii", "ignore").decode("utf-8")

def main():
    if not os.path.exists(CSV_PATH): return print(f"❌ Fichier {CSV_PATH} introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    if "Mandat" not in fields: fields.append("Mandat")

    # 1. Collecte des liens
    detail_links = []
    for p_idx in range(5): 
        target = f"{URL_ROOT}&page={p_idx}"
        print(f"📡 Scan Liste (Page {p_idx+1})...", end="\r")
        try:
            r = requests.get(f"{PROXY}?target={quote(target)}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            for a in soup.find_all("a", href=True):
                if "/competition/" in a['href'] or "/epreuve/" in a['href']:
                    detail_links.append(urljoin("/", a['href']))
        except: continue

    links = list(set(detail_links))
    print(f"\n✅ {len(links)} épreuves détectées. Analyse des détails en cours...")

    # 2. Analyse et Extraction
    updated = 0
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            # 🔍 LOGIQUE D'EXTRACTION DU MANDAT
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                text = a.get_text().lower()
                # On cherche "mandat" ou un PDF direct
                if "mandat" in text or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url:
                continue

            # 🔍 LOGIQUE DE MATCHING
            # On récupère tout le texte de la page pour comparer
            page_text = normalize(detail_soup.get_text(" "))
            
            for row in rows:
                # Si la ligne a déjà un mandat, on passe à la suivante
                if len(str(row.get("Mandat", ""))) > 10: continue
                
                code_club = str(row.get("Code structure", "")).strip()
                ville_csv = normalize(row.get("Ville", ""))
                
                # CRITÈRE : Le code structure doit être dans la page
                if code_club and code_club in page_text:
                    # On vérifie si la ville est aussi mentionnée pour éviter les erreurs
                    if ville_csv in page_text or not ville_csv:
                        row["Mandat"] = mandat_url
                        print(f"   ⭐ MATCH : {row['Ville']} | Club: {code_club} | Mandat: {mandat_url[:50]}...")
                        updated += 1
                        break
                        
        except Exception: continue
        time.sleep(0.2)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats ajoutés au fichier.")

if __name__ == "__main__":
    main()
