import csv, os, time, requests, unicodedata, random
from urllib.parse import quote, urlparse, urljoin
from bs4 import BeautifulSoup

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9"
}

# ============================
# UTILITAIRES
# ============================
def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return s.replace("-", " ")

def get_mois_fr(date_str):
    """Extrait le nom du mois d'une date format JJ/MM/AAAA"""
    parts = date_str.split("/")
    if len(parts) < 2: return ""
    mois_map = {"01":"janvier","02":"fevrier","03":"mars","04":"avril","05":"mai","06":"juin",
                "07":"juillet","08":"aout","09":"septembre","10":"octobre","11":"novembre","12":"decembre"}
    return mois_map.get(parts[1], "")

# ============================
# SCRAPING
# ============================
def get_all_ffta_competitions():
    all_data = []
    # On boucle sur les pages de résultats filtrées par départements
    for page in range(10): # Largement suffisant pour PDL
        dep_query = "&".join([f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS)])
        # On cible la saison 2026
        target_path = f"/competitions?search=&start=2025-09-01&end=2026-10-31&{dep_query}&page={page}"
        proxy_url = f"{PROXY}?target={quote(target_path)}"
        
        print(f"📡 Analyse FFTA Page {page}...", end="\r")
        try:
            r = requests.get(proxy_url, headers=HEADERS, timeout=20)
            if r.status_code != 200: break
            
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
            
            if not items: break

            for item in items:
                text_block = normalize(item.get_text(" "))
                mandat = ""
                # Cherche le lien PDF
                for l in item.find_all("a", href=True):
                    href = l['href'].lower()
                    if "mandat" in l.text.lower() or ".pdf" in href:
                        mandat = urljoin(BASE, l['href'])
                        break
                
                if mandat:
                    all_data.append({"text": text_block, "mandat": mandat})
            
            time.sleep(1.5) # Protection anti-bot
        except: break
    
    print(f"\n🎯 {len(all_data)} épreuves avec mandat trouvées sur la FFTA.")
    return all_data

# ============================
# MAIN
# ============================
def main():
    if not os.path.exists(CSV_PATH):
        return print(f"❌ Erreur : {CSV_PATH} introuvable.")

    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    if "Mandat" not in fields: fields.append("Mandat")
    
    ffta_cards = get_all_ffta_competitions()
    updated_count = 0

    for row in rows:
        # On ne traite que si le mandat est vide (ou on peut forcer la mise à jour)
        if len(str(row.get("Mandat", "")).strip()) > 10: continue

        v_csv = normalize(row.get("Ville", ""))
        code_club = str(row.get("Code structure", "")).strip()
        discipline = normalize(row.get("Discipline", ""))
        mois = get_mois_fr(row.get("Date debut", ""))

        for card in ffta_cards:
            # --- TRIPLE VÉRIFICATION ---
            # 1. Le Code Club correspond
            # 2. Le Mois correspond (évite les erreurs de saison)
            # 3. La Ville ou la Discipline est présente
            if code_club in card["text"] and mois in card["text"]:
                if v_csv in card["text"] or discipline in card["text"]:
                    row["Mandat"] = card["mandat"]
                    print(f"   ✅ Trouvé : {row['Ville']} - {discipline} ({mois})")
                    updated_count += 1
                    break

    # Sauvegarde
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n🚀 Terminé : {updated_count} mandats correctement ajoutés au CSV.")

if __name__ == "__main__":
    main()
