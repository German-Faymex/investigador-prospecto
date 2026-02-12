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
├── main.py                 # Entrypoint
├── Procfile                # Railway deploy
├── requirements.txt        # Dependencias
├── config/
│   └── settings.py         # Configuración centralizada (singleton)
├── scraper/
│   ├── google.py           # Scraper de Google
│   ├── linkedin.py         # Scraper de LinkedIn
│   └── website.py          # Scraper de sitios web
├── services/
│   ├── llm_client.py       # Cliente LLM híbrido (DeepSeek/Haiku)
│   ├── research.py         # Orquestador de investigación
│   └── email_generator.py  # Generador de emails
├── prompts/
│   └── templates.py        # Prompts para LLMs
├── webapp/
│   ├── app.py              # FastAPI app + rutas
│   ├── static/             # CSS, JS
│   └── templates/          # Jinja2 HTML templates
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

- **Scrapers async**: Todos los scrapers usan httpx async para paralelismo
- **LLM híbrido**: DeepSeek para análisis principal, Haiku para verificación
- **Sistema de verificación**: Score de calidad de la investigación (min 40/100)
- **Config singleton**: `from config.settings import get_settings`

## Deploy (Railway)

- Auto-deploy desde branch `main`
- El `Procfile` define el comando de inicio
- Variables de entorno configuradas en Railway dashboard
