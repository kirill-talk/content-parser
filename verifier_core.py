"""
Core Content Verification Engine.
Compares source website content (or generated JSON export) against published target pages (Mach3Blocks).
Specializes in text matching (intro, text-1, text-2) and social embed verification (Instagram, TikTok).
Runs entirely on Python standard library.
"""

import urllib.request
import urllib.parse
import json
import re
import html
import difflib
from typing import Dict, Any, List, Optional, Tuple

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

def match_source_post(
    target_slug: str,
    target_title: str,
    wp_api_base: str = "https://anthuriuminfo.com"
) -> Optional[Dict[str, Any]]:
    """
    Intelligently find the matching WordPress source post for a given target slug and title:
    1. Exact slug match
    2. Slug without '-copy'
    3. WP search by slug keywords
    4. WP search by title keywords with similarity ranking >= 0.65
    """
    clean_base = wp_api_base.rstrip('/')

    candidates_slugs = [target_slug]
    if "-copy" in target_slug:
        candidates_slugs.append(target_slug.replace("-copy", ""))

    for s in candidates_slugs:
        try:
            url = f"{clean_base}/wp-json/wp/v2/posts?slug={urllib.parse.quote(s)}&_embed=1"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=8) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res and isinstance(res, list):
                    return res[0]
        except Exception:
            pass

    slug_words = [w for w in target_slug.replace("-copy", "").split("-") if len(w) > 3]
    if slug_words:
        query_terms = "+".join(slug_words[:3])
        try:
            url = f"{clean_base}/wp-json/wp/v2/posts?search={query_terms}&_embed=1"
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=8) as r:
                res = json.loads(r.read().decode("utf-8"))
                if res:
                    best_match = None
                    best_score = 0.0
                    for post in res:
                        p_title = html.unescape(post.get("title", {}).get("rendered", ""))
                        score = calculate_similarity(target_title, p_title)
                        if score > best_score:
                            best_score = score
                            best_match = post
                    if best_match and best_score >= 0.65:
                        return best_match
        except Exception:
            pass

    if target_title:
        title_words = [w for w in re.findall(r'\b[a-zA-Z]{4,}\b', target_title)][:4]
        if title_words:
            query_terms = "+".join(title_words)
            try:
                url = f"{clean_base}/wp-json/wp/v2/posts?search={query_terms}&_embed=1"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res:
                        best_match = None
                        best_score = 0.0
                        for post in res:
                            p_title = html.unescape(post.get("title", {}).get("rendered", ""))
                            score = calculate_similarity(target_title, p_title)
                            if score > best_score:
                                best_score = score
                                best_match = post
                        if best_match and best_score >= 0.65:
                            return best_match
            except Exception:
                pass

    return None

def normalize_text(raw_text: str) -> str:
    """Strip HTML tags, decode entities, replace non-breaking spaces and normalize whitespace."""
    if not raw_text:
        return ""
    # Strip HTML tags
    clean = re.sub(r'<[^>]+>', ' ', raw_text)
    clean = html.unescape(clean)
    # Replace non-breaking space & special punctuation
    clean = clean.replace('\xa0', ' ').replace('&nbsp;', ' ')
    # Normalize excessive whitespace
    clean = re.sub(r'\s+', ' ', clean).strip()
    return clean

