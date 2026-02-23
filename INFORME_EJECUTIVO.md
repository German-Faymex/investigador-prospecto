# Informe Ejecutivo: Investigador de Prospectos

## Resumen

**Investigador de Prospectos** es una herramienta de inteligencia comercial B2B que automatiza la investigación de prospectos de venta y genera correos personalizados utilizando la metodología SMTYKM (Show Me That You Know Me).

**Producción:** https://web-production-72452.up.railway.app
**Versión:** v1.3.0 (20 febrero 2026)

---

## 1. Necesidad que Resuelve

Los equipos comerciales de Faymex enfrentan un problema recurrente: investigar manualmente a un prospecto (LinkedIn, Google, sitio corporativo, noticias) toma entre **20 y 30 minutos por persona**, y los correos fríos genéricos tienen tasas de apertura muy bajas.

**Desafíos específicos:**
- La investigación manual es lenta, fragmentada y no escalable
- Los correos genéricos son ignorados por los tomadores de decisión
- No existe un sistema que cruce fuentes para verificar datos y evitar errores por homónimos
- Los vendedores no siempre saben qué información usar como gancho para personalizar

---

## 2. Cómo se Abordó

### Stack Tecnológico
| Componente | Tecnología |
|---|---|
| Backend | FastAPI + Python (async) |
| Frontend | HTMX + Jinja2 + Quill Editor |
| Scraping | httpx async + BeautifulSoup4 + DuckDuckGo API |
| IA Principal | DeepSeek (análisis) + Claude Haiku (fallback) |
| Búsqueda Web | Perplexity AI sonar-pro |
| Deploy | Railway (auto-deploy desde main) |

### Decisiones Clave de Diseño
- **5 scrapers en paralelo** con timeouts diferenciados (web: 12s, Perplexity: 30s)
- **Estrategia de LLM híbrida**: DeepSeek para costo-eficiencia, Haiku como fallback para confiabilidad
- **Perplexity como 5° scraper**: búsqueda web legítima via API para enriquecimiento
- **Verificación cruzada**: similitud Jaccard entre fuentes para confirmar datos
- **Metodología SMTYKM** embebida en los prompts para generar correos que realmente personalizan

---

## 3. Cómo Funciona

### Pipeline de Investigación (45-50 segundos)

```
Entrada del Usuario (Nombre, Empresa, Cargo, Ubicación)
                    ↓
    ┌───────────────────────────────────────┐
    │   5 SCRAPERS EN PARALELO (12-30s)     │
    ├── Google Search (web general)         │
    ├── Google News (noticias recientes)    │
    ├── LinkedIn (via DuckDuckGo API)       │
    ├── Sitio Corporativo (HTML directo)    │
    └── Perplexity API (enriquecimiento)    │
    └───────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────────┐
    │   VERIFICACIÓN DE FUENTES             │
    ├── Filtrado anti-homónimos (5 capas)   │
    ├── Deduplicación de URLs               │
    ├── Verificación cruzada (Jaccard)      │
    └── Scoring de confianza                │
    └───────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────────┐
    │   ANÁLISIS LLM (DeepSeek/Haiku)       │
    ├── Extracción estructurada (JSON)      │
    ├── Clasificación de hallazgos (A-D)    │
    ├── Score de calidad (0-100)            │
    └── Enriquecimiento post-Perplexity     │
    └───────────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────────┐
    │   GENERACIÓN DE EMAIL (SMTYKM)        │
    ├── Asunto ≤40 chars (curiosity gap)    │
    ├── 4 párrafos: gancho, dolor,          │
    │   credibilidad, CTA                   │
    └── HTML + texto plano                  │
    └───────────────────────────────────────┘
                    ↓
         Interfaz Web con Editor
```

### Sistema Anti-Homónimos (5 Capas)
1. **Regla en prompt LLM**: filtra datos de homónimos
2. **Scraper LinkedIn**: filtra resultados que no mencionan la empresa
3. **Enriquecimiento**: solo usa snippets que coinciden con la empresa
4. **raw_sources en UI**: filtra resultados sin mención de empresa
5. **Prompt Perplexity**: advertencia explícita contra mezcla de homónimos

### Clasificación de Hallazgos
| Tipo | Score | Descripción |
|---|---|---|
| A | 80-100 | Evento reciente de la empresa (expansión, adquisición, proyecto específico) |
| B | 60-79 | Dato específico del ejecutivo (promoción, publicación, logro) |
| C | 40-59 | Info general de industria/empresa (verificada pero no reciente) |
| D | 0-39 | Datos insuficientes |

### Metodología SMTYKM para Emails
- **Gancho**: Mención específica de un hallazgo (no opener genérico)
- **Dolor**: Desafío específico del cargo (Mantenimiento: paradas; Proyectos: cronogramas; Compras: consolidación)
- **Credibilidad**: Mención real de cliente (CODELCO, Anglo American) sin pitch
- **CTA**: Pregunta única (nunca pedir reunión directamente)

---

## 4. Beneficios

### Eficiencia Operacional
| Métrica | Antes | Después |
|---|---|---|
| Tiempo por prospecto | 20-30 minutos | 45-50 segundos |
| Emails personalizados/día | 5-10 | 100+ |
| Costo por investigación | Tiempo del vendedor | ~$0.05-0.10 USD en APIs |
| Verificación de datos | Manual, propenso a error | Automática, 5 capas |

### Valor para el Negocio
- **Generación de pipeline** automatizada sin contratar SDRs adicionales
- **Mayor tasa de apertura** por personalización genuina basada en datos verificados
- **Menor costo por lead** del mercado (API-based, no scraping manual)
- **Replicable** a cualquier industria B2B (minería, manufactura, energía)

### Confiabilidad del Sistema
- **Redundancia de 5 fuentes**: si un scraper falla, los otros compensan
- **Fallback de LLM**: DeepSeek → Haiku automático
- **Transparencia**: fuentes crudas visibles en la UI con scoring de confianza
- **Anti-alucinación**: Perplexity solo para enriquecimiento, temperatura 0.1

---

## 5. Estado Actual

- **Versión**: v1.3.0 (3 releases mayores en 3 días de desarrollo)
- **Despliegue**: Railway con auto-deploy desde main
- **Rendimiento**: Pipeline completo en 45-50 segundos
- **Madurez**: Battle-tested, operativo en producción
