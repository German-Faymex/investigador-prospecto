# Investigador de Prospectos — Progreso de Desarrollo

## Última actualización: 2026-06-11

## Estado actual
- Tarea actual: Completada — fix crítico sitio corporativo equivocado (Noracid/Metso)
- Branch activo: main
- Último commit: d0cad88 (deployado y verificado en producción)

## Sesión 11 jun 2026 — confiabilidad LLM + fix crítico de dominio corporativo
1. **fix: modelo Haiku retirado** — `claude-3-5-haiku-20241022` fue retirado el 19-feb-2026
   y devolvía 404: el fallback cuando DeepSeek fallaba estaba roto en silencio.
   Reemplazado por `claude-haiku-4-5` en `config/settings.py`. Verificado con llamada real.
2. **feat: JSON garantizado** — antes el JSON se extraía con regex y un parseo fallido
   perdía toda la investigación. Ahora:
   - `services/schemas.py` (NUEVO): RESEARCH_SCHEMA y EMAIL_SCHEMA (JSON Schema).
   - `LLMClient.complete(..., json_schema=)`: DeepSeek usa `response_format: json_object`;
     Haiku usa structured outputs (`output_config.format`, validación contra esquema).
   - Tres call sites actualizados (researcher x2, email_generator).
   - Prompt `research_analyzer.md` alineado al esquema (`tamano_empleados`,
     `noticias_recientes` como lista, persona con logros/experiencia).
   - `_parse_llm_response` queda como red de seguridad.
   Verificado con llamadas reales a ambos proveedores + 42 tests pasando.

3. **fix crítico: sitio web de OTRA empresa** (caso reportado por Germán con captura) —
   investigando "Elio Barraza @ Noracid" la UI mostraba metso.com como sitio corporativo.
   Cadena del bug: noracid.cl responde 403 a clientes no-navegador → `_guess_company_domain`
   falla → fallback `_find_domain_via_ddg("Noracid sitio web oficial")` tomaba el PRIMER
   resultado no-red-social sin validar → metso.com (construyó la planta de Noracid, domina
   esa búsqueda) → se scrapeó el sitio de Metso como "corporate" y quedó en sitio_web.
   Fix en 3 capas (commit d0cad88):
   - `_domain_matches_company()`: el fallback DDG exige nombre de empresa en el dominio
   - `_fetch_html()`: todo fetch del sitio corporativo reintenta con TLS impersonation
     (noracid.cl ahora se scrapea: 3 páginas reales, score 85 local / 80 prod)
   - `_sanitize_sitio_web()` en researcher: descarta dominio de tercero aunque venga
     del LLM o Perplexity + regla anti-terceros en prompt
   13 tests de regresión (`tests/test_domain_validation.py`), 55 total.
   Verificado E2E local Y en producción post-deploy (sitio_web=noracid.cl, 0 URLs metso).
4. **ux: logo Faymex + ayuda** — logo blanco oficial en navbar (asset de Oportunidades
   Dashboard) + panel plegable "¿Cómo se usa y cómo funciona?" en index. Verificado con
   Playwright local y logo sirviendo 200 en prod.
5. **Verificación Perplexity** (pregunta de Germán): SÍ está activo local y en prod
   (logs: "6 citations reales obtenidas"). Matiz: su aporte suele ser invisible en la UI
   porque llena campos del perfil vía _enrich_from_perplexity sin dejar items visibles.

3b. **fix complementario: dominio homónimo (caso "Ely Diaz @ abc", commit 0cabf84)** —
   abc.com pasa la validación por nombre pero es ABC Network. La validación
   heurística no puede distinguir homónimos de dominio; el veredicto ahora lo da
   el LLM vía `empresa.sitio_web_corresponde` (boolean en el schema) y
   `_sanitize_sitio_web` lo aplica (descarta + no rellena). Verificado E2E local
   (sitio_web vacío en vez de abc.com) y en producción.

