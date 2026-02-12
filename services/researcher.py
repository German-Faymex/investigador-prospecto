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


class ResearchService:
    def __init__(self):
        self.orchestrator = ScraperOrchestrator()
        self.verifier = Verifier()
        self.llm = LLMClient()

    async def investigate(self, name: str, company: str, role: str = "") -> ResearchResult:
        """Pipeline completo: scrape → verify → LLM analysis → structured result."""
        result = ResearchResult()

        try:
            # 1. Scrape all sources in parallel
            print(f"[Research] Investigando: {name} @ {company}")
            items = await self.orchestrator.search_all(name, company, role)

            if not items:
                result.error = "No se encontraron resultados en ninguna fuente"
                result.score = 0
                return result

            # 2. Guardar fuentes raw
            result.raw_sources = [
                {"url": it.url, "title": it.title, "source": it.source}
                for it in items if it.url
            ]

            # 3. Verificar hechos cruzando fuentes
            verified_facts = self.verifier.verify(items)

            if not verified_facts:
                result.error = "No se pudieron verificar datos suficientes"
                result.score = 5
                return result

            # 4. Construir contexto para el LLM (solo facts verificados/parciales)
            context = self._build_llm_context(name, company, role, verified_facts)

            # 5. Cargar prompt y enviar al LLM
            system_prompt = self._load_prompt("research_analyzer.md")
            llm_response = await self.llm.complete(system_prompt, context)
            result.llm_used = llm_response.model_used

            # 6. Parsear respuesta del LLM
            parsed = self._parse_llm_response(llm_response.content)
            if parsed:
                result.persona = parsed.get("persona", {})
                result.empresa = parsed.get("empresa", {})
                result.hallazgos = parsed.get("hallazgos", [])
                result.hallazgo_tipo = parsed.get("hallazgo_tipo", "D")
                result.score = parsed.get("score", 0)
                result.cargo_descubierto = parsed.get("cargo_descubierto", role)
            else:
                result.error = "No se pudo parsear la respuesta del LLM"
                result.score = 10

        except Exception as e:
            result.error = str(e)
            print(f"[Research] Error: {e}")

        return result

    def _build_llm_context(self, name: str, company: str, role: str, facts) -> str:
        """Construir el user prompt con los hechos verificados."""
        lines = [
            f"## Prospecto a investigar",
            f"- Nombre: {name}",
            f"- Empresa: {company}",
            f"- Cargo conocido: {role or 'No especificado'}",
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
