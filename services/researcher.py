"""Orquesta scraping + verificación + análisis LLM."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from scraper.orchestrator import ScraperOrchestrator
from scraper.base import ScrapedItem
from services.verifier import Verifier
from services.llm_client import LLMClient


PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class ResearchResult:
    persona: dict = field(default_factory=dict)
    empresa: dict = field(default_factory=dict)
    hallazgos: list[dict] = field(default_factory=list)
    hallazgo_tipo: str = "D"
    score: int = 0
    cargo_descubierto: str = ""
    llm_used: str = "unknown"
    error: Optional[str] = None
    raw_sources: list[dict] = field(default_factory=list)
    linkedin_search_url: str = ""
    location: str = ""


class ResearchService:
    def __init__(self):
        self.orchestrator = ScraperOrchestrator()
        self.verifier = Verifier()
        self.llm = LLMClient()

    async def investigate(self, name: str, company: str, role: str = "", location: str = "") -> ResearchResult:
        """Pipeline completo: scrape → verify → LLM analysis → structured result."""
        from scraper.linkedin import LinkedInScraper

        result = ResearchResult()
        result.linkedin_search_url = LinkedInScraper.build_search_url(name, company)
        result.location = location

        try:
            # 1. Scrape all sources in parallel
            print(f"[Research] Investigando: {name} @ {company}")
            items = await self.orchestrator.search_all(name, company, role, location)

            if items:
                # 2. Guardar fuentes raw
                result.raw_sources = [
                    {"url": it.url, "title": it.title, "source": it.source}
                    for it in items if it.url
                ]

                # 3. Verificar hechos cruzando fuentes
                verified_facts = self.verifier.verify(items)

                if verified_facts:
                    # 4. Construir contexto para el LLM con datos scrapeados
                    corporate_domain = self.orchestrator.discovered_domain
                    context = self._build_llm_context(name, company, role, verified_facts, location, corporate_domain)
                    system_prompt = self._load_prompt("research_analyzer.md")
                    llm_response = await self.llm.complete(system_prompt, context)
                    result.llm_used = llm_response.model_used

                    parsed = self._parse_llm_response(llm_response.content)
                    if parsed:
                        result.persona = parsed.get("persona", {})
                        result.empresa = parsed.get("empresa", {})
                        result.hallazgos = parsed.get("hallazgos", [])
                        result.hallazgo_tipo = parsed.get("hallazgo_tipo", "D")
                        result.score = parsed.get("score", 0)
                        result.cargo_descubierto = parsed.get("cargo_descubierto", role)
                        # Asegurar que sitio_web viene del dominio descubierto
                        if corporate_domain and not result.empresa.get("sitio_web"):
                            result.empresa["sitio_web"] = corporate_domain
                        # Enriquecer campos vacíos con datos de Perplexity y LinkedIn
                        self._enrich_from_perplexity(result)
                        self._enrich_from_scraped_items(result, items)
                        return result

            # Fallback: si no hay datos de scraping, investigar directo con LLM
            print("[Research] Sin datos de scraping, usando LLM directo como fallback")
            result = await self._llm_direct_research(name, company, role, location)
            result.linkedin_search_url = LinkedInScraper.build_search_url(name, company)
            result.location = location

        except Exception as e:
            result.error = str(e)
            print(f"[Research] Error: {e}")

        return result

    async def _llm_direct_research(self, name: str, company: str, role: str = "", location: str = "") -> ResearchResult:
        """Fallback: investigar usando solo el conocimiento del LLM (sin scraping).

        IMPORTANTE: Este método solo usa conocimiento general del LLM, sin fuentes verificables.
        Los resultados se limitan a score <= 45 y hallazgo_tipo <= "C" para reflejar
        la baja confiabilidad de datos no verificados.
        """
        system_prompt = """Eres un asistente que ayuda a identificar informacion PUBLICA Y CONOCIDA sobre empresas y personas.

REGLAS ESTRICTAS - LEE CON ATENCION:

1. NUNCA inventes informacion. Si no sabes algo con CERTEZA, deja el campo vacio o escribe "No disponible".
2. NUNCA inventes noticias, contratos, montos, fechas, logros, titulos universitarios ni trayectorias profesionales.
3. NUNCA fabriques URLs de LinkedIn ni de sitios web.
4. Solo incluye informacion que sea PUBLICA, CONOCIDA y que puedas afirmar con ALTA CERTEZA.
5. Para personas que NO son figuras publicas conocidas, lo correcto es devolver campos vacios.
6. Para empresas pequenas o poco conocidas, solo incluye lo que sepas con certeza (ej: industria general, pais).
7. El score MAXIMO que puedes asignar es 45. El hallazgo_tipo MAXIMO es "C".
8. Todos los hallazgos deben tener "sources": [] y "confidence": "unverified".

