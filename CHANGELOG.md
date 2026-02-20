# Changelog

## [1.3.0] - 2026-02-20

### Calidad de datos: anti-homónimos, fuentes limpias, cargo confiable

**1. Migración a DDG API (ddgs library)**
- Reemplazado HTML scraping de DDG por `ddgs` library (API interna)
- Funciona desde Railway (datacenter IPs) sin bloqueos
- `asyncio.Lock` serializa llamadas DDG para evitar rate limiting
- Archivos: `scraper/base.py`, `scraper/google_search.py`, `scraper/google_news.py`, `scraper/linkedin.py`

**2. Fix noticias en email + visibilidad de fuentes**
- Noticias de empresa ahora aparecen como hook en el cuerpo del email SMTYKM
- Todas las fuentes scrapeadas son visibles en la UI
- Archivos: `services/email_generator.py`, `webapp/templates/partials/research_result.html`

**3. Fix color score-hot**
- El gradiente de score >= 80 usaba rojo (#D82A34) que parecía error
- Cambiado a naranja-ámbar (#ea580c → #f59e0b) para indicar "oportunidad caliente"
- Archivos: `webapp/static/css/app.css`

**4. Sistema anti-homónimos (multi-capa)**
- **Capa 1 — Prompt LLM**: Regla #8 en `research_analyzer.md` obliga al LLM a filtrar datos de personas homónimas en otras empresas
- **Capa 2 — LinkedIn scraper**: `_search_ddg_api()` prioriza resultados DDG que mencionan la empresa del prospecto (máx 3 matching vs 2 non-matching)
- **Capa 3 — Enriquecimiento**: `_enrich_from_scraped_items()` solo usa snippets de LinkedIn que mencionan la empresa correcta
- **Capa 4 — Fuentes mostradas**: `raw_sources` filtra TODOS los resultados de búsqueda (DDG, Google, LinkedIn) que no mencionan la empresa en título/snippet
- **Capa 5 — Perplexity**: Regla anti-homónimo en system prompt de Perplexity
- Nuevo método `_text_mentions_company()` para matching flexible de nombres de empresa
- Archivos: `services/researcher.py`, `scraper/linkedin.py`, `scraper/perplexity.py`, `prompts/research_analyzer.md`

**5. Filtrado de fuentes ruidosas y deduplicación**
- Filtro de dominios ruidosos: ZoomInfo, RocketReach, TheOrg, TwitchTracker, ChileTrabajos se excluyen de fuentes mostradas (siguen llegando al LLM para cruce)
- Filtro de noticias irrelevantes: solo se muestran noticias que mencionan la empresa o persona
- Deduplicación de URLs: `seen_urls` set previene duplicados en fuentes
- Archivos: `services/researcher.py`

**6. Fuentes unificadas en UI**
- Reemplazadas las secciones separadas de fuentes (persona/empresa) por una sola sección "fuentes consultadas" debajo de los resultados
- Previene secciones de fuentes vacías cuando DDG rate limiting reduce resultados de un tipo específico
- Archivos: `webapp/templates/partials/research_result.html`

**7. Prioridad del cargo proporcionado por el usuario**
- Sección `⚠️ INSTRUCCIÓN PRIORITARIA SOBRE CARGO` inyectada en contexto del LLM cuando el usuario proporciona cargo
- Datos de ZoomInfo/RocketReach con cargo contradictorio se filtran antes de llegar al LLM
- Fallback: si el LLM devuelve "No disponible" para cargo, se usa el cargo del formulario
- Archivos: `services/researcher.py`

**8. Jerarquía de confiabilidad de fuentes**
- Regla 5b en prompt: LinkedIn > Perplexity > Sitio web > ZoomInfo (variable)
- Regla de cargo: si LinkedIn y ZoomInfo difieren, evaluar cuál es más reciente; cargo del usuario prevalece
- Advertencia en contexto LLM sobre fuentes desactualizadas
- Archivos: `prompts/research_analyzer.md`, `services/researcher.py`

**9. Trayectoria en orden cronológico inverso**
- Regla 5c en prompt: trayectoria siempre empieza con cargo ACTUAL (más reciente primero)
- Formato: "Actualmente [cargo] en [empresa]. Anteriormente [cargo anterior]..."
- Archivos: `prompts/research_analyzer.md`

**10. Intereses solo de datos reales**
- Regla 5d en prompt: intereses solo de datos explícitos (ej: sección de LinkedIn)
- Prohibido inferir intereses a partir de cargos o industria
- Archivos: `prompts/research_analyzer.md`

**11. Fix extracción de educación**
- Regex limitado a 80-100 chars para evitar capturar fragmentos de snippets
- Skip de fragmentos "ucation:" de meta tags de LinkedIn
- Skip de palabras de negocio ("nuestro", "servicios", "empresa")
- Patrones agregados: IESA, DUOC
- Archivos: `services/researcher.py`

**12. Fix timeout HTMX**
- `htmx.config.timeout = 120000` (2 min) para investigaciones largas (~50s)
- Handler `htmx:beforeSwap` para prevenir page resets en errores
- Mensajes de error mejorados con códigos HTTP
- Archivos: `webapp/templates/base.html`, `webapp/templates/index.html`, `webapp/static/js/app.js`

---

## [1.2.0] - 2026-02-19

### Integración Perplexity API + correcciones anti-alucinación

**1. Perplexity API como 5to scraper**
- Nuevo `scraper/perplexity.py` — usa Perplexity sonar-pro para búsqueda web real
- Se ejecuta en paralelo con los otros 4 scrapers
- Genera ScrapedItems solo de persona y empresa (NO noticias — muy propensas a alucinación)
- No usa URLs de Perplexity (frecuentemente fabricadas/404)
- Datos estructurados se guardan en `last_result` para enriquecimiento post-LLM
- Fallback silencioso si no hay API key
- Archivos: `scraper/perplexity.py` (nuevo), `config/settings.py`, `scraper/orchestrator.py`, `.env.example`

**2. Enriquecimiento post-LLM con datos de Perplexity**
- `_enrich_from_perplexity()` en researcher llena campos vacíos (trayectoria, educación, cargo, industria, etc.)
- Solo enriquece persona y empresa, NO hallazgos (anti-alucinación)
- `_fill_if_empty()` helper respeta datos existentes
- Verifier actualizado: fuentes perplexity_* nunca se descartan
- Archivos: `services/researcher.py`, `services/verifier.py`

**3. Correcciones anti-alucinación de Perplexity**
- Prompt con reglas estrictas anti-alucinación (7 reglas explícitas)
- Advertencia de empresas homónimas (ej: Faymex Chile vs México)
- Temperature bajada a 0.1 (antes 0.2)
- Timeout reducido a 25s
- Eliminados items de hallazgos/noticias del pipeline
- Eliminado enriquecimiento de hallazgos desde Perplexity
- Archivos: `scraper/perplexity.py`, `services/researcher.py`

**4. Fix alucinación "89,500 proyectos"**
- El prompt research_analyzer.md tenía ejemplo incorrecto (`"+89500 proyectos"` cuando el sitio dice "+89500 horas efectivas")
- Regla corregida: citar cifras con unidad exacta, nunca confundir métricas
- Archivos: `prompts/research_analyzer.md`

**5. Velocidad de scraping**
- Orchestrator cambiado de `asyncio.gather` a `asyncio.wait(timeout=15s)`
- Scrapers lentos/bloqueados se cancelan sin bloquear los demás
- Archivos: `scraper/orchestrator.py`

**6. Mejoras de UI**
- Fuentes separadas por panel (persona vs empresa)
- Labels de fuentes con badges compactos (perplexity_empresa→perplexity, corporate→web, etc.)
- Fix overlap de labels con layout flex
- Archivos: `webapp/templates/partials/research_result.html`

**7. Asuntos de email con brecha de curiosidad**
- 5 técnicas de curiosidad gap en el prompt
- Prohibido describir cargo/industria en el asunto
- Ejemplos buenos y malos explícitos
- Archivos: `prompts/email_generator.md`

**8. Capitalización de nombres**
- `_title_case()` normaliza nombres del formulario ("gustavo peralta" → "Gustavo Peralta")
- Respeta preposiciones españolas (de, del, la) y mixed case (McDonald)
- Solo aplica a nombres de persona, no empresas
- Archivos: `webapp/routers/research.py`

**9. Extracción de servicios del nav**
- Corporate scraper ahora extrae textos de links del `<nav>` antes de eliminarlo
- Los servicios/productos del menú se agregan como metadatos
- Archivos: `scraper/corporate_site.py`

---

## [1.1.0] - 2026-02-19

### 6 mejoras de feedback beta

**1. Campo "Cargo" obligatorio**
- El campo Cargo ya no es opcional; se requiere tanto en el formulario (atributo `required`) como en el backend (`Form(...)`)
- Archivos: `index.html`, `research.py`

**2. URLs de LinkedIn y sitio web al tope de las tarjetas**
- "Buscar en LinkedIn" aparece justo después del nombre en Info Personal
- Sitio web de la empresa aparece justo después del nombre en Info Empresa
- Archivos: `research_result.html`

**3. LinkedIn search URL (en vez de perfil directo)**
- Nuevo método estático `LinkedInScraper.build_search_url(name, company)` que genera URL de búsqueda de personas en LinkedIn
- Nuevo campo `linkedin_search_url` en `ResearchResult` — se genera siempre, independiente del scraping
- El link en la UI dice "Buscar en LinkedIn" (honesto: es búsqueda, no perfil)
- Archivos: `linkedin.py`, `researcher.py`, `research_result.html`

**4. Match geográfico contacto ↔ noticias**
- Nuevo campo "Ubicación (opcional)" en el formulario con 4 columnas en desktop
- El parámetro `location` fluye por toda la cadena: router → orchestrator → scrapers → LLM prompts → email
- Google News incluye la ubicación en el query cuando está disponible
- Prompts de análisis y email priorizan hallazgos de la región del prospecto
- Nuevo campo `location` en `ResearchResult`
- Archivos: `index.html`, `research.py`, `base.py`, `orchestrator.py`, `google_news.py`, `google_search.py`, `corporate_site.py`, `linkedin.py`, `researcher.py`, `email_generator.py`, `research_analyzer.md`, `email_generator.md`

**5. Fix espacio faltante en cierre del email**
- Reforzada instrucción en el prompt para incluir salto de línea entre "Quedo atento," y el nombre
- Nuevo método `_fix_email_closing()` en `EmailGenerator` que aplica post-procesamiento con regex para garantizar el `<br>` / `\n`
- Archivos: `email_generator.md`, `email_generator.py`

**6. Botón "Nueva Investigación"**
- Nuevo botón en la fila de acciones del formulario (aparece tras recibir resultados)
- Botón duplicado al fondo de los resultados para acceso rápido
- Función `resetPage()`: limpia formulario, vacía resultados, resetea step indicator, scroll al top + focus
- Archivos: `index.html`, `app.js`, `research_result.html`

---

## [1.0.0] - 2026-02-18

### Release inicial
- Investigación de prospectos B2B con 4 scrapers async (Google Search, Google News, LinkedIn, Corporate)
- Verificación cruzada de fuentes con scoring de confianza
- Análisis LLM híbrido (DeepSeek + Claude Haiku fallback)
- Generación automática de emails SMTYKM personalizados
- UI con HTMX + Quill editor + step indicator
- Deploy en Railway con auto-deploy desde main
