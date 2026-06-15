"""Tests de la resolución de entidades con LLM (mejora #1).

Capa primaria contra contaminación por homónimos: clasifica cada resultado de
búsqueda en prospecto/empresa/irrelevante antes del análisis. Con fallback a la
heurística `_is_relevant_item` si la llamada LLM falla o no parsea.
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from scraper.base import ScrapedItem
from services.researcher import ResearchService


def _svc(content=None, side_effect=None):
    svc = ResearchService.__new__(ResearchService)
    mock = AsyncMock()
    if side_effect is not None:
        mock.side_effect = side_effect
    else:
        mock.return_value = SimpleNamespace(content=content, model_used="mock")
    svc.llm = SimpleNamespace(complete=mock)
    return svc


def _classif(pairs):
    """pairs: lista de (indice, categoria) → JSON del schema."""
    return json.dumps({
        "clasificaciones": [
            {"indice": i, "categoria": c, "razon": "test"} for i, c in pairs
        ]
    })


# Items del caso Nadia: perfil propio + homónimo de California + corporate seguro
PROFILE = ScrapedItem(
    url="https://cl.linkedin.com/in/nadia-rl",
    title="Nadia Ramirez Lara - Ingeniera Industrial",
    snippet="Instituto Profesional ESUCOMEX. Valparaíso",
    source="linkedin",
)
HOMONYM = ScrapedItem(
    url="https://www.linkedin.com/in/nadia-pm",
    title="Nadia Ramirez - Program Manager - Microsoft",
    snippet="California State Polytechnic University-Pomona. San Jose",
    source="duckduckgo",
)
CORPORATE = ScrapedItem(
    url="https://desertking.com/about",
    title="Desert King",
    snippet="Productores de extractos de quillay y yucca",
    source="corporate",
)
PERPLEXITY = ScrapedItem(
    url="", title="Nadia - perfil", snippet="...", source="perplexity_persona",
)


class TestResolveEntitiesLLM:
    def _run(self, svc, items, name="Nadia Ramirez Lara", company="Desert King"):
        return asyncio.run(svc._resolve_entities(name, company, "", "", items))

    def test_homonimo_descartado_prospecto_y_safe_conservados(self):
        svc = _svc(_classif([(0, "prospecto"), (1, "irrelevante")]))
        result = self._run(svc, [PROFILE, HOMONYM, CORPORATE])
        urls = {it.url for it in result}
        assert HOMONYM.url not in urls          # homónimo descartado
        assert PROFILE.url in urls              # prospecto conservado
        assert CORPORATE.url in urls            # safe (corporate) intacto

    def test_corporate_no_se_envia_al_llm(self):
        # Solo los candidatos de búsqueda van en el prompt; corporate va aparte
        svc = _svc(_classif([(0, "prospecto"), (1, "irrelevante")]))
        self._run(svc, [PROFILE, HOMONYM, CORPORATE])
        user_prompt = svc.llm.complete.call_args.args[1]
        assert "desertking.com/about" not in user_prompt
        assert "nadia-rl" in user_prompt

    def test_sin_candidatos_no_llama_llm(self):
        svc = _svc(_classif([]))
        result = self._run(svc, [CORPORATE, PERPLEXITY])
        assert result == [CORPORATE, PERPLEXITY]
        svc.llm.complete.assert_not_called()

    def test_indice_omitido_se_conserva(self):
        # El LLM solo clasificó el idx 0; el idx 1 (omitido) se conserva
        svc = _svc(_classif([(0, "prospecto")]))
        result = self._run(svc, [PROFILE, HOMONYM])
        assert len(result) == 2

    def test_empresa_se_conserva(self):
        news = ScrapedItem(
            url="https://news.cl/x", title="Desert King expande planta",
            snippet="La empresa chilena invierte...", source="google_news",
        )
        svc = _svc(_classif([(0, "empresa")]))
        result = self._run(svc, [news])
        assert result == [news]


class TestResolveEntitiesFallback:
    def _run(self, svc, items):
        return asyncio.run(svc._resolve_entities("Juan Perez", "Acme", "", "", items))

    def _items(self):
        return [
            ScrapedItem(url="https://a", title="Juan Perez", snippet="gerente en Acme Corp", source="duckduckgo"),
            ScrapedItem(url="https://b", title="Juan Perez", snippet="otra persona empresa rival", source="duckduckgo"),
        ]

    def test_excepcion_cae_a_heuristica(self):
        svc = _svc(side_effect=RuntimeError("API down"))
        result = self._run(svc, self._items())
        urls = {it.url for it in result}
        assert "https://a" in urls       # menciona Acme → heurística lo mantiene
        assert "https://b" not in urls   # no menciona empresa → heurística lo descarta

    def test_json_invalido_cae_a_heuristica(self):
        svc = _svc(content="esto no es json valido")
        result = self._run(svc, self._items())
        urls = {it.url for it in result}
        assert "https://a" in urls
        assert "https://b" not in urls

    def test_clasificaciones_no_lista_cae_a_heuristica(self):
        svc = _svc(content=json.dumps({"clasificaciones": "no-es-lista"}))
        result = self._run(svc, self._items())
        assert {it.url for it in result} == {"https://a"}


class TestExtractorCleanup:
    """Limpieza de ruido pegado por snippets de LinkedIn sin puntuación."""

    def test_ubicacion_sin_conteo_de_contactos(self):
        loc = ResearchService._extract_location("Ubicación: Valparaíso 172 contactos en LinkedIn | otra cosa")
        assert loc == "Valparaíso"

    def test_educacion_sin_ubicacion_pegada(self):
        edu = ResearchService._extract_education(
            "Instituto Profesional ESUCOMEX Ubicación: Valparaíso 172 contactos"
        )
        assert "ESUCOMEX" in edu
        assert "Valpara" not in edu
        assert "contacto" not in edu.lower()

    def test_educacion_no_duplica_misma_institucion(self):
        # Caso real Nadia: el mismo instituto con el mismo ruido en dos
        # fragmentos del perfil colapsa tras el corte (dedup exacto)
        edu = ResearchService._extract_education(
            "Instituto Profesional ESUCOMEX Ubicación: Valparaíso | "
            "Instituto Profesional ESUCOMEX Ubicación: Valparaíso"
        )
        assert edu.count("ESUCOMEX") == 1
