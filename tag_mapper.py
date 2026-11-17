"""
Complete Tag Mapping Rules for Mach3Blocks Migration.
Supports loading and saving custom user overrides from custom_tag_mapping.json.
"""

import os
import json

TAXONOMY_TREE = [
    {
        "id": 0,
        "name": "",
        "slug": "",
        "hidden": False,
        "tags": [
            {"id": 451897, "name": {"nl": "verzorging", "en": "verzorging"}, "slug": {"nl": "verzorging", "en": "verzorging"}, "hidden": False},
            {"id": 451898, "name": {"nl": "inspiratie", "en": "inspiratie"}, "slug": {"nl": "inspiratie", "en": "inspiratie"}, "hidden": False},
            {"id": 451899, "name": {"nl": "feitjes & weetjes", "en": "feitjes & weetjes"}, "slug": {"nl": "feitjes-weetjes", "en": "feitjes-weetjes"}, "hidden": False},
            {"id": 451900, "name": {"nl": "do it yourself", "en": "do it yourself"}, "slug": {"nl": "do-it-yourself", "en": "do-it-yourself"}, "hidden": False},
            {"id": 451901, "name": {"nl": "potanthurium", "en": "potanthurium"}, "slug": {"nl": "potanthurium", "en": "potanthurium"}, "hidden": False},
            {"id": 451902, "name": {"nl": "snijanthurium", "en": "snijanthurium"}, "slug": {"nl": "snijanthurium", "en": "snijanthurium"}, "hidden": False},
            {"id": 452681, "name": {"nl": "most read", "en": "most read"}, "slug": {"nl": "most-read", "en": "most-read"}, "hidden": True}
        ]
    },
    {
        "id": 57156,
        "name": {"nl": "verzorging", "en": "verzorging"},
        "slug": {"nl": "verzorging", "en": "verzorging"},
        "hidden": False,
        "tags": [
            {"id": 451887, "name": {"nl": "water geven", "en": "water geven"}, "slug": {"nl": "water-geven", "en": "water-geven"}, "hidden": False},
            {"id": 451888, "name": {"nl": "gele bladeren", "en": "gele bladeren"}, "slug": {"nl": "gele-bladeren", "en": "gele-bladeren"}, "hidden": False},
            {"id": 451889, "name": {"nl": "standplaats", "en": "standplaats"}, "slug": {"nl": "standplaats", "en": "standplaats"}, "hidden": False},
            {"id": 451890, "name": {"nl": "voeding", "en": "voeding"}, "slug": {"nl": "voeding", "en": "voeding"}, "hidden": False},
            {"id": 451891, "name": {"nl": "verpotten", "en": "verpotten"}, "slug": {"nl": "verpotten", "en": "verpotten"}, "hidden": False},
            {"id": 451892, "name": {"nl": "snijanthurium", "en": "snijanthurium"}, "slug": {"nl": "snijanthurium", "en": "snijanthurium"}, "hidden": False},
            {"id": 451893, "name": {"nl": "potanthurium", "en": "potanthurium"}, "slug": {"nl": "potanthurium", "en": "potanthurium"}, "hidden": False}
        ]
    },
    {
        "id": 57157,
        "name": {"nl": "inspiratie", "en": "inspiratie"},
        "slug": {"nl": "inspiratie", "en": "inspiratie"},
        "hidden": False,
        "tags": [
            {"id": 451879, "name": {"nl": "interieur", "en": "interieur"}, "slug": {"nl": "interieur", "en": "interieur"}, "hidden": False},
            {"id": 451880, "name": {"nl": "styling", "en": "styling"}, "slug": {"nl": "styling", "en": "styling"}, "hidden": False},
            {"id": 451881, "name": {"nl": "seizoenen", "en": "seizoenen"}, "slug": {"nl": "seizoenen", "en": "seizoenen"}, "hidden": False},
            {"id": 451882, "name": {"nl": "feestdagen", "en": "feestdagen"}, "slug": {"nl": "feestdagen", "en": "feestdagen"}, "hidden": False},
            {"id": 451883, "name": {"nl": "cadeau", "en": "cadeau"}, "slug": {"nl": "cadeau", "en": "cadeau"}, "hidden": False},
            {"id": 451884, "name": {"nl": "trends", "en": "trends"}, "slug": {"nl": "trends", "en": "trends"}, "hidden": False},
            {"id": 451885, "name": {"nl": "potanthurium", "en": "potanthurium"}, "slug": {"nl": "potanthurium", "en": "potanthurium"}, "hidden": False},
            {"id": 451886, "name": {"nl": "snijanthurium", "en": "snijanthurium"}, "slug": {"nl": "snijanthurium", "en": "snijanthurium"}, "hidden": False}
        ]
    }
]

