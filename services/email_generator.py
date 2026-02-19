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

        # Mejor hallazgo
        hallazgo_desc = ""
        if research.hallazgos:
            best = research.hallazgos[0]
            hallazgo_desc = best.get("content", "")

        # Fill template
        user_prompt = email_template.replace("{nombre}", research.persona.get("nombre", ""))
        user_prompt = user_prompt.replace("{cargo}", research.cargo_descubierto or research.persona.get("cargo", ""))
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

    def _build_research_summary(self, research: ResearchResult) -> str:
        """Construir resumen legible de la investigación."""
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

        if research.hallazgos:
            lines.append("\n### Hallazgos")
            for h in research.hallazgos:
                conf = h.get("confidence", "")
                tipo = h.get("tipo", "")
                content = h.get("content", "")
                lines.append(f"- [{tipo}] ({conf}) {content}")

        if research.raw_sources:
            lines.append("\n### Fuentes")
            for src in research.raw_sources[:5]:
                title = src.get('title', '')
                source = src.get('source', '')
                url = src.get('url', '')
                lines.append(f"- {source}: {title} ({url})" if title else f"- {source}: {url}")

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
