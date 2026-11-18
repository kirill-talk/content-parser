"""
WordPress API client and Mach3Blocks post transformer with dynamic language support.
"""

import urllib.request
import urllib.parse
import json
import secrets
import string
import html
import re
from datetime import datetime

from splitter import ContentSplitter
from tag_mapper import format_tags_html, map_tags_to_ids, TAXONOMY_TREE
from multi_lang import find_language_post

def generate_nano_id(length=8) -> str:
    """Generate an alphanumeric nano-id matching Mach3Blocks style (e.g. oX6WgXe9)."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))

def fetch_posts(site_url: str = "https://anthuriuminfo.com", per_page: int = 5, page: int = 1, offset: int = None) -> list[dict]:
    """Fetch raw posts with embedded media and terms from WordPress REST API."""
    if offset is not None:
        api_url = f"{site_url.rstrip('/')}/wp-json/wp/v2/posts?per_page={per_page}&offset={offset}&_embed=1"
    else:
        api_url = f"{site_url.rstrip('/')}/wp-json/wp/v2/posts?per_page={per_page}&page={page}&_embed=1"
    req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))

def transform_post(post: dict, base_domain: str = "https://test13242.mach3blocks.io", selected_langs: list[str] = None) -> dict:
    """Transform a single WordPress post into a Mach3Blocks item dict with user-selected languages."""
    if not selected_langs:
        selected_langs = ["nl", "en"]
    if "nl" not in selected_langs:
        selected_langs.insert(0, "nl")

    post_id = post.get("id", 0)
    nano_id = generate_nano_id()
    title_raw = html.unescape(post.get("title", {}).get("rendered", ""))
    slug = post.get("slug", "")
    
    # Extract featured media
    featured_media_url = ""
    featured_media_alt = title_raw
    embedded = post.get("_embedded", {})
    if "wp:featuredmedia" in embedded and embedded["wp:featuredmedia"]:
        fm = embedded["wp:featuredmedia"][0]
        featured_media_url = fm.get("source_url", "")
        featured_media_alt = fm.get("alt_text", "") or title_raw
        
    # Extract terms (categories and tags)
    tag_names = []
    cat_names = []
    cat_ids = post.get("categories", [])
    if "wp:term" in embedded:
        for term_group in embedded["wp:term"]:
            for term in term_group:
                tax = term.get("taxonomy")
                if tax == "post_tag":
                    tag_names.append(term.get("name", ""))
                elif tax == "category":
                    cat_names.append(term.get("name", ""))

    # Publication date and modification date formatting: YYYY-MM-DD HH:MM:SS
    raw_date = post.get("date", "")
    dt_str = ""
    short_date = ""
    if raw_date:
        try:
            dt = datetime.fromisoformat(raw_date)
            dt_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            short_date = dt.strftime("%Y-%m-%d")
        except Exception:
            dt_str = raw_date.replace("T", " ")
            short_date = dt_str.split(" ")[0]

    raw_modified = post.get("modified", "") or raw_date
    mod_str = dt_str
    if raw_modified:
        try:
            dt_m = datetime.fromisoformat(raw_modified)
            mod_str = dt_m.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            mod_str = raw_modified.replace("T", " ")

    def extract_clean_excerpt(raw_html_text: str) -> str:
        """Strip HTML tags and clean whitespace for meta descriptions."""
        if not raw_html_text:
            return ""
        clean = re.sub(r'<[^>]+>', ' ', raw_html_text)
        clean = html.unescape(clean)
        clean = re.sub(r'\s+', ' ', clean).strip()
        # Truncate to reasonable meta description length if necessary (~160 chars)
        if len(clean) > 200:
            clean = clean[:197].rsplit(' ', 1)[0] + '...'
        return clean

    yoast_nl = post.get("yoast_head_json", {})
    desc_nl = yoast_nl.get("description", "") or extract_clean_excerpt(post.get("excerpt", {}).get("rendered", ""))
    og_img_nl = ""
    if yoast_nl.get("og_image") and isinstance(yoast_nl["og_image"], list):
        og_img_nl = yoast_nl["og_image"][0].get("url", "")
    if not og_img_nl:
        og_img_nl = featured_media_url

    # Relative path on source site for 301-redirect
    parsed_source_url = urllib.parse.urlparse(post.get("link", ""))
    source_rel_path_nl = parsed_source_url.path or f"/blog/{slug}/"

    # Process primary Dutch content
    raw_content_nl = post.get("content", {}).get("rendered", "")
    splitter_nl = ContentSplitter(raw_content_nl, featured_media_url=featured_media_url, post_title=title_raw)
    split_nl = splitter_nl.split()

    if not desc_nl:
        desc_nl = extract_clean_excerpt(split_nl["item-intro-text"])

    # Dictionary of lang-specific splits, titles, and SEO meta
    lang_data = {
        "nl": {
            "title": title_raw,
            "slug": slug,
            "split": split_nl,
            "tags_html": format_tags_html(tag_names),
            "meta_description": desc_nl,
            "share_image": og_img_nl,
            "redirect_path": source_rel_path_nl
        }
    }

    # Process other selected languages (en, de, fr)
    for lang in ["en", "de", "fr"]:
        if lang not in selected_langs:
            continue
        trans_post = find_language_post(post, lang)
        if trans_post:
            t_title = html.unescape(trans_post.get("title", {}).get("rendered", ""))
            t_slug = trans_post.get("slug", slug)
            t_content = trans_post.get("content", {}).get("rendered", "")
            t_embedded = trans_post.get("_embedded", {})
            t_fm_url = ""
            if "wp:featuredmedia" in t_embedded and t_embedded["wp:featuredmedia"]:
                t_fm_url = t_embedded["wp:featuredmedia"][0].get("source_url", "")
            t_splitter = ContentSplitter(t_content, featured_media_url=t_fm_url, post_title=t_title)
            t_split = t_splitter.split()

            t_tags = []
            if "wp:term" in t_embedded:
                for tg in t_embedded["wp:term"]:
                    for t in tg:
                        if t.get("taxonomy") == "post_tag":
                            t_tags.append(t.get("name", ""))
            t_tags_html = format_tags_html(t_tags) if t_tags else lang_data["nl"]["tags_html"]

            t_yoast = trans_post.get("yoast_head_json", {})
            t_desc = t_yoast.get("description", "") or extract_clean_excerpt(trans_post.get("excerpt", {}).get("rendered", ""))
            if not t_desc:
                t_desc = extract_clean_excerpt(t_split["item-intro-text"])
            
            t_img = ""
            if t_yoast.get("og_image") and isinstance(t_yoast["og_image"], list):
                t_img = t_yoast["og_image"][0].get("url", "")
            if not t_img:
                t_img = t_fm_url or og_img_nl

            t_parsed_url = urllib.parse.urlparse(trans_post.get("link", ""))
            t_redirect = t_parsed_url.path or f"/{lang}/{t_slug}/"

            lang_data[lang] = {
                "title": t_title,
                "slug": t_slug,
                "split": t_split,
                "tags_html": t_tags_html,
                "meta_description": t_desc,
                "share_image": t_img,
                "redirect_path": t_redirect
            }
        else:
            # Fallback to NL if no translation found
            lang_data[lang] = {
                "title": title_raw,
                "slug": slug,
                "split": split_nl,
                "tags_html": lang_data["nl"]["tags_html"],
                "meta_description": desc_nl,
                "share_image": og_img_nl,
                "redirect_path": source_rel_path_nl
            }

    # Primary media HTML tags from main post (language-independent images)
    item_media_html = f'<img src="{featured_media_url}" alt="{featured_media_alt}">' if featured_media_url else ""
    media_2_html = split_nl["media-2"] or ""
    media_3_html = split_nl["media-3"] or ""

    assigned_tag_ids = map_tags_to_ids(tag_names, cat_names, category_ids=cat_ids)
    original_link = post.get("link", f"https://anthuriuminfo.com/blog/{slug}/")

    # Build dynamic multi-language fields dict based on selected_langs
    def make_lang_field(key_getter):
        return {l: key_getter(lang_data[l]) for l in selected_langs if l in lang_data}

    item_fields = {
        "item-heading": {"value": make_lang_field(lambda d: d["title"])},
        "date": {"value": {l: short_date for l in selected_langs}},
        "item-media": {"value": {l: item_media_html for l in selected_langs}},
        "media-size": {"value": {l: "" for l in selected_langs}},
        "tags": {"value": make_lang_field(lambda d: d["tags_html"])},
        "item-intro-text": {"value": make_lang_field(lambda d: d["split"]["item-intro-text"])},
        "media-2": {"value": {l: media_2_html for l in selected_langs}},
        "media-2-text": {"value": make_lang_field(lambda d: d["split"]["media-2-text"] or split_nl["media-2-text"])},
        "text-1": {"value": make_lang_field(lambda d: d["split"]["text-1"])},
        "media-3": {"value": {l: media_3_html for l in selected_langs}},
        "media-3-text": {"value": make_lang_field(lambda d: d["split"]["media-3-text"] or split_nl["media-3-text"])},
        "text-2": {"value": make_lang_field(lambda d: d["split"]["text-2"])},
        "instagram": {"value": make_lang_field(lambda d: d["split"]["instagram"] or split_nl["instagram"])}
    }

    name_dict = {l: lang_data[l]["title"] for l in selected_langs}
    slug_dict = {l: lang_data[l]["slug"] for l in selected_langs}
    meta_desc_dict = {l: lang_data[l]["meta_description"] for l in selected_langs}
    share_img_dict = {l: lang_data[l]["share_image"] for l in selected_langs}
    redirect_dict = {l: [lang_data[l]["redirect_path"]] if lang_data[l]["redirect_path"] else [] for l in selected_langs}

    # Check robots meta from Yoast
    robots = yoast_nl.get("robots", {})
    noindex = robots.get("index") == "noindex"
    nofollow = robots.get("follow") == "nofollow"

    return {
        "id": post_id,
        "nano-id": nano_id,
        "source-url": original_link,
        "name": name_dict,
        "slug": slug_dict,
        "301-redirect": redirect_dict,
        "target": {l: "_self" for l in selected_langs},
        "aria-label": name_dict,
        "meta-title": name_dict,
        "meta-description": meta_desc_dict,
        "meta-keywords": {l: "" for l in selected_langs},
        "share-title": name_dict,
        "share-description": meta_desc_dict,
        "share-image": share_img_dict,
        "hidden": False,
        "unsearchable": False,
        "noindex": noindex,
        "nofollow": nofollow,
        "show-from": dt_str,
        "hide-from": None,
        "created": dt_str,
        "last-modified": mod_str,
        "publication-date": dt_str,
        "modification-date": mod_str,
        "tags": assigned_tag_ids,
        "fields": item_fields
    }

def build_mach3blocks_json(posts: list[dict], base_domain: str = "https://test13242.mach3blocks.io", selected_langs: list[str] = None) -> dict:
    """Build full Mach3Blocks export JSON with taxonomy tags and parsed items."""
    transformed_items = [transform_post(p, base_domain=base_domain, selected_langs=selected_langs) for p in posts]
    return {
        "tags": TAXONOMY_TREE,
        "items": transformed_items
    }
