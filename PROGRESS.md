# Investigador de Prospectos — Progreso de Desarrollo

## Última actualización: 2026-03-23T14:30:00-03:00

## Estado actual
- Tarea actual: Completada — LinkedIn Deep Scraper + fixes de contaminación
- Branch activo: main (feature/linkedin-deep-scraper mergeado)
- Último commit: b74b2ff fix: filter hallazgos that attribute wrong LinkedIn cargo to prospect

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
