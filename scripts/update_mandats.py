import csv, requests, unicodedata, time, os, random
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# ============================
# CONFIGURATION
# ============================
CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"
DEPARTEMENTS = ["44", "49", "53", "72", "85"]

# Liste de User-Agents pour tromper la détection
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
]

def normalize(s):
    if not s: return ""
    s = str(s).lower().strip()
    s = unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("utf-8")
    return s.replace("-", " ")

def get_all_cards():
    cards = []
    page = 0
    max_pages = 65 
    
    print(f"🚀 Lancement du scan profond (Objectif: {max_pages} pages)")
    
    while page < max_pages:
        dep_params = "&".join(f"dep%5B{i}%5D={d}" for i, d in enumerate(DEPARTEMENTS))
        target = f"/competitions?search=&start=2025-09-01&end=2026-08-31&{dep_params}&page={page}"
        proxy_url = f"{PROXY}?target={quote(target, safe='')}"
        
        headers = {"User-Agent": random.choice(USER_AGENTS)}
        
        try:
            r = requests.get(proxy_url, headers=headers, timeout=20)
            soup = BeautifulSoup(r.text, "html.parser")
            items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
            
            if not items:
                # Petite sécurité : si page vide, on attend un peu et on retente une fois
                print(f"\n⚠️ Page {page} semble vide. Nouvelle tentative dans 5s...")
                time.sleep(5)
                r = requests.get(proxy_url, headers=headers, timeout=20)
                soup = BeautifulSoup(r.text, "html.parser")
                items = soup.find_all(["article", "div"], class_=["views-row", "competition-item", "card"])
                if not items:
                    print("🏁 Fin réelle des résultats ou blocage définitif.")
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
            
            print(f"   ✅ Page {page} traitée ({len(items)} épreuves)", end="\r")
            
            # PAUSE CRUCIALE pour éviter le ban
            time.sleep(random.uniform(1.5, 3.0))
            page += 1
            
        except Exception as e:
            print(f"\n❌ Erreur page {page}: {e}")
            break
            
    print(f"\n🎯 Total : {len(cards)} compétitions en mémoire.")
    return cards

def main():
    if not os.path.exists(CSV_PATH): return print("Fichier CSV introuvable")
    
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        fields = reader.fieldnames

    if "Mandat" not in fields: fields.append("Mandat")
    
    cards = get_all_cards()
    updated = 0

    for row in rows:
        if len(str(row.get("Mandat", "")).strip()) > 10: continue

        v_csv = normalize(row.get("Ville", ""))
        v_comp = normalize(row.get("Ville compétition", ""))
        d_csv = str(row.get("Departement", "")).strip()
        code_club = str(row.get("Code structure", "")).strip()

        for card in cards:
            # Match par Code Structure ou Ville
            match_code = code_club and code_club in card["text"]
            match_ville = (v_csv and v_csv in card["text"]) or (v_comp and v_comp in card["text"])
            
            if (match_code or match_ville) and d_csv in card["text"]:
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
        print(f"\n🎉 Terminé ! {updated} mandats ajoutés.")
    else:
        print("\nℹ️ Aucun nouveau mandat trouvé. Vérifie que le CSV n'est pas déjà à jour.")

if __name__ == "__main__":
    main()
