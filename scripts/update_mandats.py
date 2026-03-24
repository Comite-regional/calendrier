import csv, os, time, requests, unicodedata, re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Ton URL source validée
URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC"

def clean_text(s):
    """Nettoie le texte de façon agressive (minuscules, pas d'accents, pas de ponctuation)"""
    if not s: return ""
    s = str(s).lower()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', s) # On ne garde que les lettres et chiffres

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
                h = a['href']
                if "/competition/" in h or "/epreuve/" in h:
                    detail_links.append(urljoin("/", h))
        except: continue

    links = list(set(detail_links))
    print(f"\n✅ {len(links)} épreuves trouvées. Analyse en profondeur...")

    # 2. Analyse et Extraction
    updated = 0
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            # 1. On cherche le mandat (PDF ou texte "Mandat")
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                text = a.get_text().lower()
                if "mandat" in text or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url: continue

            # 2. On prépare le texte de la page pour le matching
            page_content_clean = clean_text(detail_soup.get_text())
            
            # 3. On compare avec chaque ligne du CSV
            for row in rows:
                # On ignore les lignes qui ont déjà un mandat
                if len(str(row.get("Mandat", ""))) > 10: continue
                
                code_club = clean_text(row.get("Code structure", ""))
                ville = clean_text(row.get("Ville", ""))
                
                # MATCH : Si le code club est présent OU si la ville est présente avec le nom du club
                # (Le code club est plus fiable)
                if code_club and code_club in page_content_clean:
                    row["Mandat"] = mandat_url
                    print(f"   ⭐ MATCH TROUVÉ : {row['Ville']} | Club: {row['Code structure']}")
                    updated += 1
                    break
                elif ville and ville in page_content_clean and clean_text(row.get("Club organisateur", "")) in page_content_clean:
                    row["Mandat"] = mandat_url
                    print(f"   ⭐ MATCH (Ville/Club) : {row['Ville']}")
                    updated += 1
                    break
                        
        except Exception: continue
        time.sleep(0.2)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats ont été injectés dans le CSV.")

if __name__ == "__main__":
    main()
