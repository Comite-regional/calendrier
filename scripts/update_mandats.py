import csv
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIGURATION
# ============================================================

CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")
BASE_PROXY_URL = os.getenv("BASE_PROXY_URL", "https://ffta-proxy.s-general.workers.dev/")
BASE_SITE_URL = "https://www.ffta.fr"

MAX_PAGES = int(os.getenv("MAX_PAGES", "80"))
SLEEP_SECONDS = float(os.getenv("SLEEP_S", "0.4"))
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
STOP_AFTER_EMPTY_PAGES = int(os.getenv("STOP_AFTER_EMPTY_PAGES", "5"))
STOP_AFTER_ERROR_PAGES = int(os.getenv("STOP_AFTER_ERROR_PAGES", "5"))

REPORT_DIR = os.getenv("REPORT_DIR", "reports")
REPORT_PATH = os.path.join(REPORT_DIR, "last_report.md")

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "fr-FR,fr;q=0.9",
}


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class CompetitionCard:
    title: str
    detail_url: str = ""
    mandat_url: str = ""
    date_start: str = ""
    date_end: str = ""
    city: str = ""
    raw_text: str = ""


@dataclass
class ReportItem:
    date: str
    title: str
    city: str
    mandat: str = ""
    old_mandat: str = ""
    new_mandat: str = ""


