# Changelog

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
