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
import os
from typing import Dict, Any, List, Optional, Tuple

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PARSED_EXPORT_CACHE_FILE = "last_parsed_export.json"

def save_parsed_export_cache(data: Dict[str, Any], filepath: str = PARSED_EXPORT_CACHE_FILE):
    """Persist parsed/exported items to local JSON cache for fast verification."""
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Warning: could not save parsed export cache: {e}")

def load_parsed_export_cache(filepath: str = PARSED_EXPORT_CACHE_FILE) -> Optional[Dict[str, Any]]:
    """Load previously parsed/exported items from local JSON cache."""
    try:
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return None

def match_cached_item(
    target_slug: str,
    target_title: str,
    cached_items: List[Dict[str, Any]],
    lang: str = "nl"
) -> Optional[Dict[str, Any]]:
    """
    Match a target article against local parsed/exported items:
    1. Match by slug (or slug prefix before ~)
    2. Match by title similarity >= 0.70
    """
    if not cached_items:
        return None

    clean_slug = (target_slug or "").strip().lower().replace("-copy", "")
    clean_title = (target_title or "").strip()

    # 1. Check slug
    if clean_slug:
        for it in cached_items:
            it_slug = (it.get("slug", {}).get(lang) or it.get("slug", {}).get("nl") or "").lower()
            if it_slug and (it_slug == clean_slug or it_slug.startswith(clean_slug) or clean_slug.startswith(it_slug)):
                return it

    # 2. Check title similarity
    if clean_title:
        best_item = None
        best_score = 0.0
        for it in cached_items:
            it_title = it.get("name", {}).get(lang) or it.get("name", {}).get("nl") or ""
            score = calculate_similarity(clean_title, it_title)
            if score > best_score:
                best_score = score
                best_item = it
        if best_item and best_score >= 0.65:
            return best_item

    return None

