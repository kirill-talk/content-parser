# Universal Content Migration Platform (JSON Export)

A high-performance, modular content migration platform designed to extract, transform, and normalize web content from diverse source platforms into clean, structured JSON schemas.

---

## Key Features

1. **Intelligent Content Normalization & Structural Splitting**:
   - Parses unstructured content streams into semantic layout slots (introductory summaries, primary body blocks, visual media with captions, and supplemental text blocks).
   - Removes redundant in-content title tags that duplicate the article headline.
   - Normalizes heading hierarchies to unified design system specifications.
   - Strips image downscaling and dimension artifacts to ensure media assets are exported at full original resolution.

2. **Automated Source API Discovery & Pre-flight Analysis**:
   - Probes target sources for active REST endpoints, data feeds, and export capabilities.
   - Provides an **Analyze** matrix allowing users to inspect items, availability of language translations, and export readiness before running migrations.

3. **Multi-Language Synchronization**:
   - Supports flexible multi-language pairings across arbitrary locales.
   - Correlates multilingual counterparts via publication metadata and media asset fingerprints.
   - Emits unified multilingual field objects structured per locale.

4. **Interactive Taxonomy & Filter Mapping**:
   - Maps source tags and categories into target taxonomy structures and numeric filter IDs.
   - Web UI table allows real-time searching, inspection, and manual override of any tag mapping.
   - Persistent configuration file preserves custom mappings across export sessions.

5. **Universal & Extensible Architecture**:
   - **Pluggable Source Adapters (`sources/`)**: Standardized interface for adding new CMS, API, or feed connectors.
   - **Declarative Rule Builder Foundation (`rules/`)**: Configurable field-level mapping rules (path extraction, CSS selectors, regular expressions, and transformations).
   - **Per-Source Profiles (`profiles/`)**: Individualized configurations per domain (locales, taxonomy trees, extraction schemas).
   - **Zero External Python Dependencies**: Built entirely on standard Python libraries.
   - **Container Ready**: Packaged with Docker and reverse-proxy routing configurations.

---

## Project Structure

```
content-parser/
├── sources/                  # Source connectors & API discovery engines
│   ├── base.py               # Abstract BaseSource adapter interface
│   ├── detector.py           # Universal REST/JSON capability detector
│   └── wordpress.py          # REST API source adapter
├── rules/                    # Declarative field extraction & transformation schemas
│   └── schema.py             # ParsingRule and SiteParsingSchema definitions
├── profiles/                 # Per-source configuration profiles
│   └── manager.py            # Profile manager (domain, mapping, target collections)
├── agents.py                 # Multi-worker migration agents coordinator
├── agents.md                 # Agent architecture and execution flow documentation
├── compose.yaml              # Docker compose container setup
├── multi_lang.py             # Multilingual correlation and pairing engine
├── parser_core.py            # Core extraction and target JSON schema builder
├── README.md                 # Platform documentation
├── server.py                 # Lightweight HTTP server & REST API
├── splitter.py               # Content block partitioning and HTML cleaner
├── static/
│   └── index.html            # Responsive Dark-Themed Management Studio UI
├── tag_mapper.py             # Taxonomy engine & filter mapping logic
└── wp_tags_cache.json        # Pre-cached taxonomy data
```

---

## Local Development & Docker Run

### Running locally:
```bash
python3 server.py 8080
# Access at http://localhost:8080
```

### Running with Docker:
```bash
docker compose up -d --build
# Access via configured reverse-proxy domain or host port
```

---

## API Endpoints

- `GET /api/status`: Service health check and system status.
- `GET /api/detect?url=...`: Universal detection of source JSON export capabilities and endpoints.
- `GET /api/profiles`: Retrieve list of configured source site profiles.
- `GET /api/analyze?langs=nl,en&count=5`: Pre-flight analysis of content and language availability.
- `GET /api/parse?langs=nl,en&count=5`: Full extraction, transformation, and structured JSON generation.
- `GET /api/tags/mapping`: Retrieve source taxonomy tags, current mapping rules, and available targets.
- `POST /api/tags/mapping`: Save user-defined taxonomy mapping overrides.
- `GET /api/agents`: Monitor active background worker agents.
