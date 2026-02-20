"""Scraper que usa Perplexity API (sonar-pro) para búsqueda web real."""
import json
from datetime import datetime, timedelta

import httpx

from scraper.base import BaseScraper, ScrapedItem


class PerplexityScraper(BaseScraper):
    """Busca información sobre prospectos usando Perplexity sonar-pro.

    IMPORTANTE: Perplexity tiende a alucinar noticias, URLs y datos sobre
    personas poco conocidas. Por eso:
    - Solo generamos ScrapedItems para persona y empresa (datos estructurados)
    - NO generamos items de hallazgos/noticias (demasiado propensos a ser falsos)
    - Las URLs de Perplexity NO se usan (frecuentemente son fabricadas/404)
    - Los datos de persona/empresa se usan para enriquecimiento post-LLM
    """

    API_URL = "https://api.perplexity.ai/chat/completions"
    MODEL = "sonar-pro"

    def __init__(self):
        super().__init__()
        self.last_result: dict | None = None  # Datos estructurados de la última búsqueda

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        self.last_result = None
        api_key = self.settings.perplexity_api_key
        if not api_key:
            return []

        today = datetime.now()
        six_months_ago = today - timedelta(days=180)
        date_limit = six_months_ago.strftime("%B %Y")
        current_date = today.strftime("%d de %B de %Y")

        system_prompt = (
            "Eres un investigador B2B. Tu tarea es buscar información REAL y VERIFICABLE.\n\n"
            "REGLAS ANTI-ALUCINACIÓN (CRÍTICAS - LEER CON ATENCIÓN):\n"
            "1. NUNCA inventes información. Si no encuentras datos reales, deja el campo vacío ''.\n"
            "2. NUNCA fabriques URLs. Si no tienes una URL REAL que hayas encontrado, deja el campo vacío.\n"
            "3. NUNCA inventes noticias, eventos, conferencias, montos de inversión ni proyectos.\n"
            "4. Si no encuentras información sobre la PERSONA, devuelve persona con campos vacíos.\n"
            "5. CUIDADO con empresas homónimas: verifica que la empresa encontrada sea la CORRECTA.\n"
            "   - Verifica país, industria y contexto. Si hay ambigüedad, indica cuál empresa encontraste.\n"
            "6. El campo 'hallazgos' SOLO debe contener noticias que REALMENTE existan con URLs REALES.\n"
            "   Si no encuentras noticias reales, devuelve 'hallazgos': []\n"
            "7. Es MIL VECES mejor devolver campos vacíos que inventar datos falsos.\n\n"
            f"FECHA ACTUAL: {current_date}.\n"
            f"Solo información de los últimos 6 meses (desde {date_limit}).\n\n"
            "Responde en JSON con esta estructura:\n"
            "{\n"
            '  "persona": {\n'
            '    "nombre_completo": "", "cargo_actual": "", "empresa_actual": "",\n'
            '    "linkedin_url": "", "trayectoria": "", "educacion": "",\n'
            '    "ubicacion": "", "logros_recientes": []\n'
            "  },\n"
            '  "empresa": {\n'
            '    "nombre": "", "industria": "", "descripcion": "",\n'
            '    "productos_servicios": [], "tamano_empleados": "",\n'
            '    "ubicacion": "", "sitio_web": "",\n'
            '    "desafios_sector": [], "competidores": [], "presencia": ""\n'
            "  },\n"
            '  "hallazgos": []\n'
            "}"
        )

        location_part = f" en {location}" if location else ""
        role_part = f" ({role})" if role else ""
        user_prompt = (
            f"Investiga a {name}{role_part} de la empresa {company}{location_part}.\n\n"
            f"Busca ESPECÍFICAMENTE:\n"
            f"1. El perfil de LinkedIn de {name} - busca su headline, experiencia laboral, "
            f"educación universitaria, ubicación geográfica (ciudad/país)\n"
            f"2. Si no encuentras LinkedIn, busca cualquier perfil público con su trayectoria "
            f"profesional, formación académica y ubicación\n"
            f"3. Información de {company}: industria, productos/servicios, tamaño (empleados), sitio web, "
            f"descripción del negocio, operaciones principales, competidores, presencia geográfica, "
            f"desafíos del sector\n\n"
            f"CAMPOS PRIORITARIOS para la persona:\n"
            f"- educacion: nombre de universidad/institución y título/carrera obtenida\n"
            f"- ubicacion: ciudad y país donde trabaja o reside\n"
            f"- trayectoria: resumen de su carrera profesional y cargos anteriores\n"
            f"- cargo_actual: su puesto actual en {company}\n\n"
            f"IMPORTANTE: {company} puede tener homónimos en otros países. "
            f"Asegúrate de que la información corresponda a la empresa correcta"
            f"{location_part}.\n"
            f"Si no encuentras información verificable, devuelve campos vacíos. "
            f"NO inventes datos ni URLs."
        )

        try:
            async with httpx.AsyncClient(timeout=25) as client:
                response = await client.post(
                    self.API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.MODEL,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.1,
                        "max_tokens": 4096,
                    },
                )
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            items = self._parse_response(content, name, company)
            return items

        except Exception as e:
            print(f"[PerplexityScraper] Error: {e}")
            return []

    def _parse_response(self, content: str, name: str, company: str) -> list[ScrapedItem]:
        """Parsea la respuesta JSON de Perplexity en ScrapedItems.

        Solo genera items para persona y empresa. Los hallazgos/noticias
        de Perplexity se IGNORAN porque son muy propensos a alucinación
        (URLs inventadas, eventos falsos, confusión de empresas homónimas).
        """
        try:
            clean = content
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]

            data = json.loads(clean.strip())
        except (json.JSONDecodeError, IndexError):
            return []

        # Guardar datos estructurados para enriquecimiento directo
        # (pero sin hallazgos — son poco confiables)
        safe_data = {
            "persona": data.get("persona", {}),
            "empresa": data.get("empresa", {}),
        }
        self.last_result = safe_data

        items = []

        # Item de persona — sin URL (las URLs de Perplexity suelen ser fabricadas)
        persona = data.get("persona", {})
        if persona:
            parts = []
            if persona.get("cargo_actual"):
                parts.append(f"Cargo: {persona['cargo_actual']}")
            if persona.get("empresa_actual"):
                parts.append(f"Empresa: {persona['empresa_actual']}")
            if persona.get("trayectoria"):
                parts.append(f"Trayectoria: {persona['trayectoria']}")
            if persona.get("educacion"):
                parts.append(f"Educación: {persona['educacion']}")
            if persona.get("ubicacion"):
                parts.append(f"Ubicación: {persona['ubicacion']}")
            if persona.get("logros_recientes"):
                logros = [l for l in persona["logros_recientes"] if l]
                if logros:
                    parts.append(f"Logros: {'; '.join(logros[:3])}")

            if parts:
                items.append(ScrapedItem(
                    url="",  # No usar URLs de Perplexity — frecuentemente fabricadas
                    title=f"{persona.get('nombre_completo', name)} - Perfil profesional",
                    snippet=". ".join(parts),
                    source="perplexity_persona",
                ))

        # Item de empresa — sin URL (usar dominio del corporate scraper en su lugar)
        empresa = data.get("empresa", {})
        if empresa:
            parts = []
            if empresa.get("industria"):
                parts.append(f"Industria: {empresa['industria']}")
            if empresa.get("descripcion"):
                parts.append(empresa["descripcion"])
            if empresa.get("productos_servicios"):
                parts.append(f"Productos/Servicios: {', '.join(empresa['productos_servicios'][:5])}")
            if empresa.get("tamano_empleados"):
                parts.append(f"Tamaño: {empresa['tamano_empleados']}")
            if empresa.get("ubicacion"):
                parts.append(f"Ubicación: {empresa['ubicacion']}")
            if empresa.get("presencia"):
                parts.append(f"Presencia: {empresa['presencia']}")
            if empresa.get("competidores"):
                parts.append(f"Competidores: {', '.join(empresa['competidores'][:5])}")
            if empresa.get("desafios_sector"):
                parts.append(f"Desafíos: {', '.join(empresa['desafios_sector'][:3])}")

            if parts:
                items.append(ScrapedItem(
                    url="",  # No usar URLs de Perplexity
                    title=f"{empresa.get('nombre', company)} - Información corporativa",
                    snippet=". ".join(parts),
                    source="perplexity_empresa",
                ))

        # NOTA: NO creamos items de hallazgos/noticias de Perplexity.
        # Son la fuente principal de alucinación (URLs inventadas,
        # noticias falsas, confusión con empresas homónimas).

        return items