def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate text similarity ratio between 0.0 and 1.0 (1.0 = identical)."""
    norm1 = normalize_text(text1)
    norm2 = normalize_text(text2)
    if not norm1 and not norm2:
        return 1.0
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0
    return difflib.SequenceMatcher(None, norm1, norm2).ratio()

def generate_diff(expected: str, actual: str) -> List[str]:
    """Generate unified-style diff lines between expected and actual text."""
    exp_lines = normalize_text(expected).split('. ')
    act_lines = normalize_text(actual).split('. ')
    diff = list(difflib.unified_diff(
        exp_lines, act_lines,
        fromfile='Source / Export', tofile='Target (Mach3Blocks)',
        lineterm=''
    ))
    return diff

def extract_social_embed_urls(raw_html: str) -> Dict[str, List[str]]:
    """Extract Instagram and TikTok URLs from HTML content or embeds."""
    embeds = {"instagram": [], "tiktok": []}
    if not raw_html:
        return embeds

    # Instagram matching (p/code, reel/code, tv/code)
    ig_matches = re.findall(
        r'https?://(?:www\.)?instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)',
        raw_html
    )
    for code in ig_matches:
        url = f"https://www.instagram.com/reel/{code}/"
        if url not in embeds["instagram"]:
            embeds["instagram"].append(url)

    # Also check generic data-url attributes for Instagram
    data_urls = re.findall(r'data-url=[\"\']([^\"\']+)[\"\']', raw_html)
    for du in data_urls:
        if "instagram.com" in du:
            m = re.search(r'instagram\.com/(?:p|reel|tv)/([a-zA-Z0-9_-]+)', du)
            if m:
                clean_url = f"https://www.instagram.com/reel/{m.group(1)}/"
                if clean_url not in embeds["instagram"]:
                    embeds["instagram"].append(clean_url)

    # TikTok matching
    tt_matches = re.findall(
        r'https?://(?:www\.)?tiktok\.com/@[^/]+/video/(\d+)',
        raw_html
    )
    for vid_id in tt_matches:
        # Match full URL or canonical video URL
        full_match = re.search(rf'https?://(?:www\.)?tiktok\.com/@[^/\"\'\s]+/video/{vid_id}', raw_html)
        url = full_match.group(0) if full_match else f"https://www.tiktok.com/@video/{vid_id}"
        if url not in embeds["tiktok"]:
            embeds["tiktok"].append(url)

    return embeds

def discover_target_articles(
    base_url: str = "https://test13242.mach3blocks.io",
    archive_path: str = "/nl/tips-advies/",
    max_pages: int = 10
) -> List[Dict[str, str]]:
    """
    Crawl archive pagination on target site and collect published article URLs and slugs.
    Returns list of dicts: [{'url': ..., 'slug': ..., 'nano_id': ...}]
    """
    clean_base = base_url.rstrip('/')
    found_articles = []
    seen_urls = set()

    for page in range(1, max_pages + 1):
        if page == 1:
            page_url = f"{clean_base}{archive_path}"
        else:
            page_url = f"{clean_base}{archive_path}?page={page}"

        try:
            req = urllib.request.Request(page_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=12) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
        except Exception:
            break

        # Match links to blog posts: /nl/blog/{slug-with-nano-id}/
        links = re.findall(r'href=[\"\'](/nl/blog/([^/\"\'~]+)(?:~([^/\"\'~]+))?/?[\"\'])', content)
        if not links:
            break

        new_on_page = 0
        for rel_href, slug_part, nano_id in links:
            # Normalize full URL
            full_path = rel_href.split('"')[0].split("'")[0]
            if not full_path.endswith('/'):
                full_path += '/'
            full_target_url = f"{clean_base}{full_path}"

            if full_target_url not in seen_urls:
                seen_urls.add(full_target_url)
                new_on_page += 1
                found_articles.append({
                    "url": full_target_url,
                    "slug": slug_part,
                    "nano_id": nano_id or "",
                    "path": full_path
                })

        if new_on_page == 0:
            break

    return found_articles

def parse_target_page(html_content: str, target_url: str = "") -> Dict[str, Any]:
    """
    Scrape structured content fields from Mach3Blocks article HTML.
    Extracts title, intro text, body text blocks, media captions, and social embeds.
    """
    result = {
        "url": target_url,
        "title": "",
        "intro_text": "",
        "text_1": "",
        "text_2": "",
        "embed_urls": {"instagram": [], "tiktok": []},
        "boxes_with_data_url": [],
        "images": [],
        "tags": []
    }

    # 1. Title (H1)
    h1_match = re.search(r'<h1[^>]*>(.*?)</h1>', html_content, re.DOTALL)
    if h1_match:
        result["title"] = normalize_text(h1_match.group(1))

    # 2. Extract sections / custom-blocks
    # Mach3Blocks structure:
    # - custom-block-28055845 (Hero / Title + Intro text)
    # - custom-block-28056034 (Text-1 / Embeds)
    # - custom-block-28056038 (Text-2)
    
    # Intro text: often inside custom-block-28055845 in a .text-3 dark div
    hero_match = re.search(r'id=[\"\']custom-block-28055845[\"\'][^>]*>(.*?)(?=<section|\Z)', html_content, re.DOTALL)
    if hero_match:
        intro_match = re.search(r'<div[^>]*class=[\"\'][^\"\']*text-3[^\"\']*[\"\'][^>]*>(.*?)</div>', hero_match.group(1), re.DOTALL)
        if intro_match:
            result["intro_text"] = intro_match.group(1).strip()

    # Text-1: inside custom-block-28056034
    block_34 = re.search(r'id=[\"\']custom-block-28056034[\"\'][^>]*>(.*?)(?=<section|\Z)', html_content, re.DOTALL)
    if block_34:
        b1_content = block_34.group(1)
        t1_match = re.search(r'<div[^>]*class=[\"\'][^\"\']*text-3[^\"\']*[\"\'][^>]*>(.*?)</div>', b1_content, re.DOTALL)
        if t1_match:
            result["text_1"] = t1_match.group(1).strip()

    # Text-2: inside custom-block-28056038
    block_38 = re.search(r'id=[\"\']custom-block-28056038[\"\'][^>]*>(.*?)(?=<section|\Z)', html_content, re.DOTALL)
    if block_38:
        b2_content = block_38.group(1)
        t2_match = re.search(r'<div[^>]*class=[\"\'][^\"\']*text-3[^\"\']*[\"\'][^>]*>(.*?)</div>', b2_content, re.DOTALL)
        if t2_match:
            result["text_2"] = t2_match.group(1).strip()

    # Fallback if custom-block IDs vary: collect all .text-3 dark elements in order
    if not result["intro_text"] and not result["text_1"]:
        all_text3 = re.findall(r'<div[^>]*class=[\"\'][^\"\']*text-3 dark(?:\s+[^\"\']*)?[\"\'][^>]*>(.*?)</div>', html_content, re.DOTALL)
        non_empty = [t.strip() for t in all_text3 if t.strip() and not t.strip() == '<div class="text-3 dark empty"></div>']
        if len(non_empty) >= 1:
            result["intro_text"] = non_empty[0]
        if len(non_empty) >= 2:
            result["text_1"] = non_empty[1]
        if len(non_empty) >= 3:
            result["text_2"] = non_empty[2]

    # 3. Social Embeds Detection
    # Look for .box[data-url] elements
    box_urls = re.findall(r'<div[^>]*class=[\"\'][^\"\']*box[^\"\']*[\"\'][^>]*data-url=[\"\']([^\"\']+)[\"\']', html_content)
    result["boxes_with_data_url"] = box_urls

    extracted = extract_social_embed_urls(html_content)
    result["embed_urls"] = extracted

    # 4. Images
    img_tags = re.findall(r'<img[^>]+src=[\"\']([^\"\']+)[\"\']', html_content)
    result["images"] = [img for img in img_tags if not any(x in img for x in ['logo', 'icon', 'arrow', 'flag'])]

    return result

def compare_article(
    source_item: Dict[str, Any],
    target_page_data: Optional[Dict[str, Any]],
    lang: str = "nl"
) -> Dict[str, Any]:
    """
    Compare a source article (from WP API or Mach3Blocks JSON export item) with scraped target page data.
    Evaluates:
    - Title similarity
    - Intro text similarity
    - Text-1 similarity
    - Text-2 similarity
    - Instagram / TikTok embed status
    Returns a comprehensive result dictionary with overall pass/warn/fail status and field diffs.
    """
    # Extract expected fields from source
    # Source may be raw WP item or transformed Mach3Blocks export item
    if "fields" in source_item:
        # It's an exported Mach3Blocks JSON item
        exp_title = source_item.get("name", {}).get(lang, "")
        fields = source_item.get("fields", {})
        exp_intro = fields.get("item-intro-text", {}).get("value", {}).get(lang, "")
        exp_text1 = fields.get("text-1", {}).get("value", {}).get(lang, "")
        exp_text2 = fields.get("text-2", {}).get("value", {}).get(lang, "")
        exp_embed = fields.get("instagram", {}).get("value", {}).get(lang, "")
        source_url = source_item.get("source-url", "")
        slug = source_item.get("slug", {}).get(lang, "")
    else:
        # It's a raw WP item
        exp_title = html.unescape(source_item.get("title", {}).get("rendered", ""))
        source_url = source_item.get("link", "")
        slug = source_item.get("slug", "")
        from splitter import ContentSplitter
        splitter = ContentSplitter(source_item.get("content", {}).get("rendered", ""), post_title=exp_title)
        split = splitter.split()
        exp_intro = split.get("item-intro-text", "")
        exp_text1 = split.get("text-1", "")
        exp_text2 = split.get("text-2", "")
        exp_embed = split.get("instagram", "")

    # Expected embed details
    exp_embed_type = None
    exp_embed_url = exp_embed.strip() if exp_embed else ""
    if "instagram.com" in exp_embed_url:
        exp_embed_type = "instagram"
    elif "tiktok.com" in exp_embed_url:
        exp_embed_type = "tiktok"

    if not target_page_data:
        return {
            "status": "MISSING_TARGET",
            "slug": slug,
            "source_url": source_url,
            "target_url": None,
            "title": {"expected": exp_title, "actual": "", "similarity": 0.0, "status": "MISSING"},
            "intro": {"expected": exp_intro, "actual": "", "similarity": 0.0, "status": "MISSING"},
            "text_1": {"expected": exp_text1, "actual": "", "similarity": 0.0, "status": "MISSING"},
            "text_2": {"expected": exp_text2, "actual": "", "similarity": 0.0, "status": "MISSING"},
            "embeds": {
                "expected": exp_embed_url,
                "expected_type": exp_embed_type,
                "found_urls": [],
                "status": "NOT_FOUND" if exp_embed_type else "NONE"
            },
            "summary": "Article not found on target site."
        }

    # Title check
    title_sim = calculate_similarity(exp_title, target_page_data.get("title", ""))
    title_status = "MATCH" if title_sim >= 0.95 else ("WARN" if title_sim >= 0.8 else "MISMATCH")

    # Intro check
    intro_sim = calculate_similarity(exp_intro, target_page_data.get("intro_text", ""))
    intro_status = "MATCH" if intro_sim >= 0.95 else ("WARN" if intro_sim >= 0.8 else "MISMATCH")

    # Text-1 check
    t1_sim = calculate_similarity(exp_text1, target_page_data.get("text_1", ""))
    t1_status = "MATCH" if t1_sim >= 0.95 else ("WARN" if t1_sim >= 0.8 else "MISMATCH")

    # Text-2 check
    t2_sim = calculate_similarity(exp_text2, target_page_data.get("text_2", ""))
    t2_status = "MATCH" if t2_sim >= 0.95 else ("WARN" if t2_sim >= 0.8 else "MISMATCH")

    # Embed check
    # Target may store embed in boxes_with_data_url or in embed_urls
    found_embed_urls = target_page_data.get("boxes_with_data_url", []) + \
                       target_page_data.get("embed_urls", {}).get("instagram", []) + \
                       target_page_data.get("embed_urls", {}).get("tiktok", [])
    
    embed_status = "NONE"
    if exp_embed_type:
        # Normalize and extract code/id to match
        matched = False
        if exp_embed_type == "instagram":
            exp_code = re.search(r'/(?:p|reel|tv)/([a-zA-Z0-9_-]+)', exp_embed_url)
            if exp_code:
                for fu in found_embed_urls:
                    if exp_code.group(1) in fu:
                        matched = True
                        break
        elif exp_embed_type == "tiktok":
            exp_id = re.search(r'/video/(\d+)', exp_embed_url)
            if exp_id:
                for fu in found_embed_urls:
                    if exp_id.group(1) in fu:
                        matched = True
                        break

        if matched:
            embed_status = "MATCH"
        else:
            embed_status = "MISSING"
    else:
        # Expected none, verify if unexpected embed exists
        embed_status = "NONE" if not found_embed_urls else "EXTRA"

    # Overall article verification status
    critical_sims = [intro_sim, t1_sim]
    if normalize_text(exp_text2):
        critical_sims.append(t2_sim)

    min_sim = min(critical_sims) if critical_sims else 1.0

    if embed_status == "MISSING":
        overall = "FAILED"
    elif min_sim >= 0.95 and title_status == "MATCH" and embed_status in ["MATCH", "NONE"]:
        overall = "PASSED"
    elif min_sim >= 0.80 and title_status in ["MATCH", "WARN"]:
        overall = "WARNING"
    else:
        overall = "FAILED"

    return {
        "status": overall,
        "slug": slug,
        "source_url": source_url,
        "target_url": target_page_data.get("url"),
        "title": {
            "expected": exp_title,
            "actual": target_page_data.get("title", ""),
            "similarity": round(title_sim * 100, 1),
            "status": title_status
        },
        "intro": {
            "expected": exp_intro,
            "actual": target_page_data.get("intro_text", ""),
            "similarity": round(intro_sim * 100, 1),
            "status": intro_status,
            "diff": generate_diff(exp_intro, target_page_data.get("intro_text", "")) if intro_sim < 0.95 else []
        },
        "text_1": {
            "expected": exp_text1,
            "actual": target_page_data.get("text_1", ""),
            "similarity": round(t1_sim * 100, 1),
            "status": t1_status,
            "diff": generate_diff(exp_text1, target_page_data.get("text_1", "")) if t1_sim < 0.95 else []
        },
        "text_2": {
            "expected": exp_text2,
            "actual": target_page_data.get("text_2", ""),
            "similarity": round(t2_sim * 100, 1),
            "status": t2_status,
            "diff": generate_diff(exp_text2, target_page_data.get("text_2", "")) if t2_sim < 0.95 else []
        },
        "embeds": {
            "expected": exp_embed_url,
            "expected_type": exp_embed_type,
            "found_urls": found_embed_urls,
            "status": embed_status
        }
    }
