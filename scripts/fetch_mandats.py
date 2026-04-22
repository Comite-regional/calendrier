#!/usr/bin/env python3
"""
fetch_mandats.py  —  CR12 Pays de la Loire
Scrape ffta.fr/competitions filtré sur les 5 départements PDL,
récupère les URLs de mandats PDF et met à jour concours26.csv.

Usage :
  python fetch_mandats.py              → mise à jour normale
  python fetch_mandats.py --dry-run    → affiche sans écrire
  python fetch_mandats.py --dump-html  → sauvegarde le HTML (debug)
  python fetch_mandats.py --pages 5    → limite à 5 pages
"""

import requests, csv, argparse, sys, time, re
from datetime import date, timedelta
from pathlib import Path
from bs4 import BeautifulSoup

# ═══════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════

BASE_URL  = "https://www.ffta.fr/competitions"
CSV_FILE  = "concours26.csv"
SEPARATOR = ";"
MAX_PAGES = 20
DELAY     = 1.5   # secondes entre pages

# IDs internes FFTA pour les 5 depts PDL
# (découverts dans l'URL de filtre, ≠ codes INSEE)
#   45 = Loire-Atlantique (44)
#   50 = Maine-et-Loire   (49)
#   54 = Mayenne          (53)
#   73 = Sarthe           (72)
#   86 = Vendée           (85)
CR12_DEPS = ["45", "50", "54", "73", "86"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "fr-FR,fr;q=0.9",
}

CSV_COLUMNS = [
    "Date debut", "Date fin", "Titre compétition", "Ville",
    "Code structure", "Club organisateur", "Code region", "Departement",
    "Discipline", "Type", "Saison",
    "Unnamed: 11", "Unnamed: 12", "Unnamed: 13", "Unnamed: 14",
    "Unnamed: 15", "Unnamed: 16", "Unnamed: 17", "Unnamed: 18",
    "Unnamed: 19", "Unnamed: 20",
    "Mail", "Unnamed: 22", "Unnamed: 23",
    "Site web", "Lieu", "Unnamed: 26", "Adresse", "Spécificité",
    "CP", "Ville compétition", "Long", "Lat",
    "Mandat", "",
]

# ═══════════════════════════════════════════
# URL
# ═══════════════════════════════════════════

def build_start_url() -> str:
    today    = date.today()
    end_date = today + timedelta(days=365)
    deps     = "".join(f"&dep%5B%5D={d}" for d in CR12_DEPS)
    return (
        f"{BASE_URL}?search=&start={today}&end={end_date}"
        f"{deps}"
        "&discipline=All&univers=All&inter=All"
        "&sort_by=start&sort_order=ASC"
    )

# ═══════════════════════════════════════════
# SCRAPING
# ═══════════════════════════════════════════

