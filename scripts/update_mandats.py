import csv
import os
import re
import time
import unicodedata
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
PROXY = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "80"))
SLEEP = float(os.getenv("SLEEP_S", "0.4"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
STOP_AFTER_EMPTY_PAGES = int(os.getenv("STOP_AFTER_EMPTY_PAGES", "5"))
STOP_AFTER_ERROR_PAGES = int(os.getenv("STOP_AFTER_ERROR_PAGES", "5"))

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

BASE_SITE = "https://www.ffta.fr"


def normalize_text(value: str) -> str:
    value = value or ""
    value = value.strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(c for c in value if unicodedata.category(c) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_date(value: str) -> str:
    """
    CSV format attendu: dd/mm/YYYY
    Retourne yyyy-mm-dd pour matcher plus facilement.
    """
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        return r.status_code, r.text
    except Exception as e:
        print(f"ERROR fetch {url}: {e}")
        return None, None


def get_listing_url(page: int) -> str:
    # On garde le proxy, mais on cible explicitement /competitions?page=N
    return f"{PROXY}?target=/competitions&page={page}"


def parse_cards(html: str):
    soup = BeautifulSoup(html, "html.parser")
    cards = []

    # Chaque compétition est structurée autour d'un lien /epreuve/xxxxx
    for title_link in soup.find_all("a", href=True):
        href = title_link["href"]
        if not href.startswith("/epreuve/"):
            continue

        title = title_link.get_text(" ", strip=True)
        if not title:
            continue

        block = title_link.find_parent()
        # On remonte un peu pour inspecter le voisinage HTML
        container = block
        for _ in range(6):
            if container is None:
                break
            # chercher dans cette zone un lien "Mandat"
            mandat_link = None
            for a in container.find_all("a", href=True):
                txt = a.get_text(" ", strip=True).lower()
                if "mandat" in txt:
                    mandat_link = a["href"]
                    break
            if mandat_link:
                text_blob = container.get_text("\n", strip=True)
                cards.append({
                    "title": title,
                    "detail": urljoin(BASE_SITE, href),
                    "mandat": urljoin(BASE_SITE, mandat_link),
                    "text": text_blob,
                })
                break
            container = container.parent

    # dédoublonnage
    uniq = {}
    for c in cards:
        uniq[(c["title"], c["detail"], c["mandat"])] = c
    return list(uniq.values())


def load_csv():
    with open(CSV_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = list(reader)
        return rows, reader.fieldnames


def save_csv(rows, fieldnames):
    with open(CSV_PATH, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def build_index(rows):
    index = {}
    for i, row in enumerate(rows):
        key = (
            normalize_date(row.get("Date debut", "")),
            normalize_text(row.get("Titre compétition", "")),
            normalize_text(row.get("Ville compétition", "") or row.get("Ville", "")),
        )
        index[key] = i
    return index


def match_row(cards, index, rows):
    updated = 0
    for card in cards:
        title_norm = normalize_text(card["title"])
        text_norm = normalize_text(card["text"])

        found_idx = None

        # match souple sur le titre contenu dans le CSV
        for idx, row in enumerate(rows):
            row_title = normalize_text(row.get("Titre compétition", ""))
            row_city = normalize_text(row.get("Ville compétition", "") or row.get("Ville", ""))

            if not row_title:
                continue

            title_ok = (row_title in title_norm) or (title_norm in row_title)
            city_ok = (not row_city) or (row_city in text_norm)

            if title_ok and city_ok:
                found_idx = idx
                break

        if found_idx is not None:
            if not rows[found_idx].get("Mandat"):
                rows[found_idx]["Mandat"] = card["mandat"]
                updated += 1
                print(f"UPDATE mandat: {rows[found_idx].get('Titre compétition')} -> {card['mandat']}")

    return updated


def main():
    rows, fieldnames = load_csv()

    if "Mandat" not in fieldnames:
        raise RuntimeError("La colonne 'Mandat' est absente du CSV.")

    total_updated = 0
    empty_pages = 0
    error_pages = 0

    for page in range(0, MAX_PAGES):
        url = get_listing_url(page)
        print(f"PAGE {page} -> {url}")

        status, html = fetch(url)

        if status != 200 or not html:
            error_pages += 1
            print(f"WARN listing page={page} status={status}")
            if error_pages >= STOP_AFTER_ERROR_PAGES:
                print("STOP: trop de pages en erreur.")
                break
            continue

        cards = parse_cards(html)

        if not cards:
            empty_pages += 1
            print(f"INFO page vide ou sans mandat exploitable: {page}")
            if empty_pages >= STOP_AFTER_EMPTY_PAGES:
                print("STOP: trop de pages vides.")
                break
        else:
            empty_pages = 0

        total_updated += match_row(cards, None, rows)
        time.sleep(SLEEP)

    save_csv(rows, fieldnames)
    print("Mandats ajoutés :", total_updated)


if __name__ == "__main__":
    main()
