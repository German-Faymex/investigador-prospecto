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

---

# Reglas de Trabajo Autónomo y Calidad

## Filosofía de Trabajo

Trabaja con autonomía total. No me preguntes antes de actuar — actúa, verifica, corrige, y solo repórtame el resultado final funcionando. Si encuentras un error, corrígelo tú mismo sin consultarme. Si algo es ambiguo, toma la decisión más razonable y documéntala brevemente.

## Regla #1: NUNCA declares algo como "listo" sin haberlo verificado

- SIEMPRE ejecuta el código después de escribirlo
- SIEMPRE verifica el output real contra el output esperado
- Si genera archivos: confirma que existen y tienen contenido correcto
- Si es una API/endpoint: haz una request de prueba real
- Si es UI: verifica que renderiza sin errores en consola
- Si es un script: ejecútalo end-to-end con datos realistas
- **"Debería funcionar" NO es una verificación. Ejecútalo.**

## Regla #2: Ciclo obligatorio de desarrollo

Para CADA tarea, sigue este ciclo sin excepción:

```
1. PLANIFICAR  → Entiende qué se pide. Si es complejo, escribe un plan breve antes de codear.
2. IMPLEMENTAR → Escribe el código/cambio.
3. EJECUTAR    → Corre el código. No asumas que funciona.
4. VERIFICAR   → Revisa el output. ¿Es correcto? ¿Hay errores? ¿Warnings?
5. CORREGIR    → Si hay cualquier error, vuelve al paso 2. No me reportes errores, resuélvelos.
6. SELF-REVIEW → Antes de declarar "listo", revisa tu trabajo como QA (ver sección abajo).
7. REPORTAR    → Solo cuando todo funciona, dame un resumen ejecutivo.
```

## Regla #3: Self-Review obligatorio (QA interno)

Antes de declarar cualquier tarea como completada, ponte el sombrero de QA engineer crítico y revisa:

- [ ] ¿Ejecuté el código y el output es correcto?
- [ ] ¿Manejé los casos edge? (nulls, arrays vacíos, strings vacíos, datos faltantes)
- [ ] ¿Hay variables hardcodeadas que deberían ser configurables?
- [ ] ¿Los imports/dependencias están todos presentes?
- [ ] ¿Los paths de archivos son correctos y relativos al contexto correcto?
- [ ] ¿El error handling es adecuado? (try/catch donde corresponde, mensajes útiles)
- [ ] ¿Funciona no solo con el "happy path" sino con datos reales imperfectos?
- [ ] ¿Los tipos son correctos? (no hay undefined, null, o NaN inesperados)
- [ ] Si modifiqué algo existente: ¿no rompí otra funcionalidad?

## Regla #4: Testing

- Si existen tests en el proyecto, córrelos SIEMPRE después de cualquier cambio
- Si no existen tests pero el cambio es significativo, escribe al menos un test básico
- Si el linter/formatter está configurado, ejecútalo antes de dar por terminado
- Comandos a ejecutar siempre que apliquen:
  - Python: `ruff check . --fix && python -m pytest -x -q`
  - Node/TS: `npm run lint && npm test`
  - General: cualquier script de CI que exista en el proyecto

## Regla #5: Manejo de errores durante el trabajo

- Si un comando falla: lee el error completo, entiéndelo, y corrígelo
- Si una dependencia falta: instálala
- Si un archivo no existe: verifica el path correcto o créalo
- Si algo no tiene sentido: investiga antes de preguntar
- **No me muestres errores que puedes resolver tú mismo**
- Solo escálame algo si: requiere una decisión de negocio, necesita credenciales que no tienes, o llevas 3+ intentos fallidos en el mismo problema

## Regla #6: Calidad del código

- Código limpio y legible, con nombres descriptivos
- Comentarios solo cuando el "por qué" no es obvio (no comentes el "qué")
- No dejes código comentado, console.logs de debug, ni TODOs sin resolver
- Si refactorizas algo, asegúrate de que todo lo que dependía de ello sigue funcionando
- Prefiere soluciones simples y robustas sobre soluciones cleveras y frágiles

## Regla #7: Comunicación de resultados

Cuando termines una tarea, reporta:

1. **Qué hice** — una o dos frases
2. **Qué verifiqué** — cómo confirmé que funciona
3. **Decisiones tomadas** — solo si tomaste alguna decisión no obvia
4. **Limitaciones conocidas** — si las hay

No necesito ver cada paso intermedio ni cada error que corregiste. Dame el resumen ejecutivo.

## Reglas específicas para Python

- Usa type hints en funciones
- Maneja excepciones específicas, no bare `except:`
- Si usas paths: usa `pathlib.Path`, no strings concatenados
- Verifica que las dependencias estén en requirements.txt o pyproject.toml

## Reglas específicas para JavaScript/TypeScript

- Prefiere TypeScript si el proyecto ya lo usa
- Maneja promises correctamente (await, try/catch)
- No dejes `any` types si puedes evitarlo
- Verifica que no haya memory leaks en event listeners o intervals
