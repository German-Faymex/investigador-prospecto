"""Genera emails SMTYKM personalizados."""
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from services.llm_client import LLMClient
from services.researcher import ResearchResult
from config.settings import get_settings

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


@dataclass
class EmailResult:
    subject: str
    body_html: str
    body_text: str
    reasoning: str


class EmailGenerator:
    def __init__(self):
        self.llm = LLMClient()
        self.settings = get_settings()

    async def generate(self, research: ResearchResult, sender_name: str = "", sender_company: str = "") -> EmailResult:
        """Generar email SMTYKM basado en resultados de investigación."""
        sender_name = sender_name or self.settings.app.sender_name
        sender_company = sender_company or self.settings.app.sender_company

        # Cargar prompts
        system_prompt = self._load_prompt("smtykm_system.md")
        email_template = self._load_prompt("email_generator.md")

        # Construir resumen de investigación
        research_summary = self._build_research_summary(research)

        # Mejor hallazgo para el gancho del email
        # Priorizar noticias recientes (tipo A) sobre datos generales
        hallazgo_desc = ""
        if research.hallazgos:
            best = self._pick_best_hallazgo(research.hallazgos)
            hallazgo_desc = best.get("content", "")

        # Fill template - tratar "No disponible" como vacío para evitar que el LLM lo use
        cargo_raw = research.cargo_descubierto or research.persona.get("cargo", "")
        cargo = "" if cargo_raw.lower().strip() in ("no disponible", "no encontrado", "no especificado") else cargo_raw

        user_prompt = email_template.replace("{nombre}", research.persona.get("nombre", ""))
        user_prompt = user_prompt.replace("{cargo}", cargo)
        user_prompt = user_prompt.replace("{empresa}", research.empresa.get("nombre", ""))
        user_prompt = user_prompt.replace("{industria}", research.empresa.get("industria", ""))
        user_prompt = user_prompt.replace("{research_summary}", research_summary)
        user_prompt = user_prompt.replace("{hallazgo_tipo}", research.hallazgo_tipo)
        user_prompt = user_prompt.replace("{hallazgo_descripcion}", hallazgo_desc)
        user_prompt = user_prompt.replace("{sender_name}", sender_name)
        user_prompt = user_prompt.replace("{sender_company}", sender_company)
        location = getattr(research, 'location', '') or ''
        user_prompt = user_prompt.replace("{location}", location)

        # Llamar al LLM
        llm_response = await self.llm.complete(system_prompt, user_prompt)

        # Parsear respuesta JSON
        parsed = self._parse_response(llm_response.content)
        if parsed:
            parsed = self._fix_email_closing(parsed, sender_name)
            return EmailResult(
                subject=parsed.get("asunto", ""),
                body_html=parsed.get("cuerpo_html", ""),
                body_text=parsed.get("cuerpo_texto", ""),
                reasoning=parsed.get("razonamiento", ""),
            )

        # Fallback si no se puede parsear
        return EmailResult(
            subject="",
            body_html="",
            body_text=llm_response.content,
            reasoning="No se pudo parsear la respuesta del LLM como JSON",
        )

    @staticmethod
    def _pick_best_hallazgo(hallazgos: list[dict]) -> dict:
        """Select the best hallazgo for the email hook.

        Priority: A (company news) > B (executive achievement) > C (industry trend) > D (general)
        Within the same tipo, prefer hallazgos with sources (verified).
        """
        tipo_priority = {"A": 0, "B": 1, "C": 2, "D": 3}

        def sort_key(h: dict) -> tuple:
            tipo = h.get("tipo", "D")
            has_sources = 1 if h.get("sources") else 0
            return (tipo_priority.get(tipo, 4), -has_sources)

        return min(hallazgos, key=sort_key)

    def _build_research_summary(self, research: ResearchResult) -> str:
        """Construir resumen legible de la investigación.

        Separa noticias recientes de otros hallazgos para que el LLM
        los identifique fácilmente como material para el gancho del email.
        """
        lines = []

        if research.persona:
            lines.append("### Persona")
            for key, val in research.persona.items():
                if val:
                    lines.append(f"- {key}: {val}")

        if research.empresa:
            lines.append("\n### Empresa")
            for key, val in research.empresa.items():
                if val:
                    lines.append(f"- {key}: {val}")

        # Separar noticias (tipo A) de otros hallazgos para que el LLM los priorice
        if research.hallazgos:
            news = [h for h in research.hallazgos if h.get("tipo") == "A"]
            other = [h for h in research.hallazgos if h.get("tipo") != "A"]

            if news:
                lines.append("\n### NOTICIAS RECIENTES DE LA EMPRESA (usar como gancho del email)")
                for h in news:
                    content = h.get("content", "")
                    sources = h.get("sources", [])
                    src_str = f" (fuente: {sources[0]})" if sources else ""
                    lines.append(f"- {content}{src_str}")

            if other:
                lines.append("\n### Otros hallazgos")
                for h in other:
                    tipo = h.get("tipo", "")
                    content = h.get("content", "")
                    lines.append(f"- [{tipo}] {content}")

        return "\n".join(lines)

    def _load_prompt(self, filename: str) -> str:
        """Cargar prompt desde archivo .md."""
        path = PROMPTS_DIR / filename
        if path.exists():
            return path.read_text(encoding="utf-8")
        print(f"[EmailGen] Prompt no encontrado: {path}")
        return ""

    def _fix_email_closing(self, parsed: dict, sender_name: str) -> dict:
        """Fix spacing if LLM omits linebreak in closing."""
        html = parsed.get("cuerpo_html", "")
        if html:
            parsed["cuerpo_html"] = re.sub(
                r"Quedo atento,\s*(?!<br)" + re.escape(sender_name),
                f"Quedo atento,<br>{sender_name}", html)
        text = parsed.get("cuerpo_texto", "")
        if text:
            parsed["cuerpo_texto"] = re.sub(
                r"Quedo atento,\s*(?!\n)" + re.escape(sender_name),
                f"Quedo atento,\n{sender_name}", text)
        return parsed

    def _parse_response(self, text: str) -> Optional[dict]:
        """Extraer JSON de la respuesta."""
        json_match = re.search(r"```json\s*(.*?)\s*```", text, re.DOTALL)
        if json_match:
            text = json_match.group(1)
        else:
            brace_match = re.search(r"\{.*\}", text, re.DOTALL)
            if brace_match:
                text = brace_match.group(0)

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
