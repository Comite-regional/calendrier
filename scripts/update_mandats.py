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


FFTA_BASE = "https://www.ffta.fr"
FFTA_LIST_URL = "https://www.ffta.fr/competitions"
CSV_PATH = os.getenv("CSV_PATH", "concours26.csv")

MAX_PAGES = int(os.getenv("MAX_PAGES", "60"))
SLEEP_S = float(os.getenv("SLEEP_S", "0.4"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.60"))

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"


# ---------- utils texte ----------

def strip_accents(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    s = strip_accents(s).upper()
    s = re.sub(r"[^A-Z0-9\s'-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, norm(a), norm(b)).ratio()


def parse_fr_date(d: str):
    if not d:
        return None
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            pass
    return None


# ---------- parsing dates FFTA ----------

def parse_dates_from_text(txt: str):
    if not txt:
        return (None, None)

    t = strip_accents(txt).lower()

    months = {
        "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5,
        "juin": 6, "juillet": 7, "aout": 8, "septembre": 9,
        "octobre": 10, "novembre": 11, "decembre": 12
    }

    m = re.search(r"du\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, d2, mn, y = m.groups()
        mo = months.get(mn)
        if mo:
            return (datetime(int(y), mo, int(d1)).date(),
                    datetime(int(y), mo, int(d2)).date())

    m = re.search(r"le\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, mn, y = m.groups()
        mo = months.get(mn)
        if mo:
            d = datetime(int(y), mo, int(d1)).date()
            return (d, d)

    return (None, None)


# ---------- scraping FFTA ----------

def make_session():
    sess = requests.Session()
    sess.headers.update({
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })
    return sess


def fetch_competitions():
    sess = make_session()
    comps = []

    for page in range(MAX_PAGES):
        params = {"page": page} if page > 0 else {}

        r = sess.get(
            FFTA_LIST_URL,
            params=params,
            timeout=30,
            allow_redirects=True
        )

        if r.status_code == 403:
            raise RuntimeError("FFTA bloque l'accès (403)")

        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        blocks = soup.select("article, .views-row")
        if not blocks:
            blocks = soup.find_all("h2")

        for block in blocks:
            a = block.find("a")
            if not a:
                continue

            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href.startswith("/"):
                detail_url = FFTA_BASE + href
            else:
                detail_url = href

            text = block.get_text(" ", strip=True)

            date_txt = ""
            m = re.search(r"(Le|Du).+?\d{4}", text)
            if m:
                date_txt = m.group(0)

            start_d, end_d = parse_dates_from_text(date_txt)

            mandat_url = ""
            for link in block.find_all("a"):
                if "mandat" in link.get_text(strip=True).lower():
                    mandat_url = link.get("href", "")
                    if mandat_url.startswith("/"):
                        mandat_url = FFTA_BASE + mandat_url

            city = ""
            m = re.search(r"\s+à\s+(.+)$", title, re.I)
            if m:
                city = m.group(1).strip()

            comps.append({
                "title": title,
                "city": city,
                "start_date": start_d,
                "mandat_url": mandat_url,
                "detail_url": detail_url,
            })

        time.sleep(SLEEP_S)

    return comps


# ---------- matching + update ----------

def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV introuvable: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, sep=";", dtype=str).fillna("")

    if "Mandat" not in df.columns:
        raise SystemExit("Colonne Mandat absente")

    if "Detail" not in df.columns:
        df["Detail"] = ""

    comps = fetch_competitions()

    by_date = {}
    for c in comps:
        if c["start_date"]:
            by_date.setdefault(str(c["start_date"]), []).append(c)

    updated = 0

    for i, row in df.iterrows():
        d = parse_fr_date(row.get("Date debut", ""))
        if not d:
            continue

        candidates = by_date.get(str(d.date()), [])
        if not candidates:
            continue

        title_csv = row.get("Titre compétition", "")

        best = None
        best_score = 0

        for c in candidates:
            score = sim(title_csv, c["title"])
            if score > best_score:
                best_score = score
                best = c

        if best and best_score >= MATCH_THRESHOLD:
            if best["detail_url"]:
                df.at[i, "Detail"] = best["detail_url"]

            if best["mandat_url"]:
                if df.at[i, "Mandat"] != best["mandat_url"]:
                    df.at[i, "Mandat"] = best["mandat_url"]
                    updated += 1

    df.to_csv(CSV_PATH, sep=";", index=False)
    print(f"OK - mandats ajoutés/modifiés: {updated}")


if __name__ == "__main__":
    main()
