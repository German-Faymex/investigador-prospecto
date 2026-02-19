"""Scraper que usa Perplexity API (sonar-pro) para búsqueda web real."""
import json
from datetime import datetime, timedelta

import httpx

from scraper.base import BaseScraper, ScrapedItem


class PerplexityScraper(BaseScraper):
    """Busca información sobre prospectos usando Perplexity sonar-pro."""

    API_URL = "https://api.perplexity.ai/chat/completions"
    MODEL = "sonar-pro"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        api_key = self.settings.perplexity_api_key
        if not api_key:
            return []

        today = datetime.now()
        six_months_ago = today - timedelta(days=180)
        date_limit = six_months_ago.strftime("%B %Y")
        current_date = today.strftime("%d de %B de %Y")

        system_prompt = (
            "Eres un investigador experto en prospección B2B. "
            "Busca información RECIENTE y VERIFICABLE sobre el ejecutivo y su empresa. "
            f"FECHA ACTUAL: {current_date}. "
            f"Solo usa información de los últimos 6 meses (desde {date_limit}). "
            "Responde SIEMPRE en JSON con esta estructura exacta:\n"
            "{\n"
            '  "persona": {\n'
            '    "nombre_completo": "", "cargo_actual": "", "empresa_actual": "",\n'
            '    "linkedin_url": "", "trayectoria": "", "educacion": "",\n'
            '    "logros_recientes": []\n'
            "  },\n"
            '  "empresa": {\n'
            '    "nombre": "", "industria": "", "descripcion": "",\n'
            '    "productos_servicios": [], "tamano_empleados": "",\n'
            '    "ubicacion": "", "sitio_web": ""\n'
            "  },\n"
            '  "hallazgos": [\n'
            '    {"titulo": "", "resumen": "", "fecha": "", "url": ""}\n'
            "  ]\n"
            "}"
        )

        location_part = f" en {location}" if location else ""
        role_part = f" ({role})" if role else ""
        user_prompt = (
            f"Investiga a {name}{role_part} de la empresa {company}{location_part}.\n\n"
            f"Busca:\n"
            f"1. Perfil profesional de {name} en {company} (cargo, trayectoria, LinkedIn, educación)\n"
            f"2. Información de {company} (industria, productos/servicios, tamaño, ubicación, sitio web)\n"
            f"3. Noticias recientes de {company} o {name} (últimos 6 meses desde {date_limit})\n"
        )

        try:
            async with httpx.AsyncClient(timeout=30) as client:
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
                        "temperature": 0.2,
                        "max_tokens": 4096,
                    },
                )
                response.raise_for_status()

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return self._parse_response(content, name, company)

        except Exception as e:
            print(f"[PerplexityScraper] Error: {e}")
            return []

    def _parse_response(self, content: str, name: str, company: str) -> list[ScrapedItem]:
        """Parsea la respuesta JSON de Perplexity en ScrapedItems."""
        try:
            clean = content
            if "```json" in clean:
                clean = clean.split("```json")[1].split("```")[0]
            elif "```" in clean:
                clean = clean.split("```")[1].split("```")[0]

            data = json.loads(clean.strip())
        except (json.JSONDecodeError, IndexError):
            # Si no es JSON, devolver el texto crudo como un solo item
            if content.strip():
                return [ScrapedItem(
                    url="",
                    title=f"{name} en {company} - Perplexity",
                    snippet=content[:2000],
                    source="perplexity",
                )]
            return []

        items = []

        # Item de persona
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
            if persona.get("logros_recientes"):
                parts.append(f"Logros: {'; '.join(persona['logros_recientes'][:3])}")

            if parts:
                items.append(ScrapedItem(
                    url=persona.get("linkedin_url", ""),
                    title=f"{persona.get('nombre_completo', name)} - Perfil profesional",
                    snippet=". ".join(parts),
                    source="perplexity_persona",
                ))

        # Item de empresa
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

            if parts:
                items.append(ScrapedItem(
                    url=empresa.get("sitio_web", ""),
                    title=f"{empresa.get('nombre', company)} - Información corporativa",
                    snippet=". ".join(parts),
                    source="perplexity_empresa",
                ))

        # Items de hallazgos/noticias
        for hallazgo in data.get("hallazgos", []):
            titulo = hallazgo.get("titulo", "")
            resumen = hallazgo.get("resumen", "")
            if not titulo and not resumen:
                continue

            fecha = hallazgo.get("fecha", "")
            snippet = resumen
            if fecha:
                snippet = f"[{fecha}] {snippet}"

            items.append(ScrapedItem(
                url=hallazgo.get("url", ""),
                title=titulo or f"Hallazgo sobre {company}",
                snippet=snippet,
                source="perplexity_news",
                timestamp=fecha,
            ))

        return items
