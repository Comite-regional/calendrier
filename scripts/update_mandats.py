import csv, requests, unicodedata, time, os
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# CONFIGURATION
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return s.replace("-", " ")

def main():
    if not os.path.exists(CSV_PATH): return print("Fichier CSV introuvable")
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    if "Mandat" not in fields: fields.append("Mandat")
    
    all_cards = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}

    # On boucle sur les 5 pages réelles (0 à 4)
    for page in range(5):
        dep_query = "&".join([f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS)])
        # Construction de l'URL cible interne à la FFTA
        target_path = f"/competitions?search=&start=2025-09-01&end=2026-08-31&{dep_query}&page={page}"
        
        # Envoi au Worker
        proxy_url = f"{PROXY}?target={quote(target_path)}"
        print(f"📡 Analyse FFTA Page {page}...")
        
        try:
            r = requests.get(proxy_url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
            
            for item in items:
                text_content = normalize(item.get_text(" "))
                mandat = ""
                for l in item.find_all("a", href=True):
                    if "mandat" in l.text.lower() or ".pdf" in l['href'].lower():
                        mandat = urljoin(BASE, l['href'])
                        break
                all_cards.append({"text": text_content, "mandat": mandat})
            
            time.sleep(2) # Pause de sécurité
        except Exception as e:
            print(f"❌ Erreur page {page}: {e}")

    # PHASE DE MATCHING
    updated = 0
    for row in rows:
        if len(str(row.get("Mandat", "")).strip()) > 10: continue
        
        v_csv = normalize(row.get("Ville", ""))
        code_club = str(row.get("Code structure", "")).strip()

        for card in all_cards:
            # Match prioritaire sur le Code Structure (présent dans le texte de la carte FFTA)
            if (code_club and code_club in card["text"]) or (v_csv and v_csv in card["text"]):
                if card["mandat"]:
                    row["Mandat"] = card["mandat"]
                    print(f"   ⭐ Trouvé : {row['Ville']} ({code_club})")
                    updated += 1
                    break

    if updated > 0:
        with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n🎉 Succès : {updated} mandats ajoutés !")
    else:
        print("\nℹ️ Aucun nouveau mandat trouvé.")

if __name__ == "__main__":
    main()
