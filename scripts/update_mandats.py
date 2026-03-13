import csv
import os
import re
import time
import unicodedata
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
BASE_PROXY_URL = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
MAX_PAGES = int(os.getenv("MAX_PAGES", "80"))
SLEEP_S = float(os.getenv("SLEEP_S", "0.5"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
STOP_AFTER_EMPTY_PAGES = int(os.getenv("STOP_AFTER_EMPTY_PAGES", "5"))
STOP_AFTER_ERROR_PAGES = int(os.getenv("STOP_AFTER_ERROR_PAGES", "5"))

LISTING_BASE = "https://www.ffta.fr"
DETAIL_BASE = "https://www.ffta.fr"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


@dataclass
class ListingItem:
    date_text: str
    title: str
    city: str
    detail_url: str
    mandat_url: str = ""


def log(msg: str) -> None:
    print(msg, flush=True)


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in text if not unicodedata.combining(c))


def norm(text: str) -> str:
    text = strip_accents(text or "").lower().strip()
    text = re.sub(r"\s+", " ", text)
    text = text.replace("’", "'").replace("`", "'")
    text = re.sub(r"[^a-z0-9\s'/\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def norm_city(text: str) -> str:
    text = norm(text)
    text = text.replace("saint ", "st ")
    return text


def csv_row_key(row: Dict[str, str]) -> Tuple[str, str, str]:
    date_value = (row.get("Date debut") or "").strip()
    title_value = norm(row.get("Titre compétition", ""))
    city_value = norm_city(row.get("Ville compétition") or row.get("Ville") or "")
    return (date_value, title_value, city_value)


def listing_key(item: ListingItem) -> Tuple[str, str, str]:
    return (
        item.date_text.strip(),
        norm(item.title),
        norm_city(item.city),
    )


def fetch_html(url: str) -> Tuple[Optional[int], Optional[str]]:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
        return resp.status_code, resp.text
    except requests.RequestException as exc:
        log(f"ERROR request_failed url={url} error={exc}")
        return None, None


def absolute_url(href: str, base: str) -> str:
    return urljoin(base, href)


def parse_listing_page(html: str) -> List[ListingItem]:
    soup = BeautifulSoup(html, "html.parser")
    items: List[ListingItem] = []

    cards = soup.select("article, .views-row, .node, .card")
    for card in cards:
        raw_text = card.get_text(" ", strip=True)
        if not raw_text:
            continue

        detail_url = ""
        mandat_url = ""
        title = ""
        city = ""
        date_text = ""

        links = card.find_all("a", href=True)
        if not links:
            continue

        for a in links:
            href = absolute_url(a["href"], LISTING_BASE)
            label = norm(a.get_text(" ", strip=True))

            if "/epreuve/" in href and not detail_url:
                detail_url = href

            if "detail" in label or "détail" in label:
                detail_url = href

            if "mandat" in label or href.lower().endswith(".pdf"):
                mandat_url = href

        text = raw_text

        date_match = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
        if date_match:
            date_text = date_match.group(0)

        lines = [x.strip() for x in card.stripped_strings if x.strip()]
        if lines:
            title = lines[0]

        # cherche une ville plausible
        possible_city = ""
        for token in lines[1:]:
            if len(token) > 2 and len(token) < 80:
                possible_city = token
                break
        city = possible_city

        if detail_url and title:
            items.append(
                ListingItem(
                    date_text=date_text,
                    title=title,
                    city=city,
                    detail_url=detail_url,
                    mandat_url=mandat_url,
                )
            )

    # dédoublonnage
    unique: Dict[Tuple[str, str, str, str], ListingItem] = {}
    for item in items:
        key = (item.date_text, norm(item.title), norm_city(item.city), item.detail_url)
        if key not in unique:
            unique[key] = item

    return list(unique.values())


def extract_title_from_detail(soup: BeautifulSoup) -> str:
    for sel in ["h1", "h2", ".page-title", ".node__title"]:
        tag = soup.select_one(sel)
        if tag:
            text = tag.get_text(" ", strip=True)
            if text:
                return text
    return ""


def extract_date_from_detail(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)
    m = re.search(r"\b\d{2}/\d{2}/\d{4}\b", text)
    return m.group(0) if m else ""


def extract_city_from_detail(soup: BeautifulSoup) -> str:
    text = soup.get_text(" ", strip=True)

    patterns = [
        r"\b(?:ville|commune)\s*[:\-]\s*([A-Za-zÀ-ÿ' \-]+)",
        r"\b([A-ZÀ-Ÿ][A-ZÀ-Ÿ' \-]{2,})\b",
    ]
    for pattern in patterns:
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return ""


def extract_mandat_from_detail(detail_url: str) -> str:
    status, html = fetch_html(detail_url)
    if status != 200 or not html:
        log(f"WARN detail status={status} url={detail_url}")
        return ""

    soup = BeautifulSoup(html, "html.parser")

    for a in soup.find_all("a", href=True):
        href = absolute_url(a["href"], DETAIL_BASE)
        label = norm(a.get_text(" ", strip=True))
        if "mandat" in label and href.lower().endswith(".pdf"):
            return href

    for a in soup.find_all("a", href=True):
        href = absolute_url(a["href"], DETAIL_BASE)
        if href.lower().endswith(".pdf"):
            return href

    return ""


def refine_listing_item_from_detail(item: ListingItem) -> ListingItem:
    status, html = fetch_html(item.detail_url)
    if status != 200 or not html:
        log(f"WARN detail_refine status={status} url={item.detail_url}")
        return item

    soup = BeautifulSoup(html, "html.parser")

    detail_title = extract_title_from_detail(soup)
    detail_date = extract_date_from_detail(soup)
    detail_city = extract_city_from_detail(soup)

    mandat_url = item.mandat_url or extract_mandat_from_detail(item.detail_url)

    return ListingItem(
        date_text=detail_date or item.date_text,
        title=detail_title or item.title,
        city=detail_city or item.city,
        detail_url=item.detail_url,
        mandat_url=mandat_url,
    )


def build_listing_map() -> Dict[Tuple[str, str, str], ListingItem]:
    listing_map: Dict[Tuple[str, str, str], ListingItem] = {}
    empty_pages = 0
    error_pages = 0

    for page in range(MAX_PAGES):
        url = f"{BASE_PROXY_URL}?page={page}"
        status, html = fetch_html(url)

        if status != 200 or not html:
            error_pages += 1
            log(f"WARN page={page} status={status} url={url}")
            if error_pages >= STOP_AFTER_ERROR_PAGES:
                log("STOP too_many_errors")
                break
            time.sleep(SLEEP_S)
            continue

        error_pages = 0
        items = parse_listing_page(html)
        log(f"INFO page={page} items={len(items)}")

        if not items:
            empty_pages += 1
            if empty_pages >= STOP_AFTER_EMPTY_PAGES:
                log("STOP too_many_empty_pages")
                break
            time.sleep(SLEEP_S)
            continue

        empty_pages = 0

        for item in items:
            refined = refine_listing_item_from_detail(item)
            key = listing_key(refined)

            if key not in listing_map:
                listing_map[key] = refined

            time.sleep(SLEEP_S)

        time.sleep(SLEEP_S)

    return listing_map


def load_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        rows = []
        for row in reader:
            cleaned = {k: (v or "").strip() for k, v in row.items()}
            rows.append(cleaned)
        return rows


def save_csv_rows(path: str, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=";", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = load_csv_rows(CSV_PATH)
    if not rows:
        log("ERROR csv_empty")
        return 1

    fieldnames = list(rows[0].keys())
    if "Mandat" not in fieldnames or "Detail" not in fieldnames:
        log("ERROR missing_columns Mandat/Detail")
        return 1

    listing_map = build_listing_map()
    log(f"INFO listing_map_size={len(listing_map)}")

    updated_detail = 0
    updated_mandat = 0
    matched_rows = 0

    for row in rows:
        key = csv_row_key(row)
        item = listing_map.get(key)

        if not item:
            continue

        matched_rows += 1

        if item.detail_url and not row.get("Detail", "").strip():
            row["Detail"] = item.detail_url
            updated_detail += 1

        if item.mandat_url and row.get("Mandat", "").strip() != item.mandat_url:
            row["Mandat"] = item.mandat_url
            updated_mandat += 1

    # 2e passe : si Detail existe mais Mandat vide, on tente directement la fiche
    filled_from_existing_detail = 0
    for row in rows:
        if row.get("Mandat", "").strip():
            continue
        detail_url = row.get("Detail", "").strip()
        if not detail_url:
            continue

        mandat = extract_mandat_from_detail(detail_url)
        if mandat:
            row["Mandat"] = mandat
            updated_mandat += 1
            filled_from_existing_detail += 1

        time.sleep(SLEEP_S)

    save_csv_rows(CSV_PATH, rows, fieldnames)

    log(f"INFO matched_rows={matched_rows}")
    log(f"INFO updated_detail={updated_detail}")
    log(f"INFO updated_mandat={updated_mandat}")
    log(f"INFO filled_from_existing_detail={filled_from_existing_detail}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
