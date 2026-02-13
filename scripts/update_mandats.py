#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import time
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

import pandas as pd
import requests
from bs4 import BeautifulSoup

# --------------------
# CONFIG
# --------------------
# IMPORTANT: on passe par TON worker (évite le 403 depuis GitHub Actions)
FFTA_LIST_URL = os.getenv("FFTA_LIST_URL", "https://ffta-proxy.s-general.workers.dev")
CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")

MAX_PAGES = int(os.getenv("MAX_PAGES", "60"))
SLEEP_S = float(os.getenv("SLEEP_S", "0.4"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.60"))

UA = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)

# --------------------
# UTILS
# --------------------
def strip_accents(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def norm(s: str) -> str:
    s = strip_accents(s).upper()
    s = s.replace("’", "'")
    s = re.sub(r"[^A-Z0-9\s'-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def parse_fr_date(d: str):
    """CSV: 'Date debut' en format souvent dd/mm/yyyy."""
    if not d or not isinstance(d, str):
        return None
    d = d.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            pass
    return None


def parse_dates_from_text(txt: str):
    """
    Texte FFTA souvent:
      - "Le 14 février 2026"
      - "Du 14 au 15 février 2026"
    Renvoie (start_date, end_date) en date (ou (None, None)).
    """
    if not txt:
        return (None, None)

    t = strip_accents(txt).lower().strip()

    months = {
        "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12
    }

    # du 14 au 15 fevrier 2026
    m = re.search(r"du\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, d2, mn, y = m.groups()
        mo = months.get(mn)
        if mo:
            return (datetime(int(y), mo, int(d1)).date(),
                    datetime(int(y), mo, int(d2)).date())

    # le 14 fevrier 2026
    m = re.search(r"le\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, mn, y = m.groups()
        mo = months.get(mn)
        if mo:
            dd = datetime(int(y), mo, int(d1)).date()
            return (dd, dd)

    return (None, None)


# --------------------
# FETCH / PARSE FFTA (via worker)
# --------------------
def make_session() -> requests.Session:
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return sess


def build_page_url(page: int) -> str:
    # On construit explicitement l’URL de page côté worker
    # Exemple: https://...workers.dev/?page=3
    base = FFTA_LIST_URL.rstrip("/")
    return f"{base}/?page={page}"


def extract_competitions_from_html(html: str):
    soup = BeautifulSoup(html, "html.parser")

    # Essais de sélection "robustes"
    # Le site peut présenter des listes en "article" ou via des "views-row"
    blocks = soup.select("article, .views-row")
    if not blocks:
        # fallback: certains templates ont surtout des h2
        blocks = soup.find_all("h2")

    comps = []

    for block in blocks:
        a = block.find("a") if hasattr(block, "find") else None
        if not a:
            continue

        title = a.get_text(" ", strip=True)
        detail_url = a.get("href", "") or ""

        # (Pas obligatoire pour ton CSV, mais on le garde)
        text = block.get_text(" ", strip=True) if hasattr(block, "get_text") else title

        # Date dans le texte
        date_txt = ""
        m = re.search(r"(Le|Du)\s+.+?\d{4}", strip_accents(text), flags=re.IGNORECASE)
        if m:
            date_txt = m.group(0)

        start_d, end_d = parse_dates_from_text(date_txt)

        # Mandat : lien contenant le mot mandat
        mandat_url = ""
        if hasattr(block, "find_all"):
            for link in block.find_all("a"):
                if "mandat" in link.get_text(" ", strip=True).lower():
                    mandat_url = link.get("href", "") or ""
                    break

        # Ville (souvent dans le titre "... à VILLE")
        city = ""
        mcity = re.search(r"\s+à\s+(.+)$", title, flags=re.IGNORECASE)
        if mcity:
            city = mcity.group(1).strip()

        comps.append({
            "title": title,
            "city": city,
            "start_date": start_d,
            "end_date": end_d,
            "mandat_url": mandat_url,
            "detail_url": detail_url,
        })

    # Dé-doublonnage simple
    seen = set()
    out = []
    for c in comps:
        key = (norm(c["title"]), str(c["start_date"]), norm(c["city"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def fetch_competitions():
    sess = make_session()
    comps = []

    for page in range(MAX_PAGES):
        url = build_page_url(page)
        try:
            r = sess.get(url, timeout=30, allow_redirects=True)
        except Exception as e:
            print(f"WARN page={page} request_error={e}")
            time.sleep(SLEEP_S)
            continue

        # IMPORTANT: on ne crash pas si status != 200 (on continue)
        if r.status_code != 200:
            print(f"WARN page={page} status={r.status_code} url={url}")
            time.sleep(SLEEP_S)
            continue

        page_comps = extract_competitions_from_html(r.text)
        comps.extend(page_comps)

        time.sleep(SLEEP_S)

    return comps


# --------------------
# UPDATE CSV
# --------------------
def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV introuvable: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, sep=";", dtype=str, encoding="utf-8").fillna("")

    if "Mandat" not in df.columns:
        raise SystemExit("Colonne 'Mandat' absente du CSV (orthographe exacte requise).")

    if "Detail" not in df.columns:
        df["Detail"] = ""

    # Téléchargement compétitions via worker
    comps = fetch_competitions()

    # Index par date de début
    by_date = {}
    for c in comps:
        if c.get("start_date"):
            by_date.setdefault(str(c["start_date"]), []).append(c)

    updated = 0
    matched = 0

    for i, row in df.iterrows():
        start_dt = parse_fr_date(row.get("Date debut", ""))
        if not start_dt:
            continue

        candidates = by_date.get(str(start_dt.date()), [])
        if not candidates:
            continue

        title_csv = row.get("Titre compétition", "") or row.get("Titre competition", "") or ""

        best = None
        best_score = 0.0

        for c in candidates:
            score = sim(title_csv, c.get("title", ""))
            if score > best_score:
                best_score = score
                best = c

        if best and best_score >= MATCH_THRESHOLD:
            matched += 1

            # On remplit Detail (même si vide avant)
            if best.get("detail_url"):
                if df.at[i, "Detail"] != best["detail_url"]:
                    df.at[i, "Detail"] = best["detail_url"]

            # On remplit Mandat seulement si dispo
            if best.get("mandat_url"):
                if df.at[i, "Mandat"] != best["mandat_url"]:
                    df.at[i, "Mandat"] = best["mandat_url"]
                    updated += 1

    df.to_csv(CSV_PATH, sep=";", index=False, encoding="utf-8")
    print(f"OK - lignes matchées: {matched} | mandats ajoutés/modifiés: {updated}")


if __name__ == "__main__":
    main()
