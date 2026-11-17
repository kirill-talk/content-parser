"""
Detector and factory for data sources.
"""

from typing import Dict, Any, Optional
from sources.wordpress import WordPressSource

def detect_source(url: str) -> Dict[str, Any]:
    """
    Probe any URL to detect its CMS engine and JSON export availability.
    Currently tests WordPress REST API, can be extended with Shopify, Strapi, Webflow, RSS, etc.
    """
    wp = WordPressSource(url)
    caps = wp.detect_capabilities()
    if caps.get("has_json_api"):
        return caps
    
    return {
        "source_url": url,
        "has_json_api": False,
        "api_type": "generic_html",
        "api_endpoint": None,
        "supports_json_export": False,
        "total_posts": 0,
        "detected_features": ["No standard JSON REST API detected; requires HTML selector rules"]
    }
