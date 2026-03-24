import csv, os, time, requests, unicodedata, re
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Ton URL source PDL
URL_ROOT = "/competitions?search=&start=2026-03-24&end=2027-03-24&dep%5B0%5D=45&dep%5B1%5D=50&dep%5B2%5D=54&dep%5B3%5D=73&dep%5B4%5D=86&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC"

def clean_text(s):
    if not s: return ""
    s = str(s).lower()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', s)

def main():
    if not os.path.exists(CSV_PATH): return print("❌ Fichier CSV introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

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
    print(f"\n✅ {len(links)} épreuves trouvées sur FFTA.")

    # 2. Analyse et Matching / Ajout
    updated = 0
    added = 0
    
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            # Extraction infos de base
            titre_page = detail_soup.find("h1").get_text(strip=True) if detail_soup.find("h1") else "Sans titre"
            page_content_clean = clean_text(detail_soup.get_text())
            
            # Extraction Mandat
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                if "sante-et-tir-larc" in href: continue
                if "mandat" in a.get_text().lower() or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            # On cherche si le club (ou l'épreuve) existe déjà dans notre CSV
            found_in_csv = False
            for row in rows:
                code_club = clean_text(row.get("Code structure", ""))
                if code_club and code_club in page_content_clean:
                    # On a trouvé la ligne, on met juste à jour le mandat
                    if not row.get("Mandat"):
                        row["Mandat"] = mandat_url
                        updated += 1
                    found_in_csv = True
                    break
            
            # SI PAS TROUVÉ : ON AJOUTE UNE NOUVELLE LIGNE
            if not found_in_csv:
                new_row = {f: "" for f in fields} # On crée une ligne vide avec les bonnes colonnes
                new_row["Titre compétition"] = titre_page
                new_row["Mandat"] = mandat_url
                # On essaie de deviner la ville dans le titre
                new_row["Ville"] = titre_page.split("-")[-1].strip() 
                rows.append(new_row)
                print(f"➕ NOUVELLE ÉPREUVE AJOUTÉE : {titre_page}")
                added += 1
                        
        except Exception: continue

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats complétés et {added} nouvelles épreuves créées.")

if __name__ == "__main__":
    main()
