import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ============================
# CONFIG
# ============================

CSV_PATH = "concours26.csv"
PROXY = "https://ffta-proxy.s-general.workers.dev/"
BASE = "https://www.ffta.fr"


# ============================
# CSV
# ============================

def load_csv():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader), reader.fieldnames


def save_csv(rows, fields):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


# ============================
# SCRAP FFTA
# ============================

def get_cards():
    cards = []

    for page in range(10):
        url = f"{PROXY}?target=/competitions&page={page}"
        print("PAGE", page)

        r = requests.get(url)
        if r.status_code != 200:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        for a in soup.find_all("a", href=True):
            if "/epreuve/" not in a["href"]:
                continue

            title = a.get_text(strip=True)

            block = a.parent
            text = block.get_text(" ", strip=True)

            mandat = ""
            for link in block.find_all("a", href=True):
                if "mandat" in link.get_text(strip=True).lower():
                    mandat = urljoin(BASE, link["href"])

            cards.append({
                "title": title.lower(),
                "text": text.lower(),
                "mandat": mandat
            })

    return cards


# ============================
# MATCH
# ============================

def match(row, card):
    titre = (row.get("Titre compétition") or "").lower()
    ville = (row.get("Ville compétition") or row.get("Ville") or "").lower()

    return titre in card["title"] and ville in card["text"]


# ============================
# UPDATE
# ============================

def update_mandats(rows, cards):
    added = []

    for row in rows:

        # uniquement lignes sans mandat
        if row.get("Mandat"):
            continue

        for card in cards:
            if match(row, card) and card["mandat"]:
                row["Mandat"] = card["mandat"]

                added.append(
                    f"{row.get('Titre compétition')} ({row.get('Ville compétition')})"
                )

                print("OK:", row.get("Titre compétition"))
                break

    return added


# ============================
# MAIN
# ============================

def main():
    rows, fields = load_csv()
    cards = get_cards()

    added = update_mandats(rows, cards)

    save_csv(rows, fields)

    print("\n=== RAPPORT ===")
    for a in added:
        print("-", a)

    print("\nTotal:", len(added))


if __name__ == "__main__":
    main()