def fetch_page(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except requests.exceptions.RequestException as e:
        print(f"  ERR réseau : {e}")
        return None

def parse_competitions(soup):
    comps = []
    for article in soup.select("article.competition_item"):
        comp = {}
        mandat_tag = article.select_one("a.competition_item__mandat_btn")
        comp["mandat_url"] = mandat_tag["href"].strip() if mandat_tag else ""
        detail_tag = article.select_one("a.competition_item__infos_btn")
        if detail_tag:
            href = detail_tag.get("href", "")
            comp["detail_url"] = f"https://www.ffta.fr{href}" if href.startswith("/") else href
            m = re.search(r"/epreuve/(\d+)", href)
            comp["epreuve_id"] = m.group(1) if m else ""
        else:
            comp["detail_url"] = comp["epreuve_id"] = ""
        titre_tag = article.select_one(".competition_item__title, h2, h3")
        comp["titre"] = titre_tag.get_text(strip=True) if titre_tag else ""
        date_tag = article.select_one(".competition_item__date, .date-display-single, time")
        comp["date_raw"] = date_tag.get_text(strip=True) if date_tag else ""
        if comp["titre"] or comp["epreuve_id"]:
            comps.append(comp)
    return comps

def get_next_url(soup):
    tag = soup.select_one(
        "a[title='Aller à la page suivante'],"
        "a[rel='next'],"
        ".pager__item--next a,"
        "li.pager__item--next a"
    )
    if not tag:
        return None
    href = tag.get("href", "")
    return f"https://www.ffta.fr{href}" if href.startswith("/") else href or None

def scrape_all(start_url, max_pages, dump_html):
    all_comps, url = [], start_url
    for p in range(1, max_pages + 1):
        print(f"  Page {p} : {url[:80]}...")
        soup = fetch_page(url)
        if not soup:
            break
        if dump_html:
            Path(f"debug_page_{p}.html").write_text(soup.prettify(), encoding="utf-8")
        comps = parse_competitions(soup)
        print(f"         -> {len(comps)} épreuves, "
              f"{sum(1 for c in comps if c['mandat_url'])} avec mandat")
        if not comps:
            break
        all_comps.extend(comps)
        next_url = get_next_url(soup)
        if not next_url:
            print("         -> Dernière page.")
            break
        url = next_url
        time.sleep(DELAY)
    return all_comps

# ═══════════════════════════════════════════
# MATCHING
# ═══════════════════════════════════════════

def norm(s):
    s = s.lower().strip()
    for a, b in [("à","a"),("â","a"),("é","e"),("è","e"),("ê","e"),
                 ("î","i"),("ô","o"),("ù","u"),("û","u"),("ç","c"),
                 ("œ","oe"),("æ","ae")]:
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", s)

def find_match(row, scraped):
    titre = norm(row.get("Titre compétition", ""))
    d     = row.get("Date debut", "").strip()
    # Titre + date
    for c in scraped:
        if norm(c.get("titre","")) == titre and c.get("mandat_url"):
            if not d or d in c.get("date_raw",""):
                return c
    # Titre seul
    for c in scraped:
        if norm(c.get("titre","")) == titre and c.get("mandat_url"):
            return c
    return None

# ═══════════════════════════════════════════
# CSV
# ═══════════════════════════════════════════

def load_csv(path):
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=SEPARATOR))

def save_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS, delimiter=SEPARATOR,
                           extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        w.writerows(rows)

# ═══════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",       default=CSV_FILE)
    parser.add_argument("--dry-run",   action="store_true")
    parser.add_argument("--dump-html", action="store_true")
    parser.add_argument("--pages",     type=int, default=MAX_PAGES)
    args = parser.parse_args()

    url = build_start_url()
    print(f"FFTA CR12 — Scraping mandats")
    print(f"URL de départ : {url}\n")

    scraped = scrape_all(url, args.pages, args.dump_html)
    print(f"\nTotal scrapé : {len(scraped)} épreuves "
          f"({sum(1 for c in scraped if c['mandat_url'])} avec mandat)")

    rows = load_csv(Path(args.csv))
    avant = sum(1 for r in rows if r.get("Mandat","").strip())
    print(f"CSV actuel   : {len(rows)} lignes, {avant} mandats\n")

    updated = 0
    for row in rows:
        if row.get("Mandat","").strip():
            continue
        m = find_match(row, scraped)
        if m:
            row["Mandat"] = m["mandat_url"]
            updated += 1
            print(f"  + [{row['Date debut']}] {row['Titre compétition']}")
            print(f"    {m['mandat_url']}")

    titres = {norm(r.get("Titre compétition","")) for r in rows}
    new_rows = []
    for comp in scraped:
        if norm(comp.get("titre","")) not in titres and comp.get("epreuve_id"):
            r = {col: "" for col in CSV_COLUMNS}
            r["Titre compétition"] = comp["titre"]
            r["Mandat"]            = comp.get("mandat_url","")
            r["Site web"]          = comp.get("detail_url","")
            r["Code region"]       = "CR12"
            new_rows.append(r)
            titres.add(norm(comp["titre"]))
            print(f"  NEW {comp['titre']}")

    print(f"\n--- Résumé ---")
    print(f"Mandats remplis  : {updated} / {len(rows) - avant} manquants")
    print(f"Nouvelles lignes : {len(new_rows)}")
    print(f"Total final      : {len(rows) + len(new_rows)} lignes")

    if updated == 0 and not new_rows:
        print("Rien à modifier.")
        return
    if args.dry_run:
        print("Dry-run : CSV non modifié.")
        return

    save_csv(Path(args.csv), rows + new_rows)
    print(f"CSV sauvegarde : {args.csv}")

if __name__ == "__main__":
    main()
