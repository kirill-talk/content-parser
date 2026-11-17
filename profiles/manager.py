"""
Site Profile Manager.
Allows saving, loading and managing per-source profiles (site domain, tag mapping file, parsing rules).
"""

import os
import json
from typing import Dict, Any, Optional

PROFILES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "profiles")

DEFAULT_PROFILES = {
    "anthuriuminfo": {
        "id": "anthuriuminfo",
        "name": "Anthurium Info Blog",
        "base_url": "https://anthuriuminfo.com",
        "engine": "wordpress_rest",
        "languages": ["nl", "en", "de", "fr"],
        "tag_mapping_file": "custom_tag_mapping.json",
        "splitter_type": "anthurium_3column",
        "target_collection": "blog"
    }
}

def get_profile(profile_id: str = "anthuriuminfo") -> Dict[str, Any]:
    """Retrieve profile by ID, checking profiles directory or falling back to defaults."""
    file_path = os.path.join(PROFILES_DIR, f"{profile_id}.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return DEFAULT_PROFILES.get(profile_id, DEFAULT_PROFILES["anthuriuminfo"])

def list_profiles() -> list[Dict[str, Any]]:
    """List all available site profiles."""
    profiles = list(DEFAULT_PROFILES.values())
    if os.path.exists(PROFILES_DIR):
        for fname in os.listdir(PROFILES_DIR):
            if fname.endswith(".json") and fname != "anthuriuminfo.json":
                try:
                    with open(os.path.join(PROFILES_DIR, fname), "r", encoding="utf-8") as f:
                        profiles.append(json.load(f))
                except Exception:
                    pass
    return profiles

def save_profile(profile_data: Dict[str, Any]) -> str:
    """Save or update a site profile."""
    pid = profile_data.get("id") or profile_data.get("name", "custom").lower().replace(" ", "_")
    profile_data["id"] = pid
    os.makedirs(PROFILES_DIR, exist_ok=True)
    file_path = os.path.join(PROFILES_DIR, f"{pid}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(profile_data, f, indent=2, ensure_ascii=False)
    return pid
