import csv, requests, unicodedata, time, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"

# Départements Pays de la Loire
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s

def build_target_url(page=0):
    # On cible spécifiquement la saison 2026 pour limiter le nombre de pages
    dep_params = "&".join(f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS))
    return (f"/competitions?search=&start=2025-09-01&end=2026-08-31&{dep_params}"
            f"&discipline=All&univers=All&inter=All&sort_by=start&sort_order=ASC&page={page}")

def get_all_cards():
    cards = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    
    page = 0
    while True: # Boucle infinie jusqu'à la fin des résultats
        target = build_target_url(page)
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        print(f"  -> Analyse FFTA Page {page}...", end="\r")
        
        try:
            r = requests.get(proxy_url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            
            # On cherche les blocs de compétition
            items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
            
            # Si la page est vide ou ne contient pas de compétitions, on s'arrête
            if not items:
                print(f"\n✅ Fin des résultats atteinte à la page {page}.")
                break

            for item in items:
                text_content = normalize(item.get_text(" "))
                
                # Extraction du Mandat
                mandat = ""
                for l in item.find_all("a", href=True):
                    h = l['href'].lower()
                    t = l.get_text().lower()
                    if "mandat" in t or "mandat" in h or ".pdf" in h:
                        mandat = urljoin(BASE, l['href'])
                        break
                
                cards.append({"text": text_content, "mandat": mandat})
            
            page += 1
            time.sleep(0.5) # Petite pause pour ne pas saturer le proxy
            
        except Exception as e:
            print(f"\n❌ Erreur page {page}: {e}")
            break
            
    return cards

def main():
    if not os.path.exists(CSV_PATH): 
        return print(f"❌ Erreur : {CSV_PATH} non trouvé.")
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    if "Mandat" not in fields: fields.append("Mandat")
    
    print(f"🚀 Démarrage du scan complet de la FFTA...")
    all_ffta_cards = get_all_cards()
    print(f"🎯 Total épreuves récupérées : {len(all_ffta_cards)}")
    
    updated = 0
    for row in rows:
        # On ne traite que ceux qui n'ont pas de lien valide
        if len(str(row.get("Mandat", "")).strip()) > 10:
            continue

        v_csv = normalize(row.get("Ville", ""))
        # On check les deux noms de colonnes possibles pour le département
        d_csv = str(row.get("Departement") or row.get("Département") or "").strip()
        
        if not v_csv: continue

        for card in all_ffta_cards:
            # Si la ville et le département sont présents dans le bloc de texte de la FFTA
            if v_csv in card["text"] and d_csv in card["text"]:
                if card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    print(f"   ⭐ MATCH : {row['Ville']} ({d_csv})")
                    updated += 1
                    break

    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n🎉 Succès : {updated} mandats ajoutés au CSV !")
    else:
        print("\nℹ️ Aucun nouveau mandat n'a pu être associé.")

if __name__ == "__main__":
    main()