@dataclass
class SyncReport:
    cards_found: int = 0
    new_events: list[ReportItem] = field(default_factory=list)
    mandats_added: list[ReportItem] = field(default_factory=list)
    mandats_updated: list[ReportItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ============================================================
# TEXT / DATE HELPERS
# ============================================================

def normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = unicodedata.normalize("NFD", value)
    value = "".join(char for char in value if unicodedata.category(char) != "Mn")
    value = re.sub(r"\s+", " ", value)
    return value


def normalize_date(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""

    try:
        return datetime.strptime(value, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return value


def french_month_to_number(month_name: str) -> str:
    month_name = normalize_text(month_name)

    months = {
        "janvier": "01",
        "fevrier": "02",
        "mars": "03",
        "avril": "04",
        "mai": "05",
        "juin": "06",
        "juillet": "07",
        "aout": "08",
        "septembre": "09",
        "octobre": "10",
        "novembre": "11",
        "decembre": "12",
    }
    return months.get(month_name, "")


def extract_dates_from_text(text: str) -> tuple[str, str]:
    text = text or ""

    # Exemple : "Du 21 au 22 mars 2026"
    multi_day_match = re.search(
        r"Du\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([A-Za-zéèêëàâäîïôöùûüç]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if multi_day_match:
        start_day, end_day, month_name, year = multi_day_match.groups()
        month = french_month_to_number(month_name)
        if month:
            return (
                f"{int(start_day):02d}/{month}/{year}",
                f"{int(end_day):02d}/{month}/{year}",
            )

    # Exemple : "Le 21 mars 2026"
    one_day_match = re.search(
        r"Le\s+(\d{1,2})\s+([A-Za-zéèêëàâäîïôöùûüç]+)\s+(\d{4})",
        text,
        flags=re.IGNORECASE,
    )
    if one_day_match:
        day, month_name, year = one_day_match.groups()
        month = french_month_to_number(month_name)
        if month:
            date_value = f"{int(day):02d}/{month}/{year}"
            return date_value, date_value

    return "", ""


def extract_city_from_text(text: str) -> str:
    text = text or ""

    city_match = re.search(r"\(([A-ZÀ-ÿ' \-]+)\)", text)
    if city_match:
        return city_match.group(1).strip()

    return ""


# ============================================================
# HTTP / SCRAPING
# ============================================================

def build_listing_url(page: int) -> str:
    return f"{BASE_PROXY_URL}?target=/competitions&page={page}"


def fetch_html(url: str) -> tuple[Optional[int], Optional[str]]:
    try:
        response = requests.get(url, headers=HTTP_HEADERS, timeout=REQUEST_TIMEOUT)
        return response.status_code, response.text
    except Exception as exc:
        print(f"ERROR fetch {url}: {exc}")
        return None, None


def parse_competition_cards(html: str) -> list[CompetitionCard]:
    soup = BeautifulSoup(html, "html.parser")
    cards: list[CompetitionCard] = []

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if not href.startswith("/epreuve/"):
            continue

        title = link.get_text(" ", strip=True)
        if not title:
            continue

        current_node = link
        mandat_href = ""
        surrounding_text = ""

        for _ in range(8):
            current_node = current_node.parent
            if current_node is None:
                break

            surrounding_text = current_node.get_text("\n", strip=True)

            mandat_link = current_node.find(
                "a",
                href=True,
                string=lambda s: s and "mandat" in s.lower()
            )
            if mandat_link:
                mandat_href = mandat_link.get("href", "")
                break

            # sécurité supplémentaire si le texte du lien est encapsulé
            for candidate in current_node.find_all("a", href=True):
                candidate_text = candidate.get_text(" ", strip=True).lower()
                if "mandat" in candidate_text:
                    mandat_href = candidate.get("href", "")
                    break

            if mandat_href:
                break

        date_start, date_end = extract_dates_from_text(surrounding_text)
        city = extract_city_from_text(surrounding_text)

        cards.append(
            CompetitionCard(
                title=title.strip(),
                detail_url=urljoin(BASE_SITE_URL, href),
                mandat_url=urljoin(BASE_SITE_URL, mandat_href) if mandat_href else "",
                date_start=date_start,
                date_end=date_end,
                city=city,
                raw_text=surrounding_text,
            )
        )

    return deduplicate_cards(cards)


def deduplicate_cards(cards: list[CompetitionCard]) -> list[CompetitionCard]:
    unique_cards: dict[tuple[str, str, str, str], CompetitionCard] = {}

    for card in cards:
        key = (
            normalize_text(card.title),
            card.date_start,
            card.date_end,
            normalize_text(card.city),
        )
        if key not in unique_cards:
            unique_cards[key] = card

    return list(unique_cards.values())


# ============================================================
# CSV HELPERS
# ============================================================

def load_csv_rows(csv_path: str) -> tuple[list[dict], list[str]]:
    with open(csv_path, encoding="utf-8-sig") as file:
        reader = csv.DictReader(file, delimiter=";")
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    return rows, fieldnames


def save_csv_rows(csv_path: str, rows: list[dict], fieldnames: list[str]) -> None:
    with open(csv_path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def create_empty_row(fieldnames: list[str]) -> dict:
    return {field: "" for field in fieldnames}


def build_row_from_card(card: CompetitionCard, fieldnames: list[str]) -> dict:
    row = create_empty_row(fieldnames)

    if "Date debut" in row:
        row["Date debut"] = card.date_start

    if "Date fin" in row:
        row["Date fin"] = card.date_end

    if "Titre compétition" in row:
        row["Titre compétition"] = card.title

    if "Ville compétition" in row:
        row["Ville compétition"] = card.city

    if "Ville" in row and not row["Ville"]:
        row["Ville"] = card.city

    if "Mandat" in row:
        row["Mandat"] = card.mandat_url

    return row


# ============================================================
# MATCHING LOGIC
# ============================================================

def compute_match_score(card: CompetitionCard, row: dict) -> int:
    score = 0

    card_title = normalize_text(card.title)
    row_title = normalize_text(row.get("Titre compétition", ""))

    card_city = normalize_text(card.city)
    row_city = normalize_text(row.get("Ville compétition", "") or row.get("Ville", ""))

    card_start = normalize_date(card.date_start)
    row_start = normalize_date(row.get("Date debut", ""))

    if card_title and row_title:
        if card_title == row_title:
            score += 60
        elif card_title in row_title or row_title in card_title:
            score += 40

    if card_city and row_city:
        if card_city == row_city:
            score += 30
        elif card_city in row_city or row_city in card_city:
            score += 15

    if card_start and row_start and card_start == row_start:
        score += 40

    return score


def find_best_matching_row(card: CompetitionCard, rows: list[dict]) -> tuple[Optional[int], int]:
    best_index = None
    best_score = -1

    for index, row in enumerate(rows):
        score = compute_match_score(card, row)
        if score > best_score:
            best_score = score
            best_index = index

    if best_score >= 70:
        return best_index, best_score

    return None, best_score


# ============================================================
# REPORTING
# ============================================================

def ensure_report_directory() -> None:
    os.makedirs(REPORT_DIR, exist_ok=True)


def build_report_markdown(report: SyncReport) -> str:
    now_string = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines: list[str] = []

    lines.append("# Rapport de synchronisation FFTA")
    lines.append("")
    lines.append(f"Date du scan : {now_string}")
    lines.append("")
    lines.append("## Résumé")
    lines.append(f"- Épreuves détectées : {report.cards_found}")
    lines.append(f"- Nouvelles épreuves ajoutées : {len(report.new_events)}")
    lines.append(f"- Mandats ajoutés : {len(report.mandats_added)}")
    lines.append(f"- Mandats mis à jour : {len(report.mandats_updated)}")
    lines.append(f"- Erreurs : {len(report.errors)}")
    lines.append("")

    lines.extend(render_report_section("Nouvelles épreuves ajoutées", report.new_events))
    lines.extend(render_report_section("Mandats ajoutés", report.mandats_added))
    lines.extend(render_report_section("Mandats mis à jour", report.mandats_updated, updated=True))

    lines.append("## Erreurs")
    if not report.errors:
        lines.append("- Aucune")
    else:
        for error in report.errors:
            lines.append(f"- {error}")
    lines.append("")

    return "\n".join(lines)


def render_report_section(title: str, items: list[ReportItem], updated: bool = False) -> list[str]:
    lines: list[str] = []
    lines.append(f"## {title}")

    if not items:
        lines.append("- Aucune")
        lines.append("")
        return lines

    for item in items:
        lines.append(f"- {item.date} — {item.title} — {item.city}")
        if updated:
            lines.append(f"  - Ancien : {item.old_mandat}")
            lines.append(f"  - Nouveau : {item.new_mandat}")
        else:
            lines.append(f"  - Mandat : {item.mandat}")

    lines.append("")
    return lines


def write_report(report: SyncReport) -> None:
    ensure_report_directory()
    markdown = build_report_markdown(report)

    with open(REPORT_PATH, "w", encoding="utf-8") as file:
        file.write(markdown)

    github_summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if github_summary_path:
        with open(github_summary_path, "a", encoding="utf-8") as file:
            file.write(markdown + "\n")


# ============================================================
# CORE SYNC LOGIC
# ============================================================

def process_card(card: CompetitionCard, rows: list[dict], fieldnames: list[str], report: SyncReport) -> None:
    row_index, score = find_best_matching_row(card, rows)

    if row_index is None:
        new_row = build_row_from_card(card, fieldnames)
        rows.append(new_row)

        report.new_events.append(
            ReportItem(
                date=new_row.get("Date debut", ""),
                title=new_row.get("Titre compétition", ""),
                city=new_row.get("Ville compétition", "") or new_row.get("Ville", ""),
                mandat=new_row.get("Mandat", ""),
            )
        )

        print(f"NEW EVENT: {card.title} | ville={card.city} | score={score}")
        return

    row = rows[row_index]
    current_mandat = (row.get("Mandat") or "").strip()
    scraped_mandat = (card.mandat_url or "").strip()

    if scraped_mandat and not current_mandat:
        row["Mandat"] = scraped_mandat

        report.mandats_added.append(
            ReportItem(
                date=row.get("Date debut", ""),
                title=row.get("Titre compétition", ""),
                city=row.get("Ville compétition", "") or row.get("Ville", ""),
                mandat=scraped_mandat,
            )
        )

        print(f"MANDAT ADDED: {row.get('Titre compétition', '')}")

    elif scraped_mandat and current_mandat and current_mandat != scraped_mandat:
        row["Mandat"] = scraped_mandat

        report.mandats_updated.append(
            ReportItem(
                date=row.get("Date debut", ""),
                title=row.get("Titre compétition", ""),
                city=row.get("Ville compétition", "") or row.get("Ville", ""),
                old_mandat=current_mandat,
                new_mandat=scraped_mandat,
            )
        )

        print(f"MANDAT UPDATED: {row.get('Titre compétition', '')}")


def sync_competitions(rows: list[dict], fieldnames: list[str]) -> SyncReport:
    report = SyncReport()

    empty_pages_count = 0
    error_pages_count = 0

    for page in range(MAX_PAGES):
        url = build_listing_url(page)
        print(f"PAGE {page} -> {url}")

        status_code, html = fetch_html(url)

        if status_code != 200 or not html:
            error_pages_count += 1
            error_message = f"Page {page} en erreur, status={status_code}"
            report.errors.append(error_message)
            print(error_message)

            if error_pages_count >= STOP_AFTER_ERROR_PAGES:
                print("STOP: trop de pages en erreur.")
                break

            continue

        cards = parse_competition_cards(html)
        report.cards_found += len(cards)

        if not cards:
            empty_pages_count += 1
            print(f"INFO: page {page} vide ou non exploitable")

            if empty_pages_count >= STOP_AFTER_EMPTY_PAGES:
                print("STOP: trop de pages vides.")
                break
        else:
            empty_pages_count = 0

        for card in cards:
            process_card(card, rows, fieldnames, report)

        time.sleep(SLEEP_SECONDS)

    return report


# ============================================================
# MAIN
# ============================================================

def validate_csv_structure(fieldnames: list[str]) -> None:
    if "Mandat" not in fieldnames:
        raise RuntimeError("La colonne 'Mandat' est absente du CSV.")


def main() -> None:
    rows, fieldnames = load_csv_rows(CSV_PATH)
    validate_csv_structure(fieldnames)

    report = sync_competitions(rows, fieldnames)

    save_csv_rows(CSV_PATH, rows, fieldnames)
    write_report(report)

    print("")
    print("=== SYNCHRONISATION TERMINÉE ===")
    print(f"Épreuves détectées : {report.cards_found}")
    print(f"Nouvelles épreuves : {len(report.new_events)}")
    print(f"Mandats ajoutés : {len(report.mandats_added)}")
    print(f"Mandats mis à jour : {len(report.mandats_updated)}")
    print(f"Erreurs : {len(report.errors)}")
    print(f"Rapport généré : {REPORT_PATH}")


if __name__ == "__main__":
    main()
