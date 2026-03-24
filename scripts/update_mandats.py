import csv, os, time, requests, unicodedata
from urllib.parse import quote, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return s.replace("-", " ")

def get_detail_data(detail_url):
    """Ouvre la page de détail d'une compétition pour extraire les infos et le mandat"""
    proxy_url = f"{PROXY}?target={quote(detail_url)}"
    try:
        r = requests.get(proxy_url, timeout=15)
        if r.status_code != 200: return None
        
        soup = BeautifulSoup(r.text, "html.parser")
        full_text = normalize(soup.get_text(" "))
        
        # Recherche du mandat dans la page de détail
        mandat = ""
        for a in soup.find_all("a", href=True):
            href = a['href'].lower()
            txt = a.get_text().lower()
            if "mandat" in txt or "mandat" in href or href.endswith(".pdf"):
                mandat = urljoin(BASE, a['href'])
                break
        
        return {"text": full_text, "mandat": mandat}
    except:
        return None

def main():
    if not os.path.exists(CSV_PATH): return print("Fichier CSV introuvable")

    # 1. Charger le CSV
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames
    if "Mandat" not in fields: fields.append("Mandat")

    print(f"🚀 Démarrage du Deep Scraping sur {len(rows)} lignes...")

    # 2. Parcourir les pages de la FFTA pour trouver les liens "Détail"
    competitions_to_check = []
    for page in range(6):
        dep_query = "&".join([f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS)])
        listing_path = f"/competitions?search=&start=2025-09-01&end=2026-08-31&{dep_query}&page={page}"
        proxy_url = f"{PROXY}?target={quote(listing_path)}"
        
        print(f"📂 Récupération des liens - Page {page}...", end="\r")
        try:
            r = requests.get(proxy_url, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            # On cherche les liens vers les épreuves
            for a in soup.find_all("a", href=True):
                if "/competition/" in a['href'] or "/epreuve/" in a['href']:
                    competitions_to_check.append(urljoin("/", a['href']))
        except: continue
    
    # Supprimer les doublons de liens
    competitions_to_check = list(set(competitions_to_check))
    print(f"\n🔍 {len(competitions_to_check)} fiches détaillées à analyser...")

    # 3. Analyser chaque fiche et comparer avec le CSV
    updated = 0
    for detail_path in competitions_to_check:
        print(f"🔎 Analyse de : {detail_path}...", end="\r")
        data = get_detail_data(detail_path)
        
        if not data or not data["mandat"]: continue

        # Comparaison avec chaque ligne du CSV
        for row in rows:
            # Si déjà rempli, on passe
            if len(str(row.get("Mandat", ""))) > 10: continue

            code_club = str(row.get("Code structure", "")).strip()
            ville = normalize(row.get("Ville", ""))
            
            # Si le code club est dans la page de détail, c'est le bon club !
            if code_club and code_club in data["text"]:
                # On vérifie la ville pour être sûr à 100%
                if ville in data["text"]:
                    row["Mandat"] = data["mandat"]
                    print(f"\n✅ MANDAT TROUVÉ : {row['Ville']} (Club {code_club})")
                    updated += 1
                    break
        
        time.sleep(0.5) # Petite pause pour le proxy

    # 4. Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n✨ Terminé ! {updated} mandats ajoutés avec précision chirurgicale.")

if __name__ == "__main__":
    main()
