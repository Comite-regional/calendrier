import csv, os, time, requests, unicodedata
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# URL Racine (ton filtre qui fonctionne)
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

    # 1. Collecter les liens de détails
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
    print(f"\n✅ {len(links)} épreuves à analyser dans le détail.")

    # 2. Analyse détaillée et extraction chirurgicale du mandat
    updated = 0
    for link in links:
        print(f"🔎 Analyse : {link}      ", end="\r")
        try:
            res = requests.get(f"{PROXY}?target={quote(link)}", timeout=15)
            detail_soup = BeautifulSoup(res.text, "html.parser")
            
            # Recherche du mandat avec plusieurs méthodes
            mandat_url = ""
            # Méthode A : Chercher un lien qui contient "mandat" ou finit par .pdf
            for a in detail_soup.find_all("a", href=True):
                href = a['href'].lower()
                text = a.get_text().lower()
                if "mandat" in text or "mandat" in href or href.endswith(".pdf"):
                    mandat_url = urljoin(BASE, a['href'])
                    break
            
            # Méthode B : Si rien trouvé, chercher des boutons de téléchargement
            if not mandat_url:
                for btn in detail_soup.find_all(["button", "div"], string=lambda x: x and "mandat" in x.lower()):
                    # Parfois le lien est dans le parent
                    parent_a = btn.find_parent("a", href=True)
                    if parent_a:
                        mandat_url = urljoin(BASE, parent_a['href'])
                        break

            if not mandat_url: continue

            # --- MATCHING AVEC LE CSV ---
            # On récupère le texte complet pour identifier le club
            page_content = normalize(detail_soup.get_text(" "))
            
            for row in rows:
                # On ne remplit que si le mandat est vide
                if len(str(row.get("Mandat", ""))) > 10: continue
                
                code_club = str(row.get("Code structure", "")).strip()
                ville_csv = normalize(row.get("Ville", ""))
                
                # Si le Code Structure est dans la page, c'est le bon !
                if code_club and code_club in page_content:
                    # On valide avec la ville pour être certain
                    if ville_csv in page_content:
                        row["Mandat"] = mandat_url
                        print(f"\n⭐ MANDAT AJOUTÉ : {row['Ville']} ({code_club})")
                        updated += 1
                        break
        except Exception as e:
            continue
        time.sleep(0.3)

    # 3. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🎉 Succès : {updated} mandats ont été insérés dans le CSV !")

if __name__ == "__main__":
    main()
