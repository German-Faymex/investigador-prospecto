# Changelog

## [1.5.0] - 2026-06-11

### Confiabilidad: sitio corporativo correcto, JSON garantizado, fallback LLM reparado

**1. Fix crítico: sitio web de OTRA empresa mostrado como corporativo (caso Noracid/Metso)**
- **Síntoma**: al investigar un prospecto de Noracid, la UI mostraba metso.com (proveedor de su planta) como sitio de la empresa, y se scrapeaba el sitio de Metso como fuente "corporate"
- **Causa raíz**: cuando el sitio real bloquea con 403 (noracid.cl bloquea clientes no-navegador), el fallback DDG (`"empresa" sitio web oficial`) aceptaba el primer resultado no-red-social **sin validación**
- **Fix capa 1**: `_find_domain_via_ddg()` exige que el nombre de la empresa aparezca en el dominio candidato (`_domain_matches_company()`); mejor sin dominio que con el de un tercero
- **Fix capa 2**: todas las descargas del sitio corporativo (`_fetch_html()`) reintentan con TLS impersonation (reutiliza `tls_client` de LinkedIn) → noracid.cl ahora responde y sus páginas se scrapean
- **Fix capa 3**: `ResearchService._sanitize_sitio_web()` descarta cualquier `sitio_web` final cuyo dominio no coincida con el descubierto ni con el nombre de la empresa (cubre LLM y Perplexity); regla explícita anti-terceros en el prompt
- 13 tests de regresión nuevos en `tests/test_domain_validation.py`
- Archivos: `scraper/corporate_site.py`, `services/researcher.py`, `prompts/research_analyzer.md`

**1b. Fix complementario: dominio HOMÓNIMO (caso abc/ABC Network)**
- Segundo vector, reportado el mismo día: para la empresa 'abc', el dominio descubierto abc.com pasa la validación por nombre (el nombre SÍ está en el dominio) pero pertenece a ABC Network (cadena de TV). El LLM detectaba el mismatch en un hallazgo pero no tenía canal para actuar
- Nuevo campo de control `empresa.sitio_web_corresponde` (boolean) en `RESEARCH_SCHEMA`: el LLM evalúa si el dominio descubierto automáticamente corresponde a la empresa del prospecto (industria/país/contexto vs. las demás fuentes)
- `_sanitize_sitio_web()` respeta el veredicto: descarta el dominio y no lo rellena cuando `corresponde=false`; el flag nunca llega a la UI ni al email
- Si el flag falta (DeepSeek en modo json_object puede omitirlo), se asume válido
- 6 tests nuevos (61 total)
- Archivos: `services/schemas.py`, `services/researcher.py`, `prompts/research_analyzer.md`

**1c. Fix: el filtro anti-homónimos descartaba el perfil de la PROPIA persona (caso Nadia)**
- **Síntoma**: educación y ubicación "No disponible" aunque el perfil de LinkedIn las tiene
- **Causa**: el snippet de DDG a veces no menciona la empresa (el headline de la persona no la incluye) y el filtro anti-homónimos exigía esa mención → descartaba el perfil seleccionado por el LinkedIn scraper, perdiendo educación/ubicación. No-determinístico: dependía del snippet que DDG devolviera en cada corrida
- **Fix**: excepción `_text_mentions_full_name()` — el item del LinkedIn scraper (búsqueda ya acotada por empresa) se conserva si trae el nombre completo del prospecto, en enriquecimiento y en fuentes visibles. Homónimos con otro nombre siguen descartados
- 7 tests nuevos en `tests/test_enrichment_own_profile.py` (70 total)
- Archivos: `services/researcher.py`

**1d. Fix: datos de un homónimo atribuidos al prospecto (Nadia de California)**
- **Síntoma**: educación/ubicación de OTRA persona con nombre parecido (Cal Poly Pomona / San José) mostradas como del prospecto
- **Causa (2 huecos)**: (a) la query de fallback de LinkedIn acorta el nombre y, si ningún resultado mencionaba la empresa, devolvía igual los 2 primeros homónimos; (b) los filtros anti-homónimos solo protegían la UI y el enriquecimiento — los items contaminados llegaban igual al LLM como "hechos"
- **Fix**: `_search_ddg_api` exige nombre completo cuando no hay match de empresa (si no, devuelve vacío y se intenta la siguiente query); nuevo `_is_relevant_item()` en researcher filtra los items ANTES del verifier/LLM con las mismas reglas que la UI
- 8 tests nuevos (78 total)
- Archivos: `scraper/linkedin.py`, `services/researcher.py`

**2. JSON garantizado en respuestas LLM (structured outputs)**
- Antes el JSON se extraía con regex; un parseo fallido perdía toda la investigación ya pagada
- `services/schemas.py` (nuevo): `RESEARCH_SCHEMA` y `EMAIL_SCHEMA` en JSON Schema
- `LLMClient.complete(..., json_schema=)`: DeepSeek usa `response_format: json_object` (JSON válido garantizado); Haiku usa structured outputs (`output_config.format`, validación contra esquema)
- Prompt `research_analyzer.md` alineado al esquema (`tamano_empleados`, `noticias_recientes` como lista)
- El parseo regex queda como red de seguridad
- Archivos: `services/llm_client.py`, `services/schemas.py`, `services/researcher.py`, `services/email_generator.py`

**3. Fix: fallback a Haiku roto por modelo retirado**
- `claude-3-5-haiku-20241022` fue retirado el 19-feb-2026 y devolvía 404: cuando DeepSeek fallaba, el sistema entero fallaba en silencio en vez de usar el respaldo
- Reemplazado por `claude-haiku-4-5` en `config/settings.py`; verificado con llamada real

**4. UX: logo Faymex + ayuda integrada**
- Logo horizontal oficial (blanco) en el navbar
- Panel plegable "¿Cómo se usa y cómo funciona?" sobre el formulario: guía de 3 pasos + explicación de fuentes, score, tipos de hallazgo (A–D) y metodología SMTYKM
- Archivos: `webapp/templates/base.html`, `webapp/templates/index.html`, `webapp/static/img/logo-faymex-blanco.png`

## [1.4.0] - 2026-03-23

### LinkedIn Deep Scraper + anti-contaminación (documentado retroactivamente; detalle en PROGRESS.md)

- **TLS fingerprint impersonation** (`scraper/tls_client.py`, curl_cffi): fetch directo de perfiles públicos de LinkedIn impersonando browsers reales (Chrome/Firefox/Safari/Edge), con retry de 3 perfiles ante authwall. Limitación: desde datacenter (Railway) la mayoría de perfiles devuelve 999
- **Anti-contaminación de company pages**: facts de `linkedin.com/company` se anotan con warning, se excluyen del enriquecimiento, y regla 8b en el prompt
- **Cargo del usuario prevalece** siempre sobre lo descubierto; filtro de hallazgos con cargo contradictorio
- **Fix Starlette 0.46+**: nueva API de `TemplateResponse`
- Endpoint JSON `/api/research/json` para consumidores externos

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
