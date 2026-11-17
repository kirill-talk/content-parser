# Anthuriuminfo to Mach3Blocks Migration Studio

High-performance migration studio and parser designed to transfer articles from WordPress (`https://anthuriuminfo.com/blog/`) to the **Mach3Blocks** CMS schema.

---

## Key Features

1. **Intelligent Content Splitting**:
   - Automatically decomposes monolithic WordPress content (`.main-content > .content-left`) into structured layout slots (`item-intro-text`, `text-1`, `media-2`, `media-2-text`, `text-2`, `instagram`, `media-3`, `media-3-text`, `text-3`).
   - Cleans duplicate `<h2>` titles from the beginning of articles.
   - Converts headings to standard `<h3 class="heading-3 dark">` elements.
   - Cleans thumbnail dimension suffixes (e.g., `-1067x1600.jpg`) to output full-resolution original image assets.

2. **Flexible Multilingual Synchronization**:
   - Supports any combination of languages: **NL (Dutch - Primary)**, **EN (English)**, **DE (German)**, and **FR (French)**.
   - Automatic translation pairing by publication date window and media filename matching.
   - **Analyze tool**: fast pre-flight check of translation readiness across selected ranges.

3. **Taxonomy & Filter Mapping**:
   - Interactive table mapping all 212 WordPress tags to Mach3Blocks taxonomy tree IDs (`Verzorging`, `Inspiratie`, `DIY`, etc.).
   - Visual user overrides saved to `custom_tag_mapping.json`.
   - Generates clean HTML tag lists: `<ul><li>...</li></ul>`.

4. **Production Architecture**:
   - Zero external Python dependencies (pure Python standard library).
   - Dockerized with Traefik reverse proxy integration.
   - Live URL: [https://content-parser.kidev.uk/](https://content-parser.kidev.uk/)
   - Fully responsive UI styled in dark Mach3Blocks theme with mobile drawer menu support.

---

## Project Structure

```
content-parser/
├── core/                     # Core migration engines
├── sources/                  # Source connectors & API detectors
│   ├── base.py               # Abstract BaseSource adapter
│   ├── wordpress.py          # WordPress REST API connector
│   └── detector.py           # Automatic JSON/REST API capability detector
├── rules/                    # Declarative field extraction & transformation schemas
│   └── schema.py             # ParsingRule and SiteParsingSchema
├── profiles/                 # Per-site configuration profiles
│   └── manager.py            # Profile manager (domain, tag mapping, target collections)
├── agents.py                 # Worker agents coordinator
├── agents.md                 # Agent architecture and project context documentation
├── compose.yaml              # Docker compose with Traefik routing
├── custom_tag_mapping.json   # Persistent user tag mapping overrides
├── Dockerfile                # Lightweight Python 3.12-alpine container
├── multi_lang.py             # Language matcher and pre-flight analysis
├── parser_core.py            # WordPress API fetcher and Mach3Blocks JSON builder
├── README.md                 # Project documentation
├── server.py                 # HTTP server with REST endpoints
├── splitter.py               # Content block partitioning and HTML cleaner
├── static/
│   └── index.html            # Studio Web UI (Responsive, Dark Theme)
├── tag_mapper.py             # Taxonomy tree and tag mapping logic
└── wp_tags_cache.json        # Pre-cached WordPress tags
```

---

## Local Development & Docker Run

### Running locally:
```bash
python3 server.py 8081
# Access at http://localhost:8081
```

### Running with Docker:
```bash
docker compose up -d --build
# Access at https://content-parser.kidev.uk/ or http://localhost:8081
```

---

## Endpoints

- `GET /api/status`: Service health check and current stage.
- `GET /api/analyze?langs=nl,en&count=5`: Quick scan of translation availability.
- `GET /api/parse?langs=nl,en&count=5`: Full parse and Mach3Blocks JSON generation.
- `GET /api/tags/mapping`: List all WordPress tags and current mapping status.
- `POST /api/tags/mapping`: Save custom tag mapping overrides.
