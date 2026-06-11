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


class TestIsRelevantItem:
    """Regresión caso Nadia de California: items de homónimos llegaban al LLM
    como hechos y contaminaban educación/ubicación del prospecto real."""

    def _svc(self):
        return ResearchService.__new__(ResearchService)

    def test_homonimo_linkedin_excluido_del_analisis(self):
        # El caso real: perfil de otra Nadia Ramirez (sin 'Lara', sin empresa)
        it = ScrapedItem(
            url="https://www.linkedin.com/in/nadia-r",
            title="Nadia Ramirez - SEP | LinkedIn",
            snippet="California State Polytechnic University-Pomona · San Jose",
            source="linkedin",
        )
        assert not self._svc()._is_relevant_item(it, "nadia ramirez lara", "desert king")

    def test_perfil_propio_con_nombre_completo_pasa(self):
        assert self._svc()._is_relevant_item(_nadia_item(), "nadia ramirez lara", "desert king")

    def test_item_que_menciona_empresa_pasa(self):
        it = ScrapedItem(
            url="https://example.com/nota",
            title="Supervisores de Desert King",
            snippet="Nadia lidera el equipo de producción",
            source="duckduckgo",
        )
        assert self._svc()._is_relevant_item(it, "nadia ramirez lara", "desert king")

    def test_noticia_irrelevante_excluida(self):
        it = ScrapedItem(
            url="https://news.example.com/x",
            title="Noticias de minería",
            snippet="Producción de cobre sube en el norte",
            source="google_news",
        )
        assert not self._svc()._is_relevant_item(it, "nadia ramirez lara", "desert king")

    def test_corporate_y_perplexity_pasan_siempre(self):
        for source in ("corporate", "perplexity_persona", "perplexity_empresa"):
            it = ScrapedItem(url="https://x.com", title="t", snippet="s", source=source)
            assert self._svc()._is_relevant_item(it, "nadia ramirez lara", "desert king")


class TestPerplexityHomonymGate:
    """Regresión Nadia de Mexicali: Perplexity traía a otra persona con el
    mismo nombre y, al correr antes que el enriquecimiento de LinkedIn,
    llenaba ubicación/educación con datos del homónimo."""

    def _svc_with_pplx(self, persona: dict):
        svc = ResearchService.__new__(ResearchService)

        class FakePplx:
            last_result = {"persona": persona, "empresa": {}}
            citations = []

        class FakeOrch:
            perplexity_scraper = FakePplx()

        svc.orchestrator = FakeOrch()
        return svc

    def _result(self) -> ResearchResult:
        r = ResearchResult()
        r.persona = {"nombre": "Nadia Ramirez Lara"}
        r.empresa = {"nombre": "Desert King"}
        return r

    def test_persona_homonima_de_perplexity_descartada(self):
        svc = self._svc_with_pplx({
            "nombre_completo": "Nadia Ramirez Lara",
            "empresa_actual": "Gobierno de Baja California",
            "ubicacion": "Mexicali, Baja California, México",
            "educacion": "UABC",
        })
        r = self._result()
        svc._enrich_from_perplexity(r)
        assert r.persona.get("ubicacion", "") == ""
        assert r.persona.get("educacion", "") == ""

    def test_persona_correcta_de_perplexity_se_usa(self):
        svc = self._svc_with_pplx({
            "nombre_completo": "Nadia Ramirez Lara",
            "empresa_actual": "Desert King",
            "ubicacion": "Valparaíso, Chile",
        })
        r = self._result()
        svc._enrich_from_perplexity(r)
        assert "Valpara" in r.persona.get("ubicacion", "")

    def test_linkedin_validado_gana_sobre_perplexity(self):
        # Orden nuevo: scraped items primero, Perplexity solo rellena vacíos
        svc = self._svc_with_pplx({
            "nombre_completo": "Nadia Ramirez Lara",
            "empresa_actual": "Desert King",
            "ubicacion": "Mexicali, Baja California, México",
        })
        r = self._result()
        ResearchService._enrich_from_scraped_items(svc, r, [_nadia_item()])
        svc._enrich_from_perplexity(r)
        assert "Valpara" in r.persona.get("ubicacion", "")
        assert "Mexicali" not in r.persona.get("ubicacion", "")


class TestLinkedInHomonymFallback:
    """El fallback con nombre acortado ('Nadia Ramirez') no debe devolver
    perfiles que no mencionen la empresa NI traigan el nombre completo."""

    def _scraper(self, monkeypatch, results):
        from scraper.linkedin import LinkedInScraper
        scraper = LinkedInScraper()

        async def fake(query, max_results=5):
            return results

        monkeypatch.setattr(scraper, "_ddg_text_search", fake)
        return scraper

    def test_homonimos_sin_empresa_ni_nombre_completo_descartados(self, monkeypatch):
        import asyncio
        scraper = self._scraper(monkeypatch, [
            {"href": "https://www.linkedin.com/in/n1", "title": "Nadia Ramirez - SEP | LinkedIn", "body": "Mexico"},
            {"href": "https://www.linkedin.com/in/n2", "title": "Nadia Ramirez - PM | LinkedIn", "body": "San Jose, California"},
        ])
        items = asyncio.run(scraper._search_ddg_api("q", company="Desert King", name="Nadia Ramirez Lara"))
        assert items == []

    def test_nombre_completo_sin_empresa_se_conserva(self, monkeypatch):
        import asyncio
        scraper = self._scraper(monkeypatch, [
            {"href": "https://cl.linkedin.com/in/nadia-rl", "title": "Nadia Ramirez Lara - Ingeniera Industrial | LinkedIn", "body": "Valparaíso"},
        ])
        items = asyncio.run(scraper._search_ddg_api("q", company="Desert King", name="Nadia Ramirez Lara"))
        assert len(items) == 1
        assert "nadia-rl" in items[0].url

    def test_match_de_empresa_sigue_teniendo_prioridad(self, monkeypatch):
        import asyncio
        scraper = self._scraper(monkeypatch, [
            {"href": "https://www.linkedin.com/in/otra", "title": "Nadia Ramirez Lara - Otra | LinkedIn", "body": "..."},
            {"href": "https://cl.linkedin.com/in/buena", "title": "Nadia R. - Supervisora | LinkedIn", "body": "Desert King Chile"},
        ])
        items = asyncio.run(scraper._search_ddg_api("q", company="Desert King", name="Nadia Ramirez Lara"))
        assert items[0].url.endswith("/buena")
