"""
WordPress REST API adapter implementing BaseSource.
Supports discovery of JSON endpoints via HTTP Link header and /wp-json/ index.
"""

import urllib.request
import urllib.parse
import json
import re
from typing import List, Dict, Any, Optional
from sources.base import BaseSource

class WordPressSource(BaseSource):
    def __init__(self, base_url: str = "https://anthuriuminfo.com", config: Optional[Dict[str, Any]] = None):
        super().__init__(base_url, config)
        self.api_root = None

    def detect_capabilities(self) -> Dict[str, Any]:
        """
        Inspect target site to detect WordPress REST API / JSON export capabilities.
        Checks:
        1. HTTP Link header: <.../wp-json/>; rel="https://api.w.org/"
        2. Direct /wp-json/ endpoint and routes (/wp/v2/posts)
        3. Total posts count via X-WP-Total header
        """
        result = {
            "source_url": self.base_url,
            "has_json_api": False,
            "api_type": "unknown",
            "api_endpoint": None,
            "supports_json_export": False,
            "namespaces": [],
            "total_posts": 0,
            "detected_features": []
        }

        # 1. Probe base URL for Link header or HTML discovery
        api_root_candidate = None
        try:
            req = urllib.request.Request(
                self.base_url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                link_header = resp.headers.get("Link", "")
                if 'rel="https://api.w.org/"' in link_header or "rel='https://api.w.org/'" in link_header:
                    match = re.search(r'<([^>]+)>;\s*rel=["\']https://api\.w\.org/["\']', link_header)
                    if match:
                        api_root_candidate = match.group(1).rstrip('/')
                        result["detected_features"].append("HTTP Link header discovery")
                
                # Check HTML link tag if header is missing
                if not api_root_candidate:
                    html_content = resp.read(16384).decode("utf-8", errors="ignore")
                    match = re.search(r'<link\s+[^>]*rel=["\']https://api\.w\.org/["\'][^>]*href=["\']([^"\']+)["\']', html_content, re.IGNORECASE)
                    if match:
                        api_root_candidate = match.group(1).rstrip('/')
                        result["detected_features"].append("HTML <link rel='https://api.w.org/'> discovery")
        except Exception as e:
            pass

        # Fallback to standard /wp-json/
        if not api_root_candidate:
            api_root_candidate = f"{self.base_url}/wp-json"

        # 2. Check the JSON root index
        try:
            req = urllib.request.Request(
                api_root_candidate,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
                routes = data.get("routes", {})
                namespaces = data.get("namespaces", [])
                
                has_posts = "/wp/v2/posts" in routes
                result["has_json_api"] = True
                result["api_type"] = "wordpress_rest"
                result["api_endpoint"] = api_root_candidate
                result["namespaces"] = namespaces
                result["supports_json_export"] = has_posts
                self.api_root = api_root_candidate
                result["detected_features"].append("WordPress REST API /wp-json/ verified")
        except Exception:
            # Not a WordPress REST API or protected
            return result

        # 3. Query total count from /wp/v2/posts
        if result["supports_json_export"]:
            try:
                posts_probe_url = f"{self.api_root}/wp/v2/posts?per_page=1"
                req = urllib.request.Request(
                    posts_probe_url,
                    headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    total_str = resp.headers.get("X-WP-Total", "0")
                    result["total_posts"] = int(total_str)
                    result["detected_features"].append(f"X-WP-Total header: {result['total_posts']} items available for JSON export")
            except Exception:
                pass

        return result

    def fetch_items(self, count: int = 5, offset: int = 0) -> List[Dict[str, Any]]:
        api_root = self.api_root or f"{self.base_url}/wp-json"
        api_url = f"{api_root}/wp/v2/posts?per_page={count}&offset={offset}&_embed=1"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))

    def fetch_tags(self) -> List[Dict[str, Any]]:
        api_root = self.api_root or f"{self.base_url}/wp-json"
        api_url = f"{api_root}/wp/v2/tags?per_page=100"
        req = urllib.request.Request(api_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
