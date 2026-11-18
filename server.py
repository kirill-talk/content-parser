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
        elif path == "/api/analyze/stream":
            self.handle_api_analyze_stream(params)
        elif path == "/api/parse":
            self.handle_api_parse(params)
        elif path == "/api/analyze":
            self.handle_api_analyze(params)
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
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data_dict):
            payload = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(payload)
            self.wfile.flush()

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

                for lang in ["en", "de", "fr"]:
                    if lang in selected_langs:
                        match = find_language_post(p, lang)
                        item_status["languages"][lang] = (match is not None)
                        if match:
                            item_status[f"{lang}_title"] = match.get("title", {}).get("rendered", "")
                    else:
                        item_status["languages"][lang] = False

                analysis_result.append(item_status)

            send_event({
                "type": "complete",
                "total": total,
                "data": analysis_result
            })
        except Exception as e:
            try:
                send_event({
                    "type": "error",
                    "error": str(e)
                })
            except Exception:
                pass
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
        self.send_header("Cache-Control", "no-cache, no-transform")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        def send_event(data_dict):
            payload = f"data: {json.dumps(data_dict, ensure_ascii=False)}\n\n".encode("utf-8")
            self.wfile.write(payload)
            self.wfile.flush()

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

                item = transform_post(post, selected_langs=selected_langs)
                transformed_items.append(item)

            final_result = {
                "tags": TAXONOMY_TREE,
                "items": transformed_items
            }

            send_event({
                "type": "complete",
                "total": total,
                "data": final_result
            })
        except Exception as e:
            try:
                send_event({
                    "type": "error",
                    "error": str(e)
                })
            except Exception:
                pass
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
