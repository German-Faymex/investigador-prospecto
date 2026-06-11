"""Tests de validación de dominio corporativo (regresión caso Noracid/Metso).

Bug original: al investigar un prospecto de Noracid, noracid.cl respondía 403
desde Railway, el fallback DDG devolvía metso.com (proveedor que construyó la
planta de Noracid) y el sistema scrapeaba y mostraba el sitio de OTRA empresa.
"""
import pytest

from scraper.corporate_site import CorporateSiteScraper
from services.researcher import ResearchService, ResearchResult


class TestDomainMatchesCompany:
    def test_rechaza_dominio_de_tercero(self):
        # El caso real del bug: metso.com rankea para "Noracid"
        assert not CorporateSiteScraper._domain_matches_company("www.metso.com", "Noracid")

    def test_acepta_dominio_propio_cl(self):
        assert CorporateSiteScraper._domain_matches_company("noracid.cl", "Noracid")
        assert CorporateSiteScraper._domain_matches_company("www.noracid.cl", "Noracid")

    def test_acepta_dominio_propio_com(self):
        assert CorporateSiteScraper._domain_matches_company("www.faymex.cl", "Faymex SpA")

    def test_ignora_sufijos_societarios(self):
        assert CorporateSiteScraper._domain_matches_company("noracid.cl", "Noracid S.A.")

    def test_nombre_multipalabra_matchea_por_palabra_significativa(self):
        assert CorporateSiteScraper._domain_matches_company(
            "www.collahuasi.cl", "Compañía Minera Doña Inés de Collahuasi"
        )
        assert CorporateSiteScraper._domain_matches_company(
            "www.angloamerican.com", "Anglo American"
        )

    def test_nombre_corto_tres_letras(self):
        assert CorporateSiteScraper._domain_matches_company("www.bhp.com", "BHP")
        assert CorporateSiteScraper._domain_matches_company("www.sqm.com", "SQM Salar")

    def test_rechaza_directorios_y_prensa(self):
        assert not CorporateSiteScraper._domain_matches_company("www.datanyze.com", "Noracid")
        assert not CorporateSiteScraper._domain_matches_company("www.bnamericas.com", "Noracid")


class TestSanitizeSitioWeb:
    def _result_con_sitio(self, sitio: str) -> ResearchResult:
        r = ResearchResult()
        r.empresa = {"nombre": "Noracid", "sitio_web": sitio}
        return r

    def test_descarta_sitio_de_tercero_sin_dominio_descubierto(self):
        r = self._result_con_sitio("https://www.metso.com")
        ResearchService._sanitize_sitio_web(r, "Noracid", None)
        assert r.empresa["sitio_web"] == ""

    def test_reemplaza_tercero_por_dominio_descubierto(self):
        r = self._result_con_sitio("https://www.metso.com")
        ResearchService._sanitize_sitio_web(r, "Noracid", "https://noracid.cl")
        assert r.empresa["sitio_web"] == "https://noracid.cl"

    def test_conserva_sitio_correcto(self):
        r = self._result_con_sitio("https://noracid.cl")
        ResearchService._sanitize_sitio_web(r, "Noracid", "https://noracid.cl")
        assert r.empresa["sitio_web"] == "https://noracid.cl"

    def test_conserva_dominio_descubierto_aunque_no_contenga_nombre(self):
        # El dominio descubierto es autoritativo (ya fue validado contra el HTML)
        r = self._result_con_sitio("https://www.empresa-xyz.com")
        ResearchService._sanitize_sitio_web(
            r, "Empresa XYZ Holding", "https://www.empresa-xyz.com"
        )
        assert r.empresa["sitio_web"] == "https://www.empresa-xyz.com"

    def test_sitio_sin_esquema(self):
        r = self._result_con_sitio("www.metso.com")
        ResearchService._sanitize_sitio_web(r, "Noracid", None)
        assert r.empresa["sitio_web"] == ""

    def test_campo_vacio_se_llena_con_descubierto(self):
        r = self._result_con_sitio("")
        ResearchService._sanitize_sitio_web(r, "Noracid", "https://noracid.cl")
        assert r.empresa["sitio_web"] == "https://noracid.cl"


class TestSitioWebHomonimo:
    """Caso 'abc': el dominio contiene el nombre pero es de OTRA empresa
    (abc.com = ABC Network, no la empresa chilena 'abc'). La validación por
    nombre no puede distinguirlos; el veredicto viene del LLM vía
    empresa.sitio_web_corresponde=false."""

    def _result(self, sitio: str, corresponde) -> ResearchResult:
        r = ResearchResult()
        r.empresa = {"nombre": "abc", "sitio_web": sitio}
        if corresponde is not None:
            r.empresa["sitio_web_corresponde"] = corresponde
        return r

    def test_llm_veta_dominio_homonimo(self):
        r = self._result("https://www.abc.com", corresponde=False)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert r.empresa["sitio_web"] == ""

    def test_veto_evita_rellenar_con_dominio_descubierto(self):
        # LLM dejó sitio_web vacío y marcó corresponde=false: NO rellenar
        r = self._result("", corresponde=False)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert r.empresa["sitio_web"] == ""

    def test_corresponde_true_conserva_dominio(self):
        r = self._result("https://www.abc.com", corresponde=True)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert r.empresa["sitio_web"] == "https://www.abc.com"

    def test_sin_flag_se_asume_valido(self):
        # Compatibilidad: DeepSeek (sin schema enforcement) puede omitir el campo
        r = self._result("https://www.abc.com", corresponde=None)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert r.empresa["sitio_web"] == "https://www.abc.com"

    def test_flag_se_remueve_del_resultado(self):
        # Es un campo de control: no debe llegar a la UI ni al email
        r = self._result("https://www.abc.com", corresponde=True)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert "sitio_web_corresponde" not in r.empresa

    def test_veto_no_bloquea_sitio_distinto_valido(self):
        # Perplexity puede aportar el sitio real después del veto al descubierto
        r = self._result("https://www.empresasabc.cl", corresponde=False)
        ResearchService._sanitize_sitio_web(r, "abc", "https://www.abc.com")
        assert r.empresa["sitio_web"] == "https://www.empresasabc.cl"
