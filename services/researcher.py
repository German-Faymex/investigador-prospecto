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
        """Fallback: investigar usando solo el conocimiento del LLM (sin scraping)."""
        from datetime import datetime, timedelta

        today = datetime.now()
        six_months_ago = today - timedelta(days=180)
        current_date = today.strftime("%d de %B de %Y")
        date_limit = six_months_ago.strftime("%B %Y")

        system_prompt = f"""Eres un investigador experto en prospeccion B2B para Faymex, empresa chilena de suministros industriales.
Tu tarea es investigar al prospecto usando tu conocimiento y extraer informacion ESPECIFICA y ACCIONABLE
para personalizar un email de ventas.

FECHA ACTUAL: {current_date}

CONTEXTO DE NEGOCIO - FAYMEX:
- Servicios: suministros industriales, repuestos criticos, stock local, consignacion
- Industrias clave: Mineria (cobre), Energia, Petroleo y Gas, Manufactura
- Clientes de referencia: CODELCO, Anglo American, Altonorte, ENAP
- Ventaja: stock local que evita importaciones de 8-12 semanas

QUE BUSCAR (en orden de prioridad):
1. PROYECTOS NUEVOS: Nueva planta, expansion, paradas programadas, inversiones
2. NOTICIAS RECIENTES: Contratos ganados, nuevas operaciones, crecimiento
3. LOGROS DEL EJECUTIVO: Ascensos recientes, publicaciones, premios
4. DESAFIOS: Problemas de mantenimiento, disponibilidad de equipos

RESTRICCION DE TIEMPO:
- SOLO informacion de los ULTIMOS 6 MESES (desde {date_limit})
- Si la informacion es antigua o generica, asigna hallazgo_tipo="D"

Responde SIEMPRE en formato JSON con esta estructura exacta. IMPORTANTE: se DETALLADO y EXTENSO en cada campo, no resumas.

{{
    "persona": {{
        "nombre": "Nombre completo del prospecto",
        "cargo": "Cargo actual completo con area de responsabilidad",
        "empresa": "Empresa actual",
        "linkedin": "URL de LinkedIn si la conoces (formato: https://linkedin.com/in/...)",
        "trayectoria": "Descripcion DETALLADA de su trayectoria profesional: anos de experiencia, empresas anteriores, roles anteriores, especializaciones. Minimo 3-4 oraciones.",
        "educacion": "Titulo profesional, universidad, postgrados si los tiene",
        "ubicacion": "Ciudad y pais donde trabaja",
        "intereses": "Areas de interes profesional, temas en los que se especializa",
        "logros_recientes": ["Logro 1 con detalle", "Logro 2 con detalle"],
        "experiencia_previa": ["Empresa anterior 1 - Cargo - Periodo", "Empresa anterior 2 - Cargo - Periodo"]
    }},
    "empresa": {{
        "nombre": "Nombre completo de la empresa",
        "industria": "Industria/sector especifico",
        "descripcion": "Descripcion DETALLADA de la empresa: que hace, desde cuando opera, que tan grande es, cual es su posicion en el mercado. Minimo 3-4 oraciones.",
        "productos_servicios": ["Producto/servicio principal 1", "Producto/servicio 2", "Producto/servicio 3"],
        "noticias_recientes": ["Noticia reciente 1 con fecha y detalle", "Noticia reciente 2 con fecha y detalle"],
        "desafios_sector": ["Desafio 1 especifico del sector con contexto", "Desafio 2 con contexto"],
        "competidores": ["Competidor 1", "Competidor 2"],
        "ubicacion": "Sede principal y presencia geografica",
        "presencia": "Paises o regiones donde opera",
        "sitio_web": "URL del sitio web oficial"
    }},
    "hallazgos": [
        {{
            "content": "Hallazgo ESPECIFICO con datos concretos, cifras, fechas y contexto. Debe ser una oracion completa y detallada.",
            "tipo": "A|B|C|D",
            "sources": [],
            "confidence": "partial"
        }}
    ],
    "hallazgo_tipo": "A|B|C|D",
    "score": 50,
    "cargo_descubierto": "Cargo descubierto si no fue proporcionado"
}}

IMPORTANTE: No dejes campos vacios si puedes inferir la informacion. Se extenso y detallado en las descripciones.

REGLAS DE SCORE:
- Score 80-100: Info de los ultimos 3 meses, muy especifica
- Score 60-79: Info de 3-6 meses, relevante
- Score 40-59: Info generica pero actual
- Score 0-39: Info desactualizada o no encontrada

Si no tienes informacion especifica, se honesto y asigna hallazgo_tipo="D" con score bajo."""

        location_instruction = ""
        if location:
            location_instruction = f"\n6. PRIORIZA noticias e informacion relevante para la region de {location}. Penaliza hallazgos de regiones distintas."

        user_prompt = f"""Investiga al siguiente prospecto usando tu conocimiento:

PROSPECTO:
- Nombre: {name}
- Cargo: {role or 'No especificado'}
- Empresa: {company}
- Ubicacion: {location or 'No especificada'}

INSTRUCCIONES:
1. Busca en tu conocimiento informacion ESPECIFICA sobre esta persona y empresa
2. Prioriza noticias de inversion, expansion o nuevos proyectos
3. Si conoces algun logro del ejecutivo, mencionalo
4. Los hallazgos deben tener DATOS CONCRETOS, no generalidades
5. Si no tienes informacion especifica, se honesto y asigna hallazgo_tipo="D" con score bajo{location_instruction}

Responde SOLO con el JSON estructurado, sin texto adicional."""

        llm_response = await self.llm.complete(system_prompt, user_prompt)
        result = ResearchResult(llm_used=f"{llm_response.model_used} (directo)")

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
