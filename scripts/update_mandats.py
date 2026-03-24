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
    if not s: return ""
    s = str(s).lower()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return re.sub(r'[^a-z0-9]', '', s)

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
    print(f"\n✅ {len(links)} épreuves à vérifier.")

    # 2. Analyse et Extraction
    updated = 0
    for link in links:
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            # --- RECHERCHE DU MANDAT AVEC EXCLUSION ---
            mandat_url = ""
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                text = a.get_text().lower()
                
                # On exclut les pages de santé/recommandations
                if "sante-et-tir-larc" in href or "recommandations-medicales" in href:
                    continue
                
                # On accepte si c'est un PDF ou si le texte contient "mandat"
                if "mandat" in text or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            if not mandat_url:
                continue

            page_content_clean = clean_text(detail_soup.get_text())
            
            for row in rows:
                # On ne remplit QUE si c'est vide ou si c'était l'erreur "santé"
                current_mandat = str(row.get("Mandat", ""))
                if "sante-et-tir-larc" not in current_mandat and len(current_mandat) > 10:
                    continue
                
                code_club = clean_text(row.get("Code structure", ""))
                
                if code_club and code_club in page_content_clean:
                    row["Mandat"] = mandat_url
                    print(f"   ⭐ MANDAT VALIDE : {row['Ville']} | {mandat_url[-30:]}")
                    updated += 1
                    break
                        
        except Exception: continue
        time.sleep(0.2)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Terminé ! {updated} mandats réels ajoutés (les faux ont été ignorés).")

if __name__ == "__main__":
    main()
