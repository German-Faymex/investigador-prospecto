"""Regresión caso Nadia (11-jun-2026): el filtro anti-homónimos descartaba el
perfil de LinkedIn de la PROPIA persona investigada cuando el snippet de DDG
no mencionaba la empresa (su headline no la incluye), perdiendo educación y
ubicación. El item del LinkedIn scraper viene de una búsqueda ya acotada por
empresa, así que basta el nombre completo para conservarlo."""

from scraper.base import ScrapedItem
from services.researcher import ResearchService, ResearchResult


def _nadia_item(source="linkedin"):
    # Snippet real del caso: headline sin mención a la empresa + datos LinkedIn
    return ScrapedItem(
        url="https://cl.linkedin.com/in/nadia-ramirez-lara",
        title="Nadia Ramirez Lara - Ingeniera Industrial | Certificada en Lean six sigma",
        snippet="Educación: Instituto Profesional ESUCOMEX. Ubicación: Valparaíso, Chile",
        source=source,
    )


class TestTextMentionsFullName:
    def test_nombre_completo_presente(self):
        assert ResearchService._text_mentions_full_name(
            "nadia ramirez lara - ingeniera industrial", "nadia ramirez lara"
        )

    def test_nombre_incompleto_no_matchea(self):
        # Solo apellido coincide → homónimo potencial, no aceptar
        assert not ResearchService._text_mentions_full_name(
            "miguel ramirez - supervisor de producción - eaton", "nadia ramirez lara"
        )

    def test_orden_distinto_si_matchea(self):
        assert ResearchService._text_mentions_full_name(
            "perfil de lara, nadia ramirez en linkedin", "nadia ramirez lara"
        )

    def test_nombre_vacio_no_matchea(self):
        assert not ResearchService._text_mentions_full_name("cualquier texto", "")


class TestEnrichmentOwnProfile:
    def _run(self, item) -> ResearchResult:
        svc = ResearchService.__new__(ResearchService)  # sin __init__ (no red)
        r = ResearchResult()
        r.persona = {"nombre": "Nadia Ramirez Lara"}
        r.empresa = {"nombre": "Desert King"}
        ResearchService._enrich_from_scraped_items(svc, r, [item])
        return r

    def test_perfil_propio_sin_mencion_de_empresa_se_usa(self):
        # El caso del bug: headline no menciona "Desert King" pero es SU perfil
        r = self._run(_nadia_item(source="linkedin"))
        assert "ESUCOMEX" in r.persona.get("educacion", "")
        assert "Valparaíso" in r.persona.get("ubicacion", "")

    def test_homonimo_sin_empresa_sigue_descartado(self):
        item = ScrapedItem(
            url="https://pe.linkedin.com/in/otra-persona",
            title="Gumercindo Diaz Ramirez - SUPERVISOR DE PRODUCCION - Spectrum",
            snippet="Educación: Universidad de Lima. Ubicación: Lima, Perú",
            source="linkedin",
        )
        r = self._run(item)
        assert r.persona.get("educacion", "") == ""
        assert r.persona.get("ubicacion", "") == ""

    def test_item_generico_ddg_sigue_exigiendo_empresa(self):
        # La excepción es solo para items del LinkedIn scraper (source=linkedin)
        r = self._run(_nadia_item(source="duckduckgo"))
        assert r.persona.get("educacion", "") == ""
