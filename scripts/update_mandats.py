import csv, requests, unicodedata, time, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26-3.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

def build_target_url(page=0):
    dep_params = "&".join(f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS))
    # On ratisse toute la saison 2026
    return (f"/competitions?search=&start=2025-09-01&end=2026-08-31&{dep_params}"
            f"&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC&page={page}")

def get_all_cards():
    cards = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    page = 0
    
    print(f"🚀 Scan de la FFTA en cours...")
    while True:
        target = build_target_url(page)
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        print(f"   Scraping page {page}...", end="\r")
        
        try:
            r = requests.get(proxy_url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
            
            if not items or page > 60: # Sécurité stop
                break

            for item in items:
                text_content = normalize(item.get_text(" "))
                mandat = ""
                for l in item.find_all("a", href=True):
                    h, t = l['href'].lower(), l.get_text().lower()
                    if "mandat" in t or "mandat" in h or ".pdf" in h:
                        mandat = urljoin(BASE, l['href'])
                        break
                cards.append({"text": text_content, "mandat": mandat})
            page += 1
        except: break
    print(f"\n🎯 {len(cards)} épreuves trouvées sur la FFTA.")
    return cards

def main():
    if not os.path.exists(CSV_PATH): return print("Fichier introuvable")
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    # On s'assure que la colonne Mandat existe
    if "Mandat" not in fields: fields.append("Mandat")
    
    cards = get_all_cards()
    updated_count = 0

    for row in rows:
        # On ne traite que si Mandat est vide ou contient juste un espace
        m_actuel = str(row.get("Mandat", "")).strip()
        if len(m_actuel) > 10: continue 

        # Nettoyage des données CSV pour le match
        v_csv = normalize(row.get("Ville", ""))
        d_csv = str(row.get("Departement", "")).strip()
        t_csv = normalize(row.get("Titre compétition", "")) # Nom exact dans ton CSV

        for card in cards:
            # LOGIQUE DE MATCH : La ville ET (le département OU une partie du titre)
            if v_csv and v_csv in card["text"]:
                if (d_csv in card["text"] or t_csv[:10] in card["text"]) and card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    print(f"   ⭐ MATCH : {row['Ville']} -> Mandat ajouté")
                    updated_count += 1
                    break

    # Sauvegarde finale
    if updated_count > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n✅ TERMINÉ : {updated_count} mandats insérés dans {CSV_PATH}.")
    else:
        print("\n❌ Aucun nouveau match. Vérifie que les noms de tes colonnes 'Ville' et 'Departement' n'ont pas d'espaces cachés.")

if __name__ == "__main__":
    main()
