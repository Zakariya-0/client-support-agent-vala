#!/usr/bin/env python
"""
Scrape la page des plans d'hébergement mutualisé de vala.ma et stocke
le résultat dans la table website_content (un enregistrement par plan).
"""

import logging
import sqlite3
import json
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from database import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

URL = "https://www.vala.ma/hebergement-web/premium"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ValaSupportAgentBot/1.0"}


def _text(el):
    return el.get_text(separator=" ", strip=True) if el else None


def _parse_price(price_div):
    """Le prix barré (span.prix-original) est mélangé au prix actuel dans le même bloc :
    on l'isole d'abord, puis ce qui reste est le prix actuel."""
    original_span = price_div.find("span", class_="prix-original")
    original_price = _text(original_span)
    if original_span:
        original_span.extract()
    current_price = price_div.get_text(strip=True)
    return current_price, original_price


def _feature_value(feature_ul, keyword):
    """Cherche une ligne de feature contenant `keyword` et retourne sa valeur (le <strong>)."""
    for li in feature_ul.find_all("li", recursive=False):
        p = li.find("p")
        if p and keyword.lower() in p.get_text(strip=True).lower():
            strong = li.find("strong")
            return strong.get_text(strip=True) if strong else _text(p)
    return None


def _parse_card(card):
    name_el = card.select_one(".pricing-info h5")
    desc_el = card.select_one(".pricing-info p.text-muted")
    promo_el = card.select_one(".promo-label span")
    price_div = card.select_one(".pricing-price .h2")
    feature_ul = card.select_one(".pricing-feature-list-2")

    if not name_el or not price_div or not feature_ul:
        raise ValueError("sélecteur attendu introuvable dans cette carte")

    current_price, original_price = _parse_price(price_div)

    promo_code = None
    codepromo_li = feature_ul.find("li", class_="codepromo-li")
    if codepromo_li:
        promo_code = _text(codepromo_li.find("span", class_="codeP"))

    features = []
    for li in feature_ul.find_all("li", recursive=False):
        if "codepromo-li" in (li.get("class") or []):
            continue
        text = _text(li.find("p"))
        if text:
            features.append(text)

    return {
        "name": _text(name_el),
        "content": {
            "prix_actuel": current_price,
            "prix_original": original_price,
            "promo_pourcentage": _text(promo_el),
            "code_promo": promo_code,
            "description": _text(desc_el),
            "espace_disque": _feature_value(feature_ul, "Espace disque"),
            "domaine_inclus": _feature_value(feature_ul, "Nom de domaine inclus"),
            "boite_mail": _feature_value(feature_ul, "Boite Mail"),
            "nombre_sites": _feature_value(feature_ul, "Nombre de sites"),
            "features": features,
        },
    }


def scrape_hosting_plans() -> bool:
    """Télécharge la page des plans, parse chaque carte et stocke le résultat
    dans website_content. Retourne True si au moins un plan a été enregistré."""
    try:
        response = requests.get(URL, headers=HEADERS, timeout=15)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Impossible de télécharger {URL} : {e}")
        return False

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".pricing-new-wrapper")

    if not cards:
        logger.error(
            "Aucune carte de plan trouvée (sélecteur .pricing-new-wrapper) — "
            "la structure HTML de vala.ma a probablement changé."
        )
        return False

    plans = []
    for i, card in enumerate(cards):
        try:
            plans.append(_parse_card(card))
        except ValueError as e:
            logger.warning(f"Carte #{i} ignorée : {e}")

    if not plans:
        logger.error("Toutes les cartes ont échoué au parsing — structure HTML changée ?")
        return False

    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    # Repart d'une base propre pour cette URL, pour ne pas accumuler d'anciens prix
    cursor.execute("DELETE FROM website_content WHERE url = ?", (URL,))

    scraped_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for plan in plans:
        cursor.execute('''
        INSERT INTO website_content (url, title, content, scraped_at)
        VALUES (?, ?, ?, ?)
        ''', (URL, plan["name"], json.dumps(plan["content"], ensure_ascii=False), scraped_at))

    conn.commit()
    conn.close()

    logger.info(f"✅ {len(plans)} plan(s) enregistré(s) depuis {URL}")
    return True


if __name__ == "__main__":
    if scrape_hosting_plans():
        print("✅ Scraping terminé avec succès.")
    else:
        print("❌ Le scraping a échoué — voir les logs ci-dessus.")