3c. **fix: educación/ubicación perdidas por filtro anti-homónimos (caso "Nadia
   Ramirez Lara @ Desert King")** — el snippet DDG del perfil propio no siempre
   menciona la empresa; el filtro lo descartaba y con él educación/ubicación.
   Excepción por nombre completo (`_text_mentions_full_name`) para items del
   LinkedIn scraper. OJO: los snippets DDG son no-determinísticos; si DDG no
   devuelve la educación en el snippet y LinkedIn bloquea el fetch directo (999),
   el dato simplemente no llega — limitación de fuentes, no bug.

3d. **fix: homónimo contaminando persona (commit pendiente de hash)** — la query
   de fallback de LinkedIn ("Nadia Ramirez" sin apellido2) traía perfiles de otras
   personas y el researcher los pasaba al LLM como hechos (los filtros existentes
   eran solo para UI/enriquecimiento). Ahora: nombre completo obligatorio en el
   scraper sin match de empresa + `_is_relevant_item()` filtra antes del LLM.
   PRINCIPIO para futuras sesiones: lo que no pasaría el filtro de la UI tampoco
   debe llegar al LLM.

3e. **fix: homónimo vía Perplexity** — enriquecimiento reordenado (LinkedIn
   validado primero) + gate: persona de Perplexity descartada si no menciona la
   empresa. NOTA: la completitud de educación/ubicación sigue dependiendo del
   snippet DDG de cada corrida (no-determinístico); lo garantizado ahora es que
   NO se muestran datos de otra persona.

## Datos operativos (verificados hoy)
- Railway: proyecto "Investigador Prospecto", servicio "Investigador Prospecto"
- Prod: https://web-production-72452.up.railway.app (auto-deploy desde push a main, ~2 min)
- Estado de fuentes desde Railway: Perplexity OK, corporate OK (ahora con TLS),
  DDG News OK, LinkedIn TLS casi siempre 999 (solo snippets), Google Search 0 items
- API keys local (.env): DeepSeek, Anthropic y Perplexity presentes

## Mejoras pendientes propuestas (auditoría 11 jun, en orden)
1. Resolución de entidades con LLM antes del análisis (reemplaza los filtros regex
   anti-homónimos/company-pages, la fuente principal de errores de atribución).
   El caso Noracid/Metso de hoy es el mismo patrón generalizado a todas las fuentes.
2. Verifier: deduplicar por dominio antes de contar "diversidad de fuentes"
   (Google+DDG con la misma URL no son 2 fuentes).
3. Desactivar scraping LinkedIn TLS en producción (999 desde Railway) o evaluar
   web search server-side de Anthropic como reemplazo de Google/DDG.
4. Persistencia (SQLite): caché por empresa, historial, feedback de emails.
5. Score determinístico en código (hoy lo asigna el LLM).
6. `_fix_email_closing` asume "Quedo atento," (falla con remitente mujer).
7. Mostrar las citations de Perplexity como fuentes visibles en la UI (hoy su
   aporte es invisible y genera la impresión de que no se usa).

---

# Historial — Sesión 23 mar 2026
- Último commit de esa sesión: b74b2ff fix: filter hallazgos that attribute wrong LinkedIn cargo to prospect

## Lo que se completó en esta sesión (23 mar 2026)

### 1. TLS Fingerprint Impersonation para LinkedIn (feat)
- **Nuevo archivo**: `scraper/tls_client.py` — Cliente HTTP con curl_cffi que impersona browsers reales (Chrome 131/136, Firefox 135, Safari 18, Edge 101)
- **Modificado**: `scraper/linkedin.py` — Pipeline mejorado:
  - DDG busca URL del perfil → curl_cffi con TLS fetch directo al perfil público
  - Retry con 3 TLS profiles distintos si hay authwall
  - Extracción de datos frescos: cargo actual, empresa, educación, ubicación desde og:title + JSON-LD + meta tags
  - Sanitización de títulos DDG (bug de títulos concatenados de DDG)
  - Fallback: extrae cargo del título DDG cuando TLS está bloqueado
- **Dependencia**: curl_cffi>=0.7.0 agregado a requirements.txt
- **Limitación**: Desde IP residencial (local) funciona para mayoría de perfiles. Desde datacenter (Railway) solo perfiles ultra-públicos pasan (status 999 para el resto)

### 2. Fix contaminación de página empresa LinkedIn (fix)
- **Problema**: La página `linkedin.com/company/faymex` lista TODOS los empleados con sus cargos. El LLM atribuía cargos de otros empleados (Gerente de Operaciones, Jefe Prevención de Riesgos) al prospecto investigado.
- **Solución prompt**: Nueva regla 8b en `research_analyzer.md` — instrucción explícita de no mezclar cargos de otros empleados
- **Solución código**: Facts de `linkedin.com/company` se anotan con warning en el contexto LLM. Items de company/posts pages excluidos del enriquecimiento.

### 3. Cargo proporcionado prevalece siempre (fix)
- **Problema**: El LLM llenaba `cargo_descubierto` con datos contaminados de company pages, y el fallback del usuario nunca se activaba.
- **Solución**: Si el usuario proporciona cargo en el formulario, siempre sobrescribe lo que el LLM descubrió.

### 4. Eliminación del campo Cargo de la UI (fix)
- **Problema**: Campo "Cargo" en resultados era redundante con "Trayectoria" y mostraba datos erróneos.
- **Solución**: Eliminado del template `partials/research_result.html`. Trayectoria es ahora la fuente única.

### 5. Filtro de hallazgos contradictorios (fix)
- **Problema**: LLM generaba hallazgos como "Perfil LinkedIn muestra a X como Jefe de Bodega" basándose en perfiles homónimos o company pages.
- **Solución**: Post-filtro en `researcher.py` que descarta hallazgos que mencionan un cargo LinkedIn diferente al proporcionado por el usuario.

### 6. Fix Starlette TemplateResponse API (fix)
- **Problema**: Agregar curl_cffi al rebuild hizo que Railway instalara Starlette 0.46+ que cambió la API de TemplateResponse de `(name, {"request": req})` a `(request, name, context)`.
- **Solución**: Actualizado en `webapp/app.py`, `routers/research.py`, `routers/emails.py`.

## Commits de esta sesión (6 total)
1. `4fc483c` feat: add TLS fingerprint impersonation for LinkedIn profile scraping
2. `c6571fa` fix: prevent company LinkedIn page data from contaminating prospect profiles
3. `40c89f5` fix: user-provided role always overrides LLM-discovered cargo
4. `04ef575` fix: remove redundant Cargo field from research results UI
5. `5aae5ff` fix: update TemplateResponse to new Starlette API
6. `b74b2ff` fix: filter hallazgos that attribute wrong LinkedIn cargo to prospect

## Archivos modificados
- `scraper/tls_client.py` (NUEVO) — Cliente TLS con curl_cffi
- `scraper/linkedin.py` — Pipeline LinkedIn reescrito con TLS + sanitización
- `requirements.txt` — +curl_cffi>=0.7.0
- `prompts/research_analyzer.md` — Regla 8b anti-contaminación company page
- `services/researcher.py` — Override cargo, filtro hallazgos, warning company pages
- `webapp/templates/partials/research_result.html` — Eliminado campo Cargo
- `webapp/app.py` — TemplateResponse nueva API
- `webapp/routers/research.py` — TemplateResponse nueva API
- `webapp/routers/emails.py` — TemplateResponse nueva API
- `tests/test_edge_cases.py` — Mock actualizado para tls_fetch

## Decisiones tomadas
- **No pedir login LinkedIn al usuario**: Mala UX, riesgo de cuenta, innecesario (TLS funciona sin auth)
- **No integrar Bing como buscador**: URLs obfuscadas con tracking redirects, interpreta "German" como idioma
- **Eliminar campo Cargo de UI**: Redundante con Trayectoria y fuente de confusión
- **Post-filtro de hallazgos**: Más efectivo que intentar que el LLM no genere hallazgos erróneos

## Problemas conocidos
- **DDG no-determinístico**: Los resultados de DDG varían entre ejecuciones, a veces no encuentra el perfil correcto
- **LinkedIn 999 desde datacenter**: La mayoría de perfiles regulares bloquean desde Railway (solo funciona bien desde IP residencial)
- **Nombre incorrecto**: El sistema encontró "German Saltrón Mellado" en vez de "Germán Peralta" — DDG matchea por empresa (Faymex) pero el perfil es de otro empleado

## Próximos pasos sugeridos
1. Mejorar matching de perfiles LinkedIn (validar que el nombre en el perfil coincida con el buscado)
2. Considerar pinear versiones de FastAPI/Starlette en requirements.txt para evitar breaking changes
3. Explorar Perplexity como fuente principal de cargo actual (más confiable que DDG para datos personales)
