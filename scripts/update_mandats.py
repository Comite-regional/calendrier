import csv, os, time, requests, unicodedata
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# L'URL racine basée sur tes liens (Page 1 = page=0)
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

    # 1. Collecter les liens de détails sur tes pages spécifiques
    detail_links = []
    # On scanne les pages 0, 1, 2, 3... (ajuste le range si besoin)
    for p_idx in range(5): 
        target = f"{URL_ROOT}&page={p_idx}"
        print(f"📡 Analyse de ta Page {p_idx+1} (index {p_idx})...", end="\r")
        try:
            r = requests.get(f"{PROXY}?target={quote(target)}", timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            
            items_found = 0
            for a in soup.find_all("a", href=True):
                href = a['href']
                if "/competition/" in href or "/epreuve/" in href:
                    detail_links.append(urljoin("/", href))
                    items_found += 1
            if items_found == 0: break # Plus de résultats
        except: continue

    links = list(set(detail_links))
    print(f"\n✅ {len(links)} fiches identifiées sur tes pages FFTA.")

    # 2. Analyse profonde de chaque fiche
    updated = 0
    for link in links:
        print(f"🔎 Analyse : {link}      ", end="\r")
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            page_text = normalize(detail_soup.get_text(" "))

            # Extraction du mandat (PDF ou lien "Mandat")
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                txt = a.get_text().lower()
                href = a['href'].lower()
                if "mandat" in txt or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url: continue

            # Matching avec ton CSV via le Code Structure
            for row in rows:
                code_club = str(row.get("Code structure", "")).strip()
                if code_club and code_club in page_text:
                    # Sécurité supplémentaire : la ville
                    if normalize(row.get("Ville", "")) in page_text:
                        row["Mandat"] = mandat_url
                        print(f"\n✨ Trouvé : {row['Ville']} ({code_club})")
                        updated += 1
                        break
        except: continue
        time.sleep(0.2)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats associés avec succès.")

if __name__ == "__main__":
    main()
