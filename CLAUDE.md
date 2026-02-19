# Investigador de Prospectos

Herramienta standalone de investigación B2B que busca información sobre prospectos/empresas en fuentes públicas, genera un perfil de investigación y redacta emails de primer contacto personalizados.

## Stack

- **Backend**: FastAPI + Jinja2 templates
- **Frontend**: HTMX + Quill (rich text editor)
- **Scraping**: httpx + BeautifulSoup4 (async)
- **LLM**: DeepSeek (análisis principal) + Claude Haiku (verificación)
- **Deploy**: Railway (auto-deploy desde main)

## Ejecución local

```bash
# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus API keys

# Ejecutar
python main.py
# o
uvicorn webapp.app:app --reload --port 8000
```

## Estructura del proyecto

```
├── main.py                 # Entrypoint (uvicorn)
├── Procfile                # Railway deploy
├── requirements.txt        # Dependencias
├── CHANGELOG.md            # Historial de cambios
├── config/
│   └── settings.py         # Configuración centralizada (singleton)
├── scraper/
│   ├── base.py             # BaseScraper ABC + ScrapedItem dataclass
│   ├── google_search.py    # Scraper de búsqueda general Google
│   ├── google_news.py      # Scraper de Google News (últimos 6 meses)
│   ├── linkedin.py         # Scraper de LinkedIn vía Google + build_search_url()
│   ├── corporate_site.py   # Scraper de sitios web corporativos
│   └── orchestrator.py     # Ejecuta los 4 scrapers en paralelo
├── services/
│   ├── llm_client.py       # Cliente LLM híbrido (DeepSeek → Haiku fallback)
│   ├── researcher.py       # Orquestador: scrape → verify → LLM → ResearchResult
│   ├── verifier.py         # Verificación cruzada de fuentes + scoring
│   └── email_generator.py  # Generador de emails SMTYKM
├── prompts/
│   ├── research_analyzer.md  # Prompt de análisis de investigación
│   ├── email_generator.md    # Prompt de generación de email
│   └── smtykm_system.md     # Metodología SMTYKM completa
├── webapp/
│   ├── app.py              # FastAPI app + ruta raíz
│   ├── routers/
│   │   ├── research.py     # POST /api/research
│   │   └── emails.py       # POST /api/email/generate
│   ├── static/js/
│   │   └── app.js          # Frontend JS (HTMX handlers, Quill, reset)
│   └── templates/
│       ├── base.html       # Layout base
│       ├── index.html      # Página principal (formulario)
│       └── partials/       # Fragmentos HTMX (research_result, loading, error, email_editor)
└── tests/                  # Tests
```

## Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `DEEPSEEK_API_KEY` | Sí* | API key de DeepSeek |
| `ANTHROPIC_API_KEY` | Sí* | API key de Anthropic |
| `APP_MODE` | No | `development` o `production` |
| `PORT` | No | Puerto (default: 8000) |
| `SENDER_NAME` | No | Nombre del remitente para emails |
| `SENDER_COMPANY` | No | Empresa del remitente |

*Al menos una API key es requerida.

## Patrones clave

- **Scrapers async**: Todos los scrapers heredan de `BaseScraper` y usan httpx async para paralelismo. Signature estándar: `search(name, company, role="", location="")`
- **LLM híbrido**: DeepSeek para análisis principal, Haiku como fallback
- **Sistema de verificación**: Score de calidad (0-100) basado en cruce de fuentes
- **Config singleton**: `from config.settings import get_settings`
- **LinkedIn search URL**: Se genera siempre una URL de búsqueda en LinkedIn (no perfil directo) via `LinkedInScraper.build_search_url()`
- **Match geográfico**: El campo `location` fluye desde formulario → router → orchestrator → scrapers → LLM prompts → email generator
- **Email post-processing**: `_fix_email_closing()` asegura salto de línea entre "Quedo atento," y el nombre

## Deploy (Railway)

- Auto-deploy desde branch `main`
- El `Procfile` define el comando de inicio
- Variables de entorno configuradas en Railway dashboard
