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

# Limites / réglages
MAX_PAGES = int(os.getenv("MAX_PAGES", "30"))   # augmente si besoin
SLEEP_S = float(os.getenv("SLEEP_S", "0.4"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.60"))

UA = os.getenv(
    "USER_AGENT",
    "Mozilla/5.0 (compatible; MandatBot/1.0; +https://github.com/)"
)

def strip_accents(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return s

def norm(s: str) -> str:
    s = strip_accents(s).upper()
    s = re.sub(r"[^A-Z0-9\s'-]", " ", s)
    s = s.replace("’", "'")
    s = re.sub(r"\s+", " ", s).strip()
    return s

def norm_city(s: str) -> str:
    s = norm(s)
    # retire les trucs types "ST", "STE" etc si tu veux (optionnel)
    return s

def parse_fr_date(d: str) -> datetime | None:
    if not d or not isinstance(d, str):
        return None
    d = d.strip()
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(d, fmt)
        except ValueError:
            pass
    return None

def sim(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, norm(a), norm(b)).ratio()

def parse_dates_from_text(txt: str):
    """
    txt ressemble à:
      - "Le 14 février 2026"
      - "Du 14 au 15 février 2026"
    On renvoie (start_date, end_date) en datetime.date (end_date peut = start_date).
    """
    if not txt:
        return (None, None)

    t = strip_accents(txt).lower().strip()
    # extraction rudimentaire (jours + mois + annee)
    months = {
        "janvier": 1, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12
    }

    def make_date(day, month_name, year):
        m = months.get(month_name)
        if not m:
            return None
        return datetime(int(year), int(m), int(day)).date()

    # "du 14 au 15 fevrier 2026"
    m = re.search(r"du\s+(\d{1,2})\s+au\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, d2, mn, y = m.groups()
        return (make_date(d1, mn, y), make_date(d2, mn, y))

    # "le 14 fevrier 2026"
    m = re.search(r"le\s+(\d{1,2})\s+([a-z]+)\s+(\d{4})", t)
    if m:
        d1, mn, y = m.groups()
        dd = make_date(d1, mn, y)
        return (dd, dd)

    return (None, None)

def fetch_competitions():
    sess = requests.Session()
sess.headers.update({
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
})


    comps = []
    for page in range(0, MAX_PAGES):
        params = {"page": page} if page > 0 else {}
        r = sess.get(FFTA_LIST_URL, params=params, timeout=30)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        # Sur la page, chaque entrée est structurée en blocs, on s'appuie sur:
        # - titres en h2 (ou h2 a)
        # - liens "Mandat" (extranet) et "Détail" (ffta)
        # La structure HTML peut varier, on fait robuste:
        for h2 in soup.select("h2"):
            a_title = h2.find("a")
            if not a_title:
                continue

            title = a_title.get_text(" ", strip=True)
            detail_url = a_title.get("href") or ""
            if detail_url.startswith("/"):
                detail_url = FFTA_BASE + detail_url
            elif detail_url and not detail_url.startswith("http"):
                detail_url = FFTA_BASE + "/" + detail_url.lstrip("/")

            # On remonte au conteneur (section/article/div)
            container = h2
            for _ in range(6):
                if container and container.name in ("article", "section", "div"):
                    break
                container = container.parent

            block_text = container.get_text("\n", strip=True) if container else ""
            lines = [l.strip() for l in block_text.split("\n") if l.strip()]

            discipline = ""
            city = ""
            date_txt = ""

            # Heuristique: discipline apparaît souvent juste après le titre
            # Ville est dans "à VILLE" dans le titre, ou via un autre champ
            mcity = re.search(r"\s+à\s+(.+)$", title, flags=re.IGNORECASE)
            if mcity:
                city = mcity.group(1).strip()

            # discipline: cherche une ligne qui ressemble à "Tir à 18m", "Tir 3d", etc.
            for l in lines:
                if any(k in l.lower() for k in ["tir", "para", "loisirs", "jeunes", "rencontres"]):
                    discipline = l.strip()
                    break

            # date: cherche une ligne qui commence par "Le" ou "Du"
            for l in lines:
                if l.lower().startswith("le ") or l.lower().startswith("du "):
                    date_txt = l.strip()
                    break

            start_d, end_d = parse_dates_from_text(date_txt)

            mandat_url = ""
            # lien "Mandat" => ancre contenant le texte Mandat
            if container:
                for a in container.select("a"):
                    txt = a.get_text(" ", strip=True).lower()
                    href = a.get("href") or ""
                    if "mandat" in txt and href:
                        mandat_url = href
                        if mandat_url.startswith("/"):
                            mandat_url = FFTA_BASE + mandat_url
                        break

            comps.append({
                "title": title,
                "discipline": discipline,
                "city": city,
                "start_date": start_d,
                "end_date": end_d,
                "mandat_url": mandat_url,
                "detail_url": detail_url,
            })

        time.sleep(SLEEP_S)

        # Stop si plus de pagination trouvée (optionnel).
        # Ici on ne stoppe pas automatiquement car parfois pagination cachée.
        # Tu peux optimiser plus tard.

    # dédoublonnage basique (titre+date+ville)
    seen = set()
    out = []
    for c in comps:
        key = (norm(c["title"]), str(c["start_date"]), norm_city(c["city"]))
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out

def main():
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV introuvable: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH, sep=";", dtype=str, encoding="utf-8")
    # Nettoyage NaN -> ""
    df = df.fillna("")

    # Colonne Mandat doit exister
    if "Mandat" not in df.columns:
        raise SystemExit("Colonne 'Mandat' absente du CSV")

    # (Optionnel) ajoute une colonne Detail si tu veux l'avoir aussi
    if "Detail" not in df.columns:
        df["Detail"] = ""

    comps = fetch_competitions()

    # Index simple: par date de début (YYYY-MM-DD) pour réduire la recherche
    by_date = {}
    for c in comps:
        if not c["start_date"]:
            continue
        k = str(c["start_date"])
        by_date.setdefault(k, []).append(c)

    updated = 0
    for i, row in df.iterrows():
        start_dt = parse_fr_date(row.get("Date debut", ""))
        if not start_dt:
            continue
        k = str(start_dt.date())
        candidates = by_date.get(k, [])

        if not candidates:
            continue

        city_csv = norm_city(row.get("Ville compétition", row.get("Ville", "")))
        disc_csv = norm(row.get("Discipline", ""))
        title_csv = row.get("Titre compétition", "")

        # filtre ville/disc léger + score titre
        best = None
        best_score = 0.0

        for c in candidates:
            # ville: si on a ville des deux côtés, on exige au moins 1 token commun
            city_ffta = norm_city(c.get("city", ""))
            if city_csv and city_ffta:
                if not (set(city_csv.split()) & set(city_ffta.split())):
                    continue

            # discipline: tolérant, juste un overlap
            disc_ffta = norm(c.get("discipline", ""))
            if disc_csv and disc_ffta:
                if not (set(disc_csv.split()) & set(disc_ffta.split())):
                    # ex: "Tir 3D" vs "Tir 3d" passe; mais si rien en commun, on skip
                    continue

            score = sim(title_csv, c.get("title", ""))
            if score > best_score:
                best_score = score
                best = c

        if best and best_score >= MATCH_THRESHOLD:
            # Remplit mandat si dispo
            mandat_url = best.get("mandat_url", "") or ""
            detail_url = best.get("detail_url", "") or ""

            # On écrit Detail quoi qu'il arrive (pratique)
            if detail_url and (row.get("Detail", "") != detail_url):
                df.at[i, "Detail"] = detail_url

            # On met à jour Mandat seulement si on a un vrai mandat
            if mandat_url and (row.get("Mandat", "") != mandat_url):
                df.at[i, "Mandat"] = mandat_url
                updated += 1

    df.to_csv(CSV_PATH, sep=";", index=False, encoding="utf-8")
    print(f"OK - mandats ajoutés/modifiés: {updated}")

if __name__ == "__main__":
    main()
