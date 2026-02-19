# Changelog

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