Responde SIEMPRE en formato JSON con esta estructura exacta:

{
    "persona": {
        "nombre": "Nombre proporcionado",
        "cargo": "Solo si lo conoces con certeza, sino 'No disponible'",
        "empresa": "Empresa proporcionada",
        "linkedin": "",
        "trayectoria": "Solo si es una figura publica conocida, sino 'No disponible'",
        "educacion": "Solo si es informacion publica verificable, sino 'No disponible'",
        "ubicacion": "Solo si lo sabes con certeza",
        "intereses": "No disponible",
        "logros_recientes": [],
        "experiencia_previa": []
    },
    "empresa": {
        "nombre": "Nombre de la empresa",
        "industria": "Industria/sector si es conocido",
        "descripcion": "Solo informacion publica y verificable sobre la empresa",
        "productos_servicios": [],
        "noticias_recientes": [],
        "desafios_sector": [],
        "competidores": [],
        "ubicacion": "Solo si lo sabes con certeza",
        "presencia": "",
        "sitio_web": "Solo si conoces la URL real"
    },
    "hallazgos": [
        {
            "content": "Solo hechos verificables y publicamente conocidos",
            "tipo": "C|D",
            "sources": [],
            "confidence": "unverified"
        }
    ],
    "hallazgo_tipo": "C|D",
    "score": 20,
    "cargo_descubierto": ""
}

RECUERDA: Es MUCHO mejor devolver campos vacios que inventar informacion falsa.
Si la persona no es una figura publica conocida, devuelve la mayoria de campos como "No disponible" con score bajo."""

        location_instruction = ""
        if location:
            location_instruction = f"\n- Ubicacion: {location}"

        user_prompt = f"""Proporciona SOLO informacion que conozcas con CERTEZA sobre:

- Nombre: {name}
- Empresa: {company}
- Cargo: {role or 'No especificado'}{location_instruction}