# Baseline Tag mapping from old site terms to Mach3Blocks tag IDs
DEFAULT_TAG_MAPPING = {
    # Verzorging (57156 & 0)
    "verzorging": [451897],
    "verzorgingstips": [451897],
    "water": [451887, 451897],
    "water geven": [451887, 451897],
    "water-geven": [451887, 451897],
    "gieters": [451887, 451897],
    "gele bladeren": [451888, 451897],
    "gele-bladeren": [451888, 451897],
    "bruine bladeren": [451888, 451897],
    "bruine-bladeren": [451888, 451897],
    "standplaats": [451889, 451897],
    "licht": [451889, 451897],
    "voeding": [451890, 451897],
    "verpotten": [451891, 451897],
    "potgrond": [451891, 451897],
    "snoeien": [451897],
    "stekken": [451897],
    "weinig onderhoud": [451897],
    "luchtzuiverend": [451897, 451899],

    # Inspiratie (57157 & 0)
    "inspiratie": [451898],
    "interieur": [451879, 451898],
    "woonkamer": [451879, 451898],
    "badkamer": [451879, 451898],
    "slaapkamer": [451879, 451898],
    "keuken": [451879, 451898],
    "kantoor": [451879, 451898],
    "hal": [451879, 451898],
    "terras": [451879, 451898],
    "balkon": [451879, 451898],
    "tuin": [451879, 451898],
    "urban jungle": [451879, 451898],
    "jungle": [451879, 451898],
    "scandinavisch": [451879, 451898],
    "japandi": [451879, 451898],
    "bohemian": [451879, 451898],
    "industrieel chique": [451879, 451898],

    # Styling
    "styling": [451880, 451898],
    "bloemstyling": [451880, 451898],
    "tafelstyling": [451880, 451898],
    "tafeldecoratie": [451880, 451898],
    "bloemschikken": [451880, 451898],
    "bloemist": [451880, 451898],
    "bloemstylist": [451880, 451898],
    "boeket": [451880, 451898],
    "decoratie": [451880, 451898],
    "stijlvol": [451880, 451898],
    "vaas": [451880, 451898],
    "vazen": [451880, 451898],

    # Seizoenen (451881)
    "seizoenen": [451881, 451898],
    "zomer": [451881, 451898],
    "herfst": [451881, 451898],
    "winter": [451881, 451898],
    "lente": [451881, 451898],
    "voorjaar": [451881, 451898],
    "januari": [451881, 451898],
    "december": [451881, 451898],
    "vakantie": [451881, 451898],

    # Feestdagen (451882)
    "feestdagen": [451882, 451898],
    "kerst": [451882, 451898],
    "kerstmarkt": [451882, 451898],
    "pasen": [451882, 451898],
    "paasviering": [451882, 451898],
    "valentijn": [451882, 451898],
    "moederdag": [451882, 451898],
    "vaderdag": [451882, 451898],
    "vrouwendag": [451882, 451898],
    "bruiloft": [451882, 451898],
    "feest": [451882, 451898],
    "feestelijk": [451882, 451898],

    # Cadeau (451883)
    "cadeau": [451883, 451898],
    "cadeautip": [451883, 451898],
    "cadeautips": [451883, 451898],
    "cadeauidee": [451883, 451898],
    "cadeaus": [451883, 451898],
    "inpakken": [451883, 451898],

    # Trends (451884)
    "trends": [451884, 451898],
    "trend": [451884, 451898],
    "stijltrends": [451884, 451898],
    "trendkleur": [451884, 451898],
    "trend collectie": [451884, 451898],
    "fashion": [451884, 451898],
    "mode": [451884, 451898],
    "kleur": [451884, 451898],
    "kleuren": [451884, 451898],
    "kleurrijk": [451884, 451898],
    "design": [451884, 451898],
    "2027": [451884, 451898],
    "2026": [451884, 451898],
    "2025": [451884, 451898],
    "2024": [451884, 451898],
    "2023": [451884, 451898],

    # Types: Potanthurium & Snijanthurium
    "potanthurium": [451901, 451893, 451885],
    "potanthuriums": [451901, 451893, 451885],
    "potplant": [451901, 451893, 451885],
    "potplanten": [451901, 451893, 451885],
    "kamerplant": [451901, 451893, 451885],
    "planten": [451901, 451893, 451885],
    "plant": [451901, 451893, 451885],
    "snijanthurium": [451902, 451892, 451886],
    "snijanthuriums": [451902, 451892, 451886],
    "snijbloem": [451902, 451892, 451886],
    "snijbloemen": [451902, 451892, 451886],
    "bloemen": [451902, 451892, 451886],

    # DIY (451900)
    "diy": [451900],
    "do it yourself": [451900],
    "arrangementen": [451900],
    "workshop": [451900],
    "plantenhanger": [451900],

    # Feitjes & weetjes (451899)
    "feitjes & weetjes": [451899],
    "feitjes": [451899],
    "weetjes": [451899],
    "feiten": [451899],
    "informatie": [451899],
    "over anthurium": [451899],

    # Most read (452681)
    "best gelezen": [452681],
    "most read": [452681],
}

