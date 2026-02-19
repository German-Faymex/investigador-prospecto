"""Orquesta scraping + verificación + análisis LLM."""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from scraper.orchestrator import ScraperOrchestrator
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
                    context = self._build_llm_context(name, company, role, verified_facts, location)
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

    def _build_llm_context(self, name: str, company: str, role: str, facts, location: str = "") -> str:
        """Construir el user prompt con los hechos verificados."""
        lines = [
            f"## Prospecto a investigar",
            f"- Nombre: {name}",
            f"- Empresa: {company}",
            f"- Cargo conocido: {role or 'No especificado'}",
            f"- Ubicacion: {location or 'No especificada'}",
            "",
            "## Datos recopilados y verificados",
            "",
        ]

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
