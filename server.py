"""
Lightweight Web Admin Server for Content Migration Studio.
Runs on Python standard library without any external dependencies.
"""

import http.server
import socketserver
import json
import urllib.parse
import urllib.request
import html
import os
import sys

from parser_core import fetch_posts, transform_post, build_mach3blocks_json
from multi_lang import analyze_posts_languages
from tag_mapper import TAXONOMY_TREE, load_effective_mapping, save_custom_mapping
from agents import coordinator
from sources.detector import detect_source
from profiles.manager import list_profiles, get_profile, save_profile
from verifier_core import (
    discover_target_articles,
    parse_target_page,
    compare_article,
    calculate_similarity,
    normalize_text,
    match_source_post,
    match_cached_item,
    save_parsed_export_cache,
    load_parsed_export_cache
)

PORT = 8080
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
WP_TAGS_CACHE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wp_tags_cache.json")

class MigrationHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        params = urllib.parse.parse_qs(parsed_url.query)

        if path == "/api/parse/stream":
            self.handle_api_parse_stream(params)
        elif path == "/api/verify/stream":
            self.handle_api_verify_stream(params)
        elif path == "/api/analyze/stream":
            self.handle_api_analyze_stream(params)
        elif path == "/api/parse":
            self.handle_api_parse(params)
        elif path == "/api/analyze":
            self.handle_api_analyze(params)
        elif path == "/api/verify/target-urls":
            self.handle_api_verify_target_urls(params)
        elif path == "/api/verify/cache":
            self.handle_api_verify_cache()
        elif path == "/api/detect":
            self.handle_api_detect(params)
        elif path == "/api/profiles":
            self.handle_get_profiles()
        elif path == "/api/tags/mapping":
            self.handle_get_tag_mapping()
        elif path == "/api/agents":
            self.handle_api_agents()
        elif path == "/api/status":
            self.handle_api_status()
        else:
            super().do_GET()

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path == "/api/tags/mapping":
            self.handle_save_tag_mapping()
        elif path == "/api/profiles":
            self.handle_save_profile()
        elif path == "/api/verify/single":
            self.handle_api_verify_single()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_api_status(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        res = {"status": "ok", "stage": 2, "languages": ["nl", "en", "de", "fr"]}
        self.wfile.write(json.dumps(res).encode("utf-8"))

    def handle_api_detect(self, params):
        """Detect source capabilities (JSON REST API, total posts, namespaces)."""
        target_url = params.get("url", ["https://anthuriuminfo.com"])[0]
        try:
            detection = detect_source(target_url)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(detection, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_get_profiles(self):
        """Return list of supported site profiles."""
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(list_profiles(), ensure_ascii=False).encode("utf-8"))

    def handle_save_profile(self):
        """Save custom site profile."""
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            pid = save_profile(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True, "id": pid}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_api_agents(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(coordinator.to_dict()).encode("utf-8"))

    def handle_get_tag_mapping(self):
        """Return all WP tags with counts, current mapping, and Mach3Blocks available targets."""
        effective_map = load_effective_mapping()
        
        # Load cached WP tags
        wp_tags = []
        if os.path.exists(WP_TAGS_CACHE_FILE):
            try:
                with open(WP_TAGS_CACHE_FILE, "r", encoding="utf-8") as f:
                    wp_tags = json.load(f)
            except Exception:
                pass

        # Build list of available Mach3Blocks target tags
        targets = []
        for grp in TAXONOMY_TREE:
            g_title = grp.get("name", {}).get("nl") if isinstance(grp.get("name"), dict) else (grp.get("name") or "Algemeen")
            for t in grp.get("tags", []):
                t_name = t.get("name", {}).get("nl", "")
                targets.append({"id": t["id"], "name": t_name, "group": g_title})

        response = {
            "wp_tags": wp_tags,
            "mapping": effective_map,
            "targets": targets
        }
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(response, ensure_ascii=False).encode("utf-8"))

    def handle_save_tag_mapping(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
            save_custom_mapping(data)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"success": True}).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_api_analyze_stream(self, params):
        """Stream progress events during translation analysis via Server-Sent Events (SSE)."""
        count = int(params.get("count", [5])[0])
        from_n = params.get("from", [None])[0]
        to_n = params.get("to", [None])[0]
        identifier = params.get("identifier", [None])[0]
        langs_param = params.get("langs", ["nl,en"])[0]
        selected_langs = [l.strip().lower() for l in langs_param.split(",") if l.strip()]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data_dict):
            payload = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(payload)
            self.wfile.flush()

        def send_ping():
            try:
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
            except Exception:
                pass

        coordinator.set_busy("translation_agent", "Analyzing language availability")

        try:
            send_event({
                "type": "status",
                "phase": "fetching",
                "message": "Fetching article list from WordPress REST API..."
            })

            raw_posts = []
            if identifier:
                clean_ident = identifier.strip()
                if clean_ident.startswith("http://") or clean_ident.startswith("https://"):
                    p_path = urllib.parse.urlparse(clean_ident).path
                    parts = [p for p in p_path.split("/") if p]
                    if parts:
                        clean_ident = parts[-1]

                if clean_ident.isdigit():
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts/{clean_ident}?_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = [json.loads(r.read().decode("utf-8"))]
                else:
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts?slug={urllib.parse.quote(clean_ident)}&_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = json.loads(r.read().decode("utf-8"))
                        if not raw_posts:
                            raise ValueError(f"No article found for slug or URL '{clean_ident}'")
            elif from_n is not None and to_n is not None:
                start_n = max(1, int(from_n))
                end_n = max(start_n, int(to_n))
                total_to_fetch = end_n - start_n + 1
                offset = start_n - 1
                raw_posts = self._fetch_posts_in_batches(total_to_fetch, offset=offset)
            else:
                raw_posts = self._fetch_posts_in_batches(count, offset=0)

            total = len(raw_posts)
            send_event({
                "type": "start",
                "phase": "analyzing",
                "total": total,
                "message": f"Retrieved {total} articles. Matching multi-language translations..."
            })

            from multi_lang import find_language_post
            from concurrent.futures import ThreadPoolExecutor

            analysis_result = []
            for idx, p in enumerate(raw_posts, 1):
                post_title = html.unescape(p.get("title", {}).get("rendered", f"Post #{p.get('id', idx)}"))
                post_date = p.get("date", "")[:10]

                send_event({
                    "type": "progress",
                    "current": idx,
                    "total": total,
                    "id": p.get("id"),
                    "title": post_title,
                    "percent": round((idx / total) * 100)
                })

                item_status = {
                    "id": p.get("id"),
                    "title": post_title,
                    "date": post_date,
                    "languages": {"nl": True}
                }

                send_ping()
                check_langs = [l for l in ["en", "de", "fr"] if l in selected_langs]
                if check_langs:
                    with ThreadPoolExecutor(max_workers=len(check_langs)) as pool:
                        futures = {l: pool.submit(find_language_post, p, l) for l in check_langs}
                        for l, f in futures.items():
                            try:
                                match = f.result()
                            except Exception:
                                match = None
                            item_status["languages"][l] = (match is not None)
                            if match:
                                item_status[f"{l}_title"] = match.get("title", {}).get("rendered", "")

                for l in ["en", "de", "fr"]:
                    if l not in item_status["languages"]:
                        item_status["languages"][l] = False

                analysis_result.append(item_status)

            send_event({
                "type": "complete",
                "total": total,
                "data": analysis_result
            })
            self.close_connection = True
        except Exception as e:
            try:
                send_event({
                    "type": "error",
                    "error": str(e)
                })
            except Exception:
                pass
            self.close_connection = True
        finally:
            coordinator.set_ready("translation_agent")

    def handle_api_analyze(self, params):
        """Pre-import analysis: check availability of translations without full HTML payload."""
        count = int(params.get("count", [5])[0])
        from_n = params.get("from", [None])[0]
        to_n = params.get("to", [None])[0]
        identifier = params.get("identifier", [None])[0]
        langs_param = params.get("langs", ["nl,en"])[0]
        selected_langs = [l.strip().lower() for l in langs_param.split(",") if l.strip()]

        coordinator.set_busy("translation_agent", "Analyzing language availability")
        try:
            if identifier:
                clean_ident = identifier.strip()
                if clean_ident.startswith("http://") or clean_ident.startswith("https://"):
                    p_path = urllib.parse.urlparse(clean_ident).path
                    parts = [p for p in p_path.split("/") if p]
                    if parts:
                        clean_ident = parts[-1]

                if clean_ident.isdigit():
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts/{clean_ident}?_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = [json.loads(r.read().decode("utf-8"))]
                else:
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts?slug={urllib.parse.quote(clean_ident)}&_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = json.loads(r.read().decode("utf-8"))
                        if not raw_posts:
                            raise ValueError(f"No article found for slug or URL '{clean_ident}'")
            elif from_n is not None and to_n is not None:
                start_n = max(1, int(from_n))
                end_n = max(start_n, int(to_n))
                total_to_fetch = end_n - start_n + 1
                offset = start_n - 1
                raw_posts = self._fetch_posts_in_batches(total_to_fetch, offset=offset)
            else:
                raw_posts = self._fetch_posts_in_batches(count, offset=0)

            analysis_result = analyze_posts_languages(raw_posts, selected_langs)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(analysis_result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            coordinator.set_ready("translation_agent")

    def _fetch_posts_in_batches(self, count: int, offset: int = 0) -> list[dict]:
        """Fetch posts from WordPress in chunks of up to 100 per request."""
        posts = []
        remaining = count
        curr_offset = offset
        while remaining > 0:
            batch_size = min(remaining, 100)
            batch = fetch_posts(per_page=batch_size, offset=curr_offset)
            if not batch:
                break
            posts.extend(batch)
            remaining -= len(batch)
            curr_offset += len(batch)
            if len(batch) < batch_size:
                break
        return posts

    def handle_api_parse_stream(self, params):
        """Stream progress events during parsing via Server-Sent Events (SSE)."""
        count = int(params.get("count", [5])[0])
        identifier = params.get("identifier", [None])[0]
        from_n = params.get("from", [None])[0]
        to_n = params.get("to", [None])[0]
        langs_param = params.get("langs", ["nl,en"])[0]
        selected_langs = [l.strip().lower() for l in langs_param.split(",") if l.strip()]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data_dict):
            payload = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(payload)
            self.wfile.flush()

        def send_ping():
            try:
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
            except Exception:
                pass

        coordinator.set_busy("content_agent", f"Parsing stream initiated")
        coordinator.set_busy("taxonomy_agent", "Applying taxonomy rules")

        try:
            send_event({
                "type": "status",
                "phase": "fetching",
                "message": "Fetching articles from WordPress REST API..."
            })

            raw_posts = []
            if identifier:
                clean_ident = identifier.strip()
                if clean_ident.startswith("http://") or clean_ident.startswith("https://"):
                    p_path = urllib.parse.urlparse(clean_ident).path
                    parts = [p for p in p_path.split("/") if p]
                    if parts:
                        clean_ident = parts[-1]

                if clean_ident.isdigit():
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts/{clean_ident}?_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = [json.loads(r.read().decode("utf-8"))]
                else:
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts?slug={urllib.parse.quote(clean_ident)}&_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = json.loads(r.read().decode("utf-8"))
                        if not raw_posts:
                            raise ValueError(f"No article found for slug or URL '{clean_ident}'")
            elif from_n is not None and to_n is not None:
                start_n = max(1, int(from_n))
                end_n = max(start_n, int(to_n))
                total_to_fetch = end_n - start_n + 1
                offset = start_n - 1
                raw_posts = self._fetch_posts_in_batches(total_to_fetch, offset=offset)
            else:
                raw_posts = self._fetch_posts_in_batches(count, offset=0)

            total = len(raw_posts)
            send_event({
                "type": "start",
                "phase": "parsing",
                "total": total,
                "message": f"Retrieved {total} articles. Processing translations & blocks..."
            })

            transformed_items = []
            for idx, post in enumerate(raw_posts, 1):
                raw_title = post.get("title", {}).get("rendered", f"Post #{post.get('id', idx)}")
                clean_title = html.unescape(raw_title)

                send_event({
                    "type": "progress",
                    "current": idx,
                    "total": total,
                    "id": post.get("id"),
                    "title": clean_title,
                    "percent": round((idx / total) * 100)
                })

                send_ping()
                item = transform_post(post, selected_langs=selected_langs)
                transformed_items.append(item)

            final_result = {
                "tags": TAXONOMY_TREE,
                "items": transformed_items
            }

            # Cache parsed items for subsequent verification
            save_parsed_export_cache(final_result)

            send_event({
                "type": "complete",
                "total": total,
                "data": final_result
            })
            self.close_connection = True
        except Exception as e:
            try:
                send_event({
                    "type": "error",
                    "error": str(e)
                })
            except Exception:
                pass
            self.close_connection = True
        finally:
            coordinator.set_ready("content_agent")
            coordinator.set_ready("taxonomy_agent")

    def handle_api_parse(self, params):
        count = int(params.get("count", [5])[0])
        identifier = params.get("identifier", [None])[0]
        from_n = params.get("from", [None])[0]
        to_n = params.get("to", [None])[0]
        langs_param = params.get("langs", ["nl,en"])[0]
        selected_langs = [l.strip().lower() for l in langs_param.split(",") if l.strip()]

        coordinator.set_busy("content_agent", f"Parsing {count} posts")
        coordinator.set_busy("taxonomy_agent", "Applying taxonomy rules")
        try:
            if identifier:
                clean_ident = identifier.strip()
                # If a full URL is passed, extract the slug or ID from URL path
                if clean_ident.startswith("http://") or clean_ident.startswith("https://"):
                    p_path = urllib.parse.urlparse(clean_ident).path
                    parts = [p for p in p_path.split("/") if p]
                    if parts:
                        clean_ident = parts[-1]

                if clean_ident.isdigit():
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts/{clean_ident}?_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = [json.loads(r.read().decode("utf-8"))]
                else:
                    url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts?slug={urllib.parse.quote(clean_ident)}&_embed=1"
                    req = urllib.request.Request(url, headers={"User-Agent": "MigrationBot/2.0"})
                    with urllib.request.urlopen(req, timeout=10) as r:
                        raw_posts = json.loads(r.read().decode("utf-8"))
                        if not raw_posts:
                            raise ValueError(f"No article found for slug or URL '{clean_ident}'")
            elif from_n is not None and to_n is not None:
                start_n = max(1, int(from_n))
                end_n = max(start_n, int(to_n))
                total_to_fetch = end_n - start_n + 1
                offset = start_n - 1
                raw_posts = self._fetch_posts_in_batches(total_to_fetch, offset=offset)
            else:
                raw_posts = self._fetch_posts_in_batches(count, offset=0)

            result = build_mach3blocks_json(raw_posts, selected_langs=selected_langs)
            response_data = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(response_data)
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
        finally:
            coordinator.set_ready("content_agent")
            coordinator.set_ready("taxonomy_agent")

    def handle_api_verify_cache(self):
        """Return information about the cached parsed export."""
        cache = load_parsed_export_cache()
        if cache and "items" in cache:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "cached": True,
                "items_count": len(cache["items"]),
                "sample_titles": [it.get("name", {}).get("nl", "") for it in cache["items"][:5]]
            }, ensure_ascii=False).encode("utf-8"))
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({
                "status": "ok",
                "cached": False,
                "items_count": 0
            }, ensure_ascii=False).encode("utf-8"))

    def handle_api_verify_target_urls(self, params):
        """Fetch list of target articles available on Mach3Blocks archive pages."""
        base_url = params.get("target_url", ["https://test13242.mach3blocks.io"])[0]
        max_pages = int(params.get("max_pages", [5])[0])
        try:
            articles = discover_target_articles(base_url=base_url, max_pages=max_pages)
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "count": len(articles), "articles": articles}, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_api_verify_single(self):
        """Verify a single article given source_url/slug and target_url."""
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length).decode("utf-8")
        try:
            data = json.loads(post_data)
            source_slug = data.get("source_slug", "")
            target_url = data.get("target_url", "")
            lang = data.get("lang", "nl")

            if not source_slug or not target_url:
                raise ValueError("Both 'source_slug' and 'target_url' are required.")

            # Fetch source WP post
            wp_api_url = f"https://anthuriuminfo.com/wp-json/wp/v2/posts?slug={urllib.parse.quote(source_slug)}&_embed=1"
            req = urllib.request.Request(wp_api_url, headers={"User-Agent": "MigrationVerifier/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                wp_posts = json.loads(r.read().decode("utf-8"))
                if not wp_posts:
                    raise ValueError(f"Source post '{source_slug}' not found.")
                source_post = wp_posts[0]

            # Fetch target HTML
            req_t = urllib.request.Request(target_url, headers={"User-Agent": "MigrationVerifier/1.0"})
            with urllib.request.urlopen(req_t, timeout=10) as r_t:
                target_html = r_t.read().decode("utf-8", errors="ignore")
            target_parsed = parse_target_page(target_html, target_url=target_url)

            comparison = compare_article(source_post, target_parsed, lang=lang)

            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(comparison, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))

    def handle_api_verify_stream(self, params):
        """
        Stream verification process events via Server-Sent Events (SSE).
        Supports:
        - target_url: archive base or single article URL
        - mode: 'all' (all target articles), 'range' (from N to N), 'single' (one specific URL/slug)
        - from, to: range bounds
        - slug / identifier: single article check
        - max_pages: number of archive pages to crawl
        - only_embeds: filter articles with social embeds
        - limit: max articles
        - keep-alive SSE pings
        """
        target_base = params.get("target_url", ["https://test13242.mach3blocks.io"])[0].rstrip("/")
        max_target_pages = int(params.get("max_pages", [5])[0])
        only_embeds = params.get("only_embeds", ["0"])[0] in ["1", "true", "yes"]
        limit = int(params.get("limit", [50])[0])
        mode = params.get("mode", ["recent"])[0]
        from_n = params.get("from", [None])[0]
        to_n = params.get("to", [None])[0]
        identifier = params.get("identifier", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-transform, no-store")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data_dict):
            payload = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(payload)
            self.wfile.flush()

        def send_ping():
            try:
                self.wfile.write(b": ping\n\n")
                self.wfile.flush()
            except Exception:
                pass

        coordinator.set_busy("content_agent", "Verifying content against target site")

        try:
            target_articles = []

            # Handle Single Mode
            if mode == "single" and identifier:
                clean_ident = identifier.strip()
                # If full target URL passed
                if clean_ident.startswith("http://") or clean_ident.startswith("https://"):
                    p_path = urllib.parse.urlparse(clean_ident).path
                    # Extract slug without trailing slash
                    parts = [p for p in p_path.split("/") if p]
                    full_target_url = clean_ident if clean_ident.endswith("/") else clean_ident + "/"
                    slug_part = parts[-1] if parts else clean_ident
                    if "~" in slug_part:
                        base_slug, nano_id = slug_part.split("~", 1)
                    else:
                        base_slug, nano_id = slug_part, ""
                    target_articles = [{
                        "url": full_target_url,
                        "slug": base_slug,
                        "nano_id": nano_id,
                        "path": p_path
                    }]
                else:
                    # Clean slug
                    base_slug = clean_ident.split("~")[0]
                    target_articles = [{
                        "url": f"{target_base}/nl/blog/{clean_ident}/",
                        "slug": base_slug,
                        "nano_id": "",
                        "path": f"/nl/blog/{clean_ident}/"
                    }]

                send_event({
                    "type": "status",
                    "phase": "target_found",
                    "total_target": 1,
                    "message": f"Single article verification targeted: {target_articles[0]['slug']}"
                })
            else:
                send_event({
                    "type": "status",
                    "phase": "crawling_target",
                    "message": f"Crawling published articles from {target_base}..."
                })

                send_ping()
                def crawl_progress(cur_page, total_found):
                    send_ping()
                    send_event({
                        "type": "status",
                        "phase": "crawling_target",
                        "message": f"Crawling page {cur_page}... Discovered {total_found} articles so far."
                    })

                crawled = discover_target_articles(
                    base_url=target_base,
                    archive_path="/nl/tips-advies/",
                    max_pages=max_target_pages,
                    progress_callback=crawl_progress
                )

                if mode == "range" and from_n is not None and to_n is not None:
                    start_idx = max(0, int(from_n) - 1)
                    end_idx = min(len(crawled), int(to_n))
                    target_articles = crawled[start_idx:end_idx]
                elif limit <= 0:
                    target_articles = crawled
                else:
                    target_articles = crawled[:limit]

                send_event({
                    "type": "status",
                    "phase": "target_found",
                    "total_target": len(target_articles),
                    "message": f"Discovered {len(crawled)} target articles. Selected {len(target_articles)} for verification."
                })

            if not target_articles:
                send_event({
                    "type": "complete",
                    "total": 0,
                    "passed": 0,
                    "warnings": 0,
                    "failed": 0,
                    "missing": 0,
                    "items": [],
                    "message": "No published articles found matching the criteria."
                })
                return

            articles_to_verify = target_articles
            passed_count = 0
            warn_count = 0
            failed_count = 0
            missing_embeds_count = 0
            verified_results = []

            # Check if local parsed export cache is available
            cached_export = load_parsed_export_cache()
            cached_items = cached_export.get("items", []) if cached_export else []
            if cached_items:
                send_event({
                    "type": "status",
                    "phase": "cache_loaded",
                    "message": f"Loaded {len(cached_items)} locally parsed articles from cache for fast verification."
                })

            for idx, target_item in enumerate(articles_to_verify):
                t_url = target_item["url"]
                t_slug = target_item["slug"]

                send_ping()
                send_event({
                    "type": "progress",
                    "current": idx + 1,
                    "total": len(articles_to_verify),
                    "slug": t_slug,
                    "title": t_slug,
                    "percent": round(((idx + 1) / len(articles_to_verify)) * 100),
                    "message": f"Verifying [{idx + 1}/{len(articles_to_verify)}]: {t_slug}"
                })

                # Fetch Target HTML
                target_parsed = None
                try:
                    req_t = urllib.request.Request(t_url, headers={"User-Agent": "MigrationVerifier/1.0"})
                    with urllib.request.urlopen(req_t, timeout=10) as r_t:
                        t_html = r_t.read().decode("utf-8", errors="ignore")
                    target_parsed = parse_target_page(t_html, target_url=t_url)
                except Exception as ex:
                    send_event({
                        "type": "item_error",
                        "slug": t_slug,
                        "url": t_url,
                        "error": f"Failed to fetch target page: {str(ex)}"
                    })
                    failed_count += 1
                    continue

                send_ping()
                # 1. Try matching against locally cached parsed export items first
                source_post = None
                if cached_items:
                    source_post = match_cached_item(
                        target_slug=t_slug,
                        target_title=target_parsed.get("title", ""),
                        cached_items=cached_items,
                        lang="nl"
                    )

                # 2. If not in cache or no cache, fallback to live WP API match
                if not source_post:
                    source_post = match_source_post(
                        target_slug=t_slug,
                        target_title=target_parsed.get("title", ""),
                        wp_api_base="https://anthuriuminfo.com"
                    )

                if not source_post:
                    item_res = {
                        "status": "MISSING_SOURCE",
                        "slug": t_slug,
                        "source_url": None,
                        "target_url": t_url,
                        "title": {"expected": "", "actual": target_parsed.get("title", ""), "similarity": 0.0, "status": "UNKNOWN"},
                        "intro": {"expected": "", "actual": target_parsed.get("intro_text", ""), "similarity": 0.0, "status": "UNKNOWN"},
                        "text_1": {"expected": "", "actual": target_parsed.get("text_1", ""), "similarity": 0.0, "status": "UNKNOWN"},
                        "text_2": {"expected": "", "actual": target_parsed.get("text_2", ""), "similarity": 0.0, "status": "UNKNOWN"},
                        "embeds": {
                            "expected": "",
                            "expected_type": None,
                            "found_urls": target_parsed.get("boxes_with_data_url", []),
                            "status": "EXTRA" if target_parsed.get("boxes_with_data_url") else "NONE"
                        }
                    }
                    warn_count += 1
                else:
                    item_res = compare_article(source_post, target_parsed, lang="nl")
                    if only_embeds and not item_res["embeds"].get("expected_type"):
                        continue

                    if item_res["status"] == "PASSED":
                        passed_count += 1
                    elif item_res["status"] == "WARNING":
                        warn_count += 1
                    else:
                        failed_count += 1

                    if item_res["embeds"]["status"] == "MISSING":
                        missing_embeds_count += 1

                verified_results.append(item_res)
                send_event({
                    "type": "item_verified",
                    "item": item_res
                })

            send_event({
                "type": "complete",
                "total": len(verified_results),
                "passed": passed_count,
                "warnings": warn_count,
                "failed": failed_count,
                "missing_embeds": missing_embeds_count,
                "message": f"Verification completed! {passed_count} passed, {warn_count} warnings, {failed_count} failed."
            })
        except Exception as e:
            send_event({"type": "error", "message": str(e)})
        finally:
            coordinator.set_ready("content_agent")

def run(port=PORT):
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(("", port), MigrationHandler) as httpd:
        print(f"Migration Studio Admin running at http://localhost:{port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server.")

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    run(port)