CUSTOM_MAPPING_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_tag_mapping.json")

def load_effective_mapping() -> dict:
    """Load default mapping combined with user overrides from custom_tag_mapping.json."""
    mapping = dict(DEFAULT_TAG_MAPPING)
    if os.path.exists(CUSTOM_MAPPING_FILE):
        try:
            with open(CUSTOM_MAPPING_FILE, "r", encoding="utf-8") as f:
                custom = json.load(f)
                mapping.update(custom)
        except Exception:
            pass
    return mapping

def save_custom_mapping(custom_overrides: dict) -> bool:
    """Save user tag mapping overrides."""
    try:
        with open(CUSTOM_MAPPING_FILE, "w", encoding="utf-8") as f:
            json.dump(custom_overrides, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False

# Mapping of WordPress Category IDs
CATEGORY_MAPPING = {
    4: [451898], # Inspiratie
    9: [451897], # Verzorgingstips
    6: [451899], # Over anthurium
    2: [451898], # Agenda -> Inspiratie
    3: [451898], # Meet our bloggers -> Inspiratie
}

def format_tags_html(tag_names: list[str]) -> str:
    """Format list of tag names into Mach3Blocks HTML format: <ul>\r\n<li>...</li>\r\n</ul>"""
    if not tag_names:
        return "<ul>\r\n</ul>"
    items = "\r\n".join(f"<li>{tag.strip()}</li>" for tag in tag_names if tag.strip())
    return f"<ul>\r\n{items}\r\n</ul>"

def map_tags_to_ids(tag_names: list[str], category_names: list[str] = None, category_ids: list[int] = None) -> list[int]:
    """Map human-readable tags and categories from WordPress to target Mach3Blocks IDs."""
    effective_mapping = load_effective_mapping()
    matched_ids = set()
    
    # 1. Map WordPress Categories
    if category_ids:
        for cid in category_ids:
            if cid in CATEGORY_MAPPING:
                matched_ids.update(CATEGORY_MAPPING[cid])
                
    if category_names:
        for cname in category_names:
            c_clean = cname.lower().strip()
            if c_clean in effective_mapping:
                matched_ids.update(effective_mapping[c_clean])

    # 2. Map WordPress Tags
    for tag in tag_names:
        tag_clean = tag.lower().strip()
        if tag_clean in effective_mapping:
            matched_ids.update(effective_mapping[tag_clean])
        else:
            for key, mapped_list in effective_mapping.items():
                if key in tag_clean or tag_clean in key:
                    matched_ids.update(mapped_list)
                    break

    # 3. Fallback
    has_root = any(rid in matched_ids for rid in [451897, 451898, 451899, 451900, 451901, 451902])
    if not has_root:
        matched_ids.add(451898) # Default: Inspiratie

    return sorted(list(matched_ids))