def match_source_post(
    target_slug: str,
    target_title: str,
    wp_api_base: str = "https://anthuriuminfo.com"
) -> Optional[Dict[str, Any]]:
    """
    Intelligently find the matching WordPress source post for a given target slug and title:
    1. Exact slug match (if slug is non-empty)
    2. Slug without '-copy'
    3. Title search in WP API with ranking by similarity score >= 0.70
    4. Slug keywords search in WP API
    """
    clean_base = wp_api_base.rstrip('/')

    # Strategy 1 & 2: Match by slug (only if slug is provided and not empty)
    clean_slug = (target_slug or "").strip()
    if clean_slug:
        candidates_slugs = [clean_slug]
        if "-copy" in clean_slug:
            candidates_slugs.append(clean_slug.replace("-copy", ""))

        for s in candidates_slugs:
            if not s:
                continue
            try:
                url = f"{clean_base}/wp-json/wp/v2/posts?slug={urllib.parse.quote(s)}&_embed=1"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res and isinstance(res, list):
                        return res[0]
            except Exception:
                pass

    # Strategy 3: Primary search by Title in WP API
    if target_title and target_title.strip():
        clean_title = target_title.strip()
        # Find meaningful title words
        title_words = [w for w in re.findall(r'\b[a-zA-Z0-9]{3,}\b', clean_title)]
        if title_words:
            # Try specific keywords first
            query_terms = "+".join(title_words[:4])
            try:
                url = f"{clean_base}/wp-json/wp/v2/posts?search={query_terms}&_embed=1"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res and isinstance(res, list):
                        best_match = None
                        best_score = 0.0
                        for post in res:
                            p_title = html.unescape(post.get("title", {}).get("rendered", ""))
                            score = calculate_similarity(clean_title, p_title)
                            if score > best_score:
                                best_score = score
                                best_match = post
                        if best_match and best_score >= 0.65:
                            return best_match
            except Exception:
                pass

    # Strategy 4: Fallback to slug keywords if title search didn't match
    if clean_slug:
        slug_words = [w for w in clean_slug.replace("-copy", "").split("-") if len(w) > 3]
        if slug_words:
            query_terms = "+".join(slug_words[:3])
            try:
                url = f"{clean_base}/wp-json/wp/v2/posts?search={query_terms}&_embed=1"
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=8) as r:
                    res = json.loads(r.read().decode("utf-8"))
                    if res and isinstance(res, list):
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
    max_pages: int = 10,
    progress_callback = None,
    stop_at_count: int = 0
) -> List[Dict[str, str]]:
    """
    Crawl archive pagination on target site and collect published article URLs and slugs.
    Supports:
    1. Standard domain archive: e.g. https://test13242.mach3blocks.io/nl/tips-advies/
    2. Mach3Blocks Preview overview: e.g. https://app.mach3blocks.io/preview/?wid=113568&pid=...&pkey=...
    3. Custom overview URLs with query params.
    Uses concurrent fetching for ultra-fast archive discovery.
    """
    found_articles = []
    seen_urls = set()

    parsed_input = urllib.parse.urlparse(base_url.strip())
    domain_base = f"{parsed_input.scheme}://{parsed_input.netloc}"
    is_preview = "preview" in parsed_input.path or "app.mach3blocks.io" in parsed_input.netloc or bool(parsed_input.query)

    def build_page_url(p_num: int) -> str:
        if is_preview:
            qs = urllib.parse.parse_qs(parsed_input.query)
            if p_num > 1:
                qs['page'] = [str(p_num)]
            else:
                qs.pop('page', None)
            new_query = urllib.parse.urlencode(qs, doseq=True)
            return urllib.parse.urlunparse((
                parsed_input.scheme,
                parsed_input.netloc,
                parsed_input.path,
                parsed_input.params,
                new_query,
                parsed_input.fragment
            ))
        else:
            clean_base = domain_base.rstrip('/')
            clean_path = archive_path if archive_path.startswith('/') else f"/{archive_path}"
            if p_num == 1:
                return f"{clean_base}{clean_path}"
            else:
                delim = "&" if "?" in clean_path else "?"
                return f"{clean_base}{clean_path}{delim}page={p_num}"

    def extract_articles_from_html(content: str) -> List[Dict[str, str]]:
        page_items = []
        page_seen = set()

        # Pattern 1: Mach3Blocks preview links
        preview_links = re.findall(r'href=[\"\'](/preview/\?[^\"\']*(?:ciid|cid)=[^\"\']+)[\"\']', content)
        for p_href in preview_links:
            clean_href = html.unescape(p_href).replace('&amp;', '&')
            full_url = f"{domain_base}{clean_href}"
            if full_url not in page_seen:
                page_seen.add(full_url)
                page_items.append({
                    "url": full_url,
                    "slug": "",
                    "nano_id": "",
                    "path": clean_href
                })

        # Pattern 2: Standard blog links
        standard_links = re.findall(r'href=[\"\'](/nl/blog/([^/\"\'~]+)(?:~([^/\"\'~]+))?/?[\"\'])', content)
        for rel_href, slug_part, nano_id in standard_links:
            full_path = rel_href.split('"')[0].split("'")[0]
            if not full_path.endswith('/'):
                full_path += '/'
            full_target_url = f"{domain_base}{full_path}"
            if full_target_url not in page_seen:
                page_seen.add(full_target_url)
                page_items.append({
                    "url": full_target_url,
                    "slug": slug_part,
                    "nano_id": nano_id or "",
                    "path": full_path
                })

        return page_items

    from concurrent.futures import ThreadPoolExecutor

    def fetch_single_page(p_num: int):
        u = build_page_url(p_num)
        try:
            req = urllib.request.Request(u, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8', errors='ignore')
                return p_num, extract_articles_from_html(raw)
        except Exception:
            return p_num, []

    # Fetch pages in chunks of 10 concurrently
    chunk_size = 10
    curr_start_page = 1
    max_crawl_pages = 100 if max_pages <= 0 else max_pages

    while curr_start_page <= max_crawl_pages:
        chunk_end = min(curr_start_page + chunk_size - 1, max_crawl_pages)
        pages_to_fetch = list(range(curr_start_page, chunk_end + 1))

        if progress_callback:
            progress_callback(curr_start_page, len(found_articles))

        with ThreadPoolExecutor(max_workers=min(10, len(pages_to_fetch))) as pool:
            results = list(pool.map(fetch_single_page, pages_to_fetch))

        # Sort results by page number to preserve order
        results.sort(key=lambda x: x[0])

        consecutive_empty = False
        for p_num, items in results:
            if not items:
                consecutive_empty = True
                break
            for item in items:
                if item["url"] not in seen_urls:
                    seen_urls.add(item["url"])
                    found_articles.append(item)

            if stop_at_count > 0 and len(found_articles) >= stop_at_count:
                return found_articles[:stop_at_count]

        if consecutive_empty:
            break

        curr_start_page += chunk_size

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
