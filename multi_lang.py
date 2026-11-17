"""
Multi-language post matcher and synchronizer.
Matches Dutch posts with their English, German, and French equivalents.
"""

import urllib.request
import urllib.parse
import json
import re
from datetime import datetime, timedelta

def get_post_by_url(url: str) -> list[dict]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return []

def find_language_post(nl_post: dict, lang: str = "en") -> dict | None:
    """Find matching post in another language version (en, de, fr)."""
    nl_date_str = nl_post.get("date", "")
    if not nl_date_str:
        return None
        
    try:
        nl_dt = datetime.fromisoformat(nl_date_str)
    except Exception:
        return None
        
    start_dt = (nl_dt - timedelta(days=4)).strftime("%Y-%m-%dT00:00:00")
    end_dt = (nl_dt + timedelta(days=4)).strftime("%Y-%m-%dT23:59:59")
    
    url = f"https://anthuriuminfo.com/{lang}/wp-json/wp/v2/posts?after={start_dt}&before={end_dt}&_embed=1"
    candidates = get_post_by_url(url)
    if not candidates:
        return None
        
    if len(candidates) == 1:
        return candidates[0]
        
    # Match by featured media filename
    nl_fm = ""
    nl_embedded = nl_post.get("_embedded", {})
    if "wp:featuredmedia" in nl_embedded and nl_embedded["wp:featuredmedia"]:
        nl_fm = nl_embedded["wp:featuredmedia"][0].get("source_url", "").split("/")[-1].split("?")[0].lower()
        nl_fm_base = re.sub(r'-\d+x\d+', '', nl_fm)
        nl_fm_base = re.sub(r'-\d+', '', nl_fm_base)
    
    for cand in candidates:
        cand_embedded = cand.get("_embedded", {})
        if "wp:featuredmedia" in cand_embedded and cand_embedded["wp:featuredmedia"]:
            cand_fm = cand_embedded["wp:featuredmedia"][0].get("source_url", "").split("/")[-1].split("?")[0].lower()
            cand_fm_base = re.sub(r'-\d+x\d+', '', cand_fm)
            cand_fm_base = re.sub(r'-\d+', '', cand_fm_base)
            if nl_fm_base and cand_fm_base and (nl_fm_base in cand_fm_base or cand_fm_base in nl_fm_base):
                return cand
                
    return candidates[0]

def analyze_posts_languages(posts: list[dict], selected_langs: list[str]) -> list[dict]:
    """Pre-import analysis: check availability of translations for each post."""
    analysis = []
    for p in posts:
        post_title = p.get("title", {}).get("rendered", "")
        post_date = p.get("date", "")[:10]
        item_status = {
            "id": p.get("id"),
            "title": post_title,
            "date": post_date,
            "languages": {"nl": True}
        }
        for lang in ["en", "de", "fr"]:
            if lang in selected_langs:
                match = find_language_post(p, lang)
                item_status["languages"][lang] = (match is not None)
                if match:
                    item_status[f"{lang}_title"] = match.get("title", {}).get("rendered", "")
            else:
                item_status["languages"][lang] = False
        analysis.append(item_status)
    return analysis