IMPORTANTE: Si no conoces a esta persona o empresa, devuelve campos vacios con score bajo (10-20).
NO inventes nada. Responde SOLO con el JSON estructurado."""

        llm_response = await self.llm.complete(system_prompt, user_prompt)
        result = ResearchResult(llm_used=f"{llm_response.model_used} (sin verificar)")

        parsed = self._parse_llm_response(llm_response.content)
        if parsed:
            result.persona = parsed.get("persona", {})
            result.empresa = parsed.get("empresa", {})
            result.hallazgos = parsed.get("hallazgos", [])

            # Forzar limites: sin scraping, nunca puede ser tipo A/B ni score > 45
            raw_tipo = parsed.get("hallazgo_tipo", "D")
            result.hallazgo_tipo = raw_tipo if raw_tipo in ("C", "D") else "C"
            result.score = min(parsed.get("score", 0), 45)

            # Marcar todos los hallazgos como no verificados
            for h in result.hallazgos:
                h["confidence"] = "unverified"
                h["sources"] = []
                if h.get("tipo") in ("A", "B"):
                    h["tipo"] = "C"

            result.cargo_descubierto = parsed.get("cargo_descubierto", role)
        else:
            result.error = "No se pudo parsear la respuesta del LLM"
            result.score = 10

        return result

    def _build_llm_context(self, name: str, company: str, role: str, facts, location: str = "", corporate_domain: str = "") -> str:
        """Construir el user prompt con los hechos verificados."""
        lines = [
            f"## Prospecto a investigar",
            f"- Nombre: {name}",
            f"- Empresa: {company}",
            f"- Cargo conocido: {role or 'No especificado'}",
            f"- Ubicacion: {location or 'No especificada'}",
        ]
        if corporate_domain:
            lines.append(f"- Sitio web corporativo: {corporate_domain}")
        lines.extend(["", "## Datos recopilados y verificados", ""])

        for i, fact in enumerate(facts, 1):
            if fact.confidence == "discarded":
                continue
            emoji = "✅" if fact.confidence == "verified" else "⚠️"
            sources_str = ", ".join(fact.source_names)
            urls_str = " | ".join(fact.sources[:3])
            lines.append(f"{emoji} **Dato {i}** [{fact.confidence}] (fuentes: {sources_str})")
            lines.append(f"   {fact.content}")
            if urls_str:
                lines.append(f"   URLs: {urls_str}")
            lines.append("")

        lines.append("Analiza estos datos y responde en el formato JSON especificado.")
        return "\n".join(lines)

    def _load_prompt(self, filename: str) -> str:
        """Cargar prompt desde archivo .md."""
        path = PROMPTS_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        print(f"[Research] Prompt no encontrado: {path}")
        return ""

    def _enrich_from_perplexity(self, result: ResearchResult):
        """Enriquecer campos vacíos del resultado con datos estructurados de Perplexity."""
        pplx_data = self.orchestrator.perplexity_scraper.last_result
        if not pplx_data:
            return

        # Mapeo de campos Perplexity → campos del resultado
        pplx_persona = pplx_data.get("persona", {})
        pplx_empresa = pplx_data.get("empresa", {})

        # Enriquecer persona
        persona = result.persona
        _fill = self._fill_if_empty

        _fill(persona, "trayectoria", pplx_persona.get("trayectoria", ""))
        _fill(persona, "educacion", pplx_persona.get("educacion", ""))
        _fill(persona, "cargo", pplx_persona.get("cargo_actual", ""))
        _fill(persona, "linkedin", pplx_persona.get("linkedin_url", ""))
        _fill(persona, "ubicacion", pplx_persona.get("ubicacion", ""))

        if not persona.get("logros_recientes") and pplx_persona.get("logros_recientes"):
            persona["logros_recientes"] = pplx_persona["logros_recientes"]
        if not persona.get("experiencia_previa") and pplx_persona.get("experiencia_previa"):
            persona["experiencia_previa"] = pplx_persona["experiencia_previa"]

        # Enriquecer empresa
        empresa = result.empresa
        _fill(empresa, "industria", pplx_empresa.get("industria", ""))
        _fill(empresa, "descripcion", pplx_empresa.get("descripcion", ""))
        _fill(empresa, "ubicacion", pplx_empresa.get("ubicacion", ""))
        _fill(empresa, "sitio_web", pplx_empresa.get("sitio_web", ""))
        _fill(empresa, "tamano_empleados", pplx_empresa.get("tamano_empleados", ""))
        _fill(empresa, "presencia", pplx_empresa.get("presencia", ""))

        if not empresa.get("productos_servicios") and pplx_empresa.get("productos_servicios"):
            empresa["productos_servicios"] = pplx_empresa["productos_servicios"]
        if not empresa.get("noticias_recientes") and pplx_empresa.get("noticias_recientes"):
            empresa["noticias_recientes"] = pplx_empresa["noticias_recientes"]
        if not empresa.get("competidores") and pplx_empresa.get("competidores"):
            empresa["competidores"] = pplx_empresa["competidores"]
        if not empresa.get("desafios_sector") and pplx_empresa.get("desafios_sector"):
            empresa["desafios_sector"] = pplx_empresa["desafios_sector"]

        # NOTA: NO enriquecemos hallazgos desde Perplexity.
        # Los hallazgos/noticias de Perplexity son muy propensos a alucinación
        # (URLs inventadas, noticias falsas, confusión de empresas homónimas).
        # Solo usamos datos de persona y empresa que son más confiables.

        # Si cargo_descubierto está vacío, usar el de Perplexity
        if not result.cargo_descubierto or result.cargo_descubierto in ("", "No disponible", "No especificado"):
            pplx_cargo = pplx_persona.get("cargo_actual", "")
            if pplx_cargo and pplx_cargo not in ("No disponible", "No verificado"):
                result.cargo_descubierto = pplx_cargo

        print(f"[Research] Resultado enriquecido con datos de Perplexity")

    def _enrich_from_scraped_items(self, result: ResearchResult, items: list[ScrapedItem]):
        """Enriquecer campos vacíos de persona con datos extraídos de snippets de LinkedIn.

        Cuando LinkedIn bloquea acceso directo (authwall), los buscadores aún devuelven
        snippets con datos valiosos: headline, educación, ubicación. Este método los parsea
        para llenar campos que quedaron como 'No disponible'.
        """
        # Recopilar texto de items que contienen datos de LinkedIn
        linkedin_texts = []
        for item in items:
            is_linkedin = (
                "linkedin.com" in item.url
                or item.source == "linkedin"
                or item.source == "perplexity_persona"
            )
            if is_linkedin and (item.title or item.snippet):
                linkedin_texts.append(f"{item.title} {item.snippet}")

        # También buscar items de Google/DDG que tengan URLs de LinkedIn
        for item in items:
            if item.source in ("google_search", "duckduckgo") and "linkedin.com" in item.url:
                linkedin_texts.append(f"{item.title} {item.snippet}")

        if not linkedin_texts:
            return

        combined = " | ".join(linkedin_texts)
        persona = result.persona
        _fill = self._fill_if_empty

        # Extraer educación de snippets de LinkedIn
        education = self._extract_education(combined)
        if education:
            _fill(persona, "educacion", education)

        # Extraer ubicación de snippets de LinkedIn
        location = self._extract_location(combined)
        if location:
            _fill(persona, "ubicacion", location)

        # Extraer trayectoria/headline de títulos LinkedIn
        trayectoria = self._extract_trayectoria(linkedin_texts, result.persona.get("nombre", ""))
        if trayectoria:
            _fill(persona, "trayectoria", trayectoria)

        if any(field_filled := [education, location, trayectoria]):
            print(f"[Research] Enriquecido con datos de LinkedIn snippets: "
                  f"edu={'✓' if education else '✗'} "
                  f"loc={'✓' if location else '✗'} "
                  f"tray={'✓' if trayectoria else '✗'}")

    @staticmethod
    def _extract_education(text: str) -> str:
        """Extraer información de educación de texto de LinkedIn."""
        # Patrones comunes de educación en LinkedIn
        education_patterns = [
            # "Educación: Universidad de Atacama" (formato Perplexity/LinkedIn enriquecido)
            r"[Ee]ducaci[oó]n:\s*(.+?)(?:\||$|\.|Ubicaci[oó]n|Logros|Cargo|Empresa|Trayectoria)",
            # "alumniOf" / universidades conocidas
            r"(?:Universidad|Pontificia|Instituto|Escuela|Facultad|UTFSM|USACH|U\. de|PUC|UC)[^|.]*(?:de\s+\w+[^|.]*)?",
            # Grados académicos
            r"(?:Ingenier[oa]\s+Civil[^|.]*|MBA[^|.]*|Máster[^|.]*|Master[^|.]*|Magíster[^|.]*|Doctorad[oa][^|.]*|Licenciad[oa][^|.]*)",
        ]

        results = []
        for pattern in education_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                clean = match.strip().strip("|.,; ")
                if clean and len(clean) > 3 and clean not in results:
                    results.append(clean)

        if results:
            # Deduplicar y combinar
            return ". ".join(results[:3])
        return ""

    @staticmethod
    def _extract_location(text: str) -> str:
        """Extraer ubicación de texto de LinkedIn."""
        # Patrones de ubicación
        location_patterns = [
            # "Ubicación: Santiago, Chile" (formato enriquecido)
            r"[Uu]bicaci[oó]n:\s*([^|.]+?)(?:\||$|\.)",
            # "Chile" o "Santiago, Chile" al final o entre separadores
            r"(?:^|\||\.\s+)((?:Santiago|Antofagasta|Calama|Copiap[oó]|La Serena|Vi[ñn]a del Mar|Valpara[ií]so|Concepci[oó]n|Temuco|Rancagua|Iquique|Arica|Puerto Montt|Punta Arenas)(?:\s*,\s*(?:Chile|Regi[oó]n\s+[^|.]+))?)",
            # País solo
            r"(?:^|\||\.\s+)(Chile)(?:\s*\||$|\.)",
        ]

        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                loc = match.group(1).strip().strip("|.,; ")
                if loc and len(loc) >= 3:
                    return loc

        return ""

    @staticmethod
    def _extract_trayectoria(linkedin_texts: list[str], name: str) -> str:
        """Extraer resumen de trayectoria/headline de títulos LinkedIn.

        LinkedIn titles have format: "Name - Headline | LinkedIn"
        LinkedIn snippets often contain the full headline with titles and education.
        """
        headlines = []
        name_parts = name.lower().split()

        for text in linkedin_texts:
            # Patrón de título LinkedIn: "Nombre - Headline | LinkedIn"
            # También: "Nombre - Headline - Empresa | LinkedIn"
            match = re.search(
                r"(?:" + re.escape(name) + r"|" + r"\s+".join(re.escape(p) for p in name_parts) + r")\s*[-–—]\s*(.+?)(?:\s*\|\s*LinkedIn|\s*$)",
                text,
                re.IGNORECASE,
            )
            if match:
                headline = match.group(1).strip().strip("| ")
                if headline and len(headline) > 5:
                    headlines.append(headline)

            # Patrón alternativo: "Trayectoria: ..." (formato Perplexity)
            match2 = re.search(r"Trayectoria:\s*(.+?)(?:\||$|Educaci[oó]n|Logros)", text, re.IGNORECASE)
            if match2:
                tray = match2.group(1).strip().strip("|.,; ")
                if tray and len(tray) > 5 and tray not in ("No disponible",):
                    headlines.append(tray)

        if headlines:
            # Usar el headline más largo
            best = max(headlines, key=len)
            return best
        return ""

    @staticmethod
    def _fill_if_empty(d: dict, key: str, value: str):
        """Llenar un campo solo si está vacío o contiene 'No disponible'."""
        if not value or value in ("No disponible", "No verificado", "No verificada", "No determinada"):
            return
        current = d.get(key, "")
        if not current or current in ("No disponible", "No especificado", "No verificado", ""):
            d[key] = value

    def _parse_llm_response(self, text: str) -> Optional[dict]:
        """Extraer JSON de la respuesta del LLM."""
        # Intentar encontrar JSON en la respuesta
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            # Intentar encontrar primer { ... } completo
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                text = brace_match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[Research] Error parseando JSON: {e}")
            return None
