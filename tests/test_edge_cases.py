"""Tests de casos de borde para anti-alucinación, fuentes, geografía y velocidad."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from dataclasses import dataclass

from scraper.base import ScrapedItem
from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.orchestrator import ScraperOrchestrator
from services.researcher import ResearchService, ResearchResult
from services.verifier import Verifier


# --- Helpers ---

@dataclass
class MockLLMResponse:
    content: str
    model_used: str = "test-model"


def _make_llm_json(score=85, hallazgo_tipo="A", hallazgos=None, cargo="CEO", sitio_web=""):
    """Genera un JSON de respuesta LLM configurable."""
    if hallazgos is None:
        hallazgos = [{"content": "Hallazgo test", "tipo": hallazgo_tipo, "sources": [], "confidence": "partial"}]
    return json.dumps({
        "persona": {"nombre": "Test", "cargo": cargo, "empresa": "TestCo", "trayectoria": "Inventada"},
        "empresa": {"nombre": "TestCo", "industria": "Mining", "sitio_web": sitio_web},
        "hallazgos": hallazgos,
        "hallazgo_tipo": hallazgo_tipo,
        "score": score,
        "cargo_descubierto": cargo,
    })


# --- Mock HTML responses ---

MOCK_DDG_HTML_WITH_ADS = """
<html><body>
<div class="result">
    <a class="result__a" href="https://duckduckgo.com/y.js?ad_domain=ebay.com&ad_provider=bingv7aa">Ad result on eBay</a>
    <a class="result__snippet">Buy stuff on eBay</a>
</div>
<div class="result">
    <a class="result__a" href="https://duckduckgo.com/y.js?ad_domain=amazon.com&ad_provider=bingv7aa">Amazon Ad</a>
    <a class="result__snippet">Shop on Amazon</a>
</div>
<div class="result">
    <a class="result__a" href="https://www.faymex.cl/">Faymex - Servicios especializados</a>
    <a class="result__snippet">Empresa chilena de servicios industriales</a>
</div>
<div class="result">
    <a class="result__a" href="https://cl.linkedin.com/in/german-saltron">German Saltron - LinkedIn</a>
    <a class="result__snippet">Experiencia: FAYMEX SpA. Ubicacion: Quilpue</a>
</div>
</body></html>
"""

MOCK_DDG_LINKEDIN_HTML = """
<html><body>
<div class="result">
    <a class="result__a" href="https://cl.linkedin.com/in/roberto-garcia">Roberto Garcia - Gerente | LinkedIn</a>
    <a class="result__snippet">Gerente de Mantenimiento en CODELCO. 15 anos experiencia.</a>
</div>
<div class="result">
    <a class="result__a" href="https://www.linkedin.com/company/codelco">CODELCO | LinkedIn</a>
    <a class="result__snippet">CODELCO es la principal empresa de cobre del mundo</a>
</div>
</body></html>
"""

MOCK_CORPORATE_HOMEPAGE = """
<html>
<head><title>Faymex – Servicios altamente especializados</title></head>
<body>
<nav>
<a href="https://faymex.cl/sobre-nosotros/">NOSOTROS</a>
<a href="https://faymex.cl/servicios/">SERVICIOS</a>
<a href="https://faymex.cl/contacto/">CONTACTO</a>
<a href="mailto:info@faymex.cl">Email</a>
<a href="#section1">Ancla</a>
<a href="https://faymex.cl/doc.pdf">PDF</a>
</nav>
<main>
<p>Faymex es una empresa chilena de servicios de ingenieria, fabricacion, montaje y mantenimiento industrial
con certificaciones ISO 9001:2015 e ISO 45001:2018. Fundada en 2016, Faymex se ha posicionado como un proveedor
confiable de servicios especializados para la gran mineria, energia y sector industrial en Chile.
Nuestros servicios incluyen fabricacion personalizada de piping, estructuras metalicas, estanques y equipos de
procesos, asi como construccion y montaje de instalaciones industriales complejas.</p>
</main>
</body>
</html>
"""

MOCK_CORPORATE_ABOUT = """
<html>
<head><title>Sobre Nosotros – Faymex</title></head>
<body>
<p>Fundada en 2016, Faymex ofrece servicios de fabricacion, montaje y mantenimiento industrial.</p>
</body>
</html>
"""


# =============================================================================
# TEST 1: LLM directo limita score a máximo 45
# =============================================================================
@pytest.mark.asyncio
async def test_llm_direct_caps_score_at_45():
    """Cuando los scrapers fallan y el LLM directo responde con score alto, debe truncarse a 45."""
    service = ResearchService()

    # LLM intenta dar score 85 → debe quedar en 45
    llm_response = MockLLMResponse(content=_make_llm_json(score=85, hallazgo_tipo="A"))

    with patch.object(service.orchestrator, "search_all", new_callable=AsyncMock, return_value=[]), \
         patch.object(service.llm, "complete", new_callable=AsyncMock, return_value=llm_response):
        result = await service.investigate("Persona Ficticia", "Empresa Ficticia")

    assert result.score <= 45, f"Score {result.score} excede el máximo de 45 para LLM directo"
    assert result.hallazgo_tipo in ("C", "D"), f"Tipo {result.hallazgo_tipo} no debería ser A/B sin scraping"


# =============================================================================
# TEST 2: LLM directo marca todo como "unverified"
# =============================================================================
@pytest.mark.asyncio
async def test_llm_direct_marks_unverified():
    """Sin scraping, todos los hallazgos deben tener confidence='unverified' y sources=[]."""
    service = ResearchService()

    hallazgos = [
        {"content": "Hallazgo 1", "tipo": "A", "sources": ["https://fake.com"], "confidence": "verified"},
        {"content": "Hallazgo 2", "tipo": "B", "sources": [], "confidence": "partial"},
    ]
    llm_response = MockLLMResponse(content=_make_llm_json(hallazgos=hallazgos))

    with patch.object(service.orchestrator, "search_all", new_callable=AsyncMock, return_value=[]), \
         patch.object(service.llm, "complete", new_callable=AsyncMock, return_value=llm_response):
        result = await service.investigate("Test", "TestCo")

    for h in result.hallazgos:
        assert h["confidence"] == "unverified", f"Hallazgo tiene confidence={h['confidence']}, esperado 'unverified'"
        assert h["sources"] == [], f"Hallazgo tiene sources={h['sources']}, esperado []"
        assert h["tipo"] in ("C", "D"), f"Hallazgo tipo={h['tipo']}, A/B no permitido sin scraping"


# =============================================================================
# TEST 3: LLM directo usa etiqueta "sin verificar" en llm_used
# =============================================================================
@pytest.mark.asyncio
async def test_llm_direct_label_sin_verificar():
    """El campo llm_used debe contener 'sin verificar' cuando no hay scraping."""
    service = ResearchService()

    llm_response = MockLLMResponse(content=_make_llm_json(score=20), model_used="deepseek-chat")

    with patch.object(service.orchestrator, "search_all", new_callable=AsyncMock, return_value=[]), \
         patch.object(service.llm, "complete", new_callable=AsyncMock, return_value=llm_response):
        result = await service.investigate("Test", "TestCo")

    assert "sin verificar" in result.llm_used, f"llm_used='{result.llm_used}' no contiene 'sin verificar'"
    assert "directo" not in result.llm_used, f"llm_used='{result.llm_used}' no debe contener 'directo'"


# =============================================================================
# TEST 4: DuckDuckGo filtra ads correctamente
# =============================================================================
@pytest.mark.asyncio
async def test_ddg_filters_ads():
    """Los resultados de DDG con duckduckgo.com/y.js deben ser filtrados como ads."""
    scraper = GoogleSearchScraper()

    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=None), \
         patch.object(scraper, "_ddg_post", new_callable=AsyncMock, return_value=MOCK_DDG_HTML_WITH_ADS):
        results = await scraper.search("German Saltron", "Faymex")

    # Solo deben quedar los 2 resultados orgánicos, no los 2 ads
    assert len(results) == 2, f"Esperados 2 resultados orgánicos, obtuve {len(results)}"
    for r in results:
        assert "duckduckgo.com/y.js" not in r.url, f"Ad URL no filtrada: {r.url}"
    assert any("faymex.cl" in r.url for r in results), "Falta resultado de faymex.cl"
    assert any("linkedin.com" in r.url for r in results), "Falta resultado de LinkedIn"


# =============================================================================
# TEST 5: LinkedIn DDG solo devuelve URLs de LinkedIn
# =============================================================================
@pytest.mark.asyncio
async def test_linkedin_ddg_filters_non_linkedin():
    """El scraper LinkedIn solo debe devolver URLs que contengan linkedin.com."""
    scraper = LinkedInScraper()

    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=None), \
         patch.object(scraper, "_ddg_post", new_callable=AsyncMock, return_value=MOCK_DDG_HTML_WITH_ADS):
        results = await scraper.search("German Saltron", "Faymex")

    assert len(results) == 1, f"Esperado 1 resultado LinkedIn, obtuve {len(results)}"
    assert "linkedin.com" in results[0].url
    assert "faymex.cl" not in results[0].url, "URL no-LinkedIn pasó el filtro"


# =============================================================================
# TEST 6: Corporate scraper descubre dominio y links internos
# =============================================================================
@pytest.mark.asyncio
async def test_corporate_discovers_domain_and_internal_links():
    """El corporate scraper debe adivinar el dominio y seguir links internos de la homepage."""
    scraper = CorporateSiteScraper()

    async def mock_request(url, params=None):
        if "sobre-nosotros" in url:
            return MOCK_CORPORATE_ABOUT
        elif "faymex.cl" in url:
            return MOCK_CORPORATE_HOMEPAGE
        return None

    with patch.object(scraper, "_make_request", side_effect=mock_request), \
         patch.object(scraper, "_ddg_post", new_callable=AsyncMock, return_value=None):
        results = await scraper.search("German Saltron", "Faymex")

    assert scraper.discovered_domain is not None, "No descubrió dominio"
    assert "faymex" in scraper.discovered_domain.lower()
    assert len(results) >= 1, "Debe tener al menos la homepage"

    # Verificar que NO siguió mailto:, #anchor ni .pdf
    urls = [r.url for r in results]
    for url in urls:
        assert "mailto" not in url
        assert ".pdf" not in url


# =============================================================================
# TEST 7: Dominio descubierto llega a empresa.sitio_web en el resultado
# =============================================================================
@pytest.mark.asyncio
async def test_corporate_domain_flows_to_sitio_web():
    """El dominio corporativo descubierto debe aparecer en result.empresa.sitio_web."""
    service = ResearchService()

    items = [
        ScrapedItem(url="https://www.faymex.cl/", title="Faymex", snippet="Empresa chilena de servicios industriales metalmecánicos", source="corporate"),
    ]

    # LLM responde sin sitio_web → el researcher debe inyectarlo
    llm_json = _make_llm_json(score=50, hallazgo_tipo="C", sitio_web="")
    llm_response = MockLLMResponse(content=llm_json)

    service.orchestrator.corporate_scraper.discovered_domain = "https://www.faymex.cl"

    with patch.object(service.orchestrator, "search_all", new_callable=AsyncMock, return_value=items), \
         patch.object(service.llm, "complete", new_callable=AsyncMock, return_value=llm_response):
        result = await service.investigate("German Saltron", "Faymex")

    assert result.empresa.get("sitio_web") == "https://www.faymex.cl", \
        f"sitio_web='{result.empresa.get('sitio_web')}', esperado 'https://www.faymex.cl'"


# =============================================================================
# TEST 8: Contexto LLM incluye ubicación y dominio corporativo
# =============================================================================
def test_llm_context_includes_location_and_domain():
    """El contexto enviado al LLM debe incluir ubicación del prospecto y sitio web corporativo."""
    service = ResearchService()
    verifier = Verifier()

    items = [
        ScrapedItem(url="https://example.com", title="Test", snippet="CODELCO inaugura nueva planta de procesamiento en Antofagasta region norte Chile", source="google_news"),
    ]
    facts = verifier.verify(items)

    context = service._build_llm_context(
        name="Roberto Garcia",
        company="CODELCO",
        role="Gerente Mantenimiento",
        facts=facts,
        location="Antofagasta",
        corporate_domain="https://www.codelco.com",
    )

    assert "Antofagasta" in context, "Ubicación no aparece en contexto LLM"
    assert "https://www.codelco.com" in context, "Dominio corporativo no aparece en contexto LLM"
    assert "Roberto Garcia" in context
    assert "CODELCO" in context
    assert "https://example.com" in context, "URL fuente no aparece en contexto LLM"


# =============================================================================
# TEST 9: Verificador preserva URLs de fuentes en VerifiedFact
# =============================================================================
def test_verifier_preserves_source_urls():
    """Las URLs de las fuentes deben propagarse desde ScrapedItem hasta VerifiedFact."""
    verifier = Verifier()

    items = [
        ScrapedItem(url="https://news.com/article1", title="Noticia 1",
                     snippet="CODELCO anuncia expansion proyecto nueva planta procesamiento cobre norte Chile", source="google_news"),
        ScrapedItem(url="https://other.com/article2", title="Noticia 2",
                     snippet="CODELCO expande planta nueva procesamiento cobre produccion norte mineria Chile", source="google_search"),
    ]
    facts = verifier.verify(items)

    assert len(facts) >= 1
    verified = [f for f in facts if f.confidence == "verified"]
    assert len(verified) >= 1, "Debería haber al menos 1 hecho verificado con 2 fuentes distintas"

    # Las URLs deben estar presentes
    all_urls = []
    for f in verified:
        all_urls.extend(f.sources)
    assert "https://news.com/article1" in all_urls, "URL de google_news perdida"
    assert "https://other.com/article2" in all_urls, "URL de google_search perdida"


# =============================================================================
# TEST 10: Orchestrator maneja errores sin perder resultados de scrapers exitosos
# =============================================================================
@pytest.mark.asyncio
async def test_orchestrator_partial_failure_preserves_results():
    """Si 3 de 4 scrapers fallan, el orchestrator debe devolver los resultados del que funcionó."""
    orchestrator = ScraperOrchestrator()

    corporate_items = [
        ScrapedItem(url="https://www.faymex.cl/", title="Faymex", snippet="Empresa chilena de servicios industriales", source="corporate"),
        ScrapedItem(url="https://faymex.cl/sobre-nosotros/", title="Sobre Nosotros", snippet="Fundada en 2016", source="corporate"),
    ]

    async def mock_fail(name, company, role="", location=""):
        raise Exception("Connection failed")

    async def mock_corporate(name, company, role="", location=""):
        return corporate_items

    with patch.object(orchestrator.linkedin_scraper, "search", side_effect=mock_fail), \
         patch.object(orchestrator.google_scraper, "search", side_effect=mock_fail), \
         patch.object(orchestrator.news_scraper, "search", side_effect=mock_fail), \
         patch.object(orchestrator.corporate_scraper, "search", side_effect=mock_corporate):
        results = await orchestrator.search_all("German Saltron", "Faymex")

    assert len(results) == 2, f"Esperados 2 resultados del corporate scraper, obtuve {len(results)}"
    assert all(r.source == "corporate" for r in results)


# =============================================================================
# TEST 11: Verifier incluye title no-redundante en VerifiedFact.content
# =============================================================================
def test_verifier_includes_non_redundant_title():
    """Cuando el title tiene info que no está en el snippet, debe incluirse en content."""
    verifier = Verifier()

    items = [
        ScrapedItem(
            url="https://cl.linkedin.com/in/roberto-garcia",
            title="Roberto Garcia - Gerente Mantenimiento | LinkedIn",
            snippet="Experiencia en CODELCO, 15 años en sector minero",
            source="linkedin",
        ),
    ]
    facts = verifier.verify(items)

    assert len(facts) >= 1
    # El title contiene "Gerente Mantenimiento" que no está en el snippet
    assert "Roberto Garcia" in facts[0].content or "Gerente" in facts[0].content, \
        f"Title info no incluida en content: {facts[0].content}"
    # El snippet original debe seguir presente
    assert "CODELCO" in facts[0].content


# =============================================================================
# TEST 12: LinkedIn _enrich_with_profile_page detecta authwall y hace fallback
# =============================================================================
@pytest.mark.asyncio
async def test_linkedin_enrich_authwall_fallback():
    """Si LinkedIn devuelve authwall, debe dejar los items sin cambios."""
    scraper = LinkedInScraper()

    original_snippet = "Experiencia: CODELCO, minería"
    original_title = "Roberto Garcia - LinkedIn"
    items = [
        ScrapedItem(
            url="https://cl.linkedin.com/in/roberto-garcia",
            title=original_title,
            snippet=original_snippet,
            source="linkedin",
        ),
    ]

    authwall_html = """
    <html><head><title>LinkedIn Login</title></head>
    <body><div class="authwall">Please sign-in to view this profile</div></body></html>
    """

    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=authwall_html):
        result = await scraper._enrich_with_profile_page(items)

    # Items deben quedar sin cambios
    assert result[0].snippet == original_snippet, f"Snippet cambió tras authwall: {result[0].snippet}"
    assert result[0].title == original_title, f"Title cambió tras authwall: {result[0].title}"


# =============================================================================
# TEST 13: LinkedIn _enrich_with_profile_page extrae meta description
# =============================================================================
@pytest.mark.asyncio
async def test_linkedin_enrich_extracts_meta():
    """Si el perfil es público, debe enriquecer snippet con meta tags."""
    scraper = LinkedInScraper()

    items = [
        ScrapedItem(
            url="https://cl.linkedin.com/in/roberto-garcia",
            title="Roberto Garcia - LinkedIn",
            snippet="Breve",
            source="linkedin",
        ),
    ]

    profile_html = """
    <html>
    <head>
        <title>Roberto Garcia - Gerente de Mantenimiento - CODELCO | LinkedIn</title>
        <meta name="description" content="Roberto Garcia. Gerente de Mantenimiento en CODELCO. Experiencia: 15 años en minería del cobre.">
        <meta property="og:description" content="Ve el perfil de Roberto Garcia en LinkedIn, la mayor red profesional del mundo.">
        <script type="application/ld+json">
        {
            "@type": "Person",
            "name": "Roberto Garcia",
            "jobTitle": "Gerente de Mantenimiento",
            "worksFor": {"@type": "Organization", "name": "CODELCO"},
            "address": {"addressLocality": "Antofagasta", "addressRegion": "Chile"}
        }
        </script>
    </head>
    <body><p>Profile content here, long enough to pass the 500 char check. Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation
    ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit
    esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident.</p></body>
    </html>
    """

    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=profile_html):
        result = await scraper._enrich_with_profile_page(items)

    # Snippet debe haberse enriquecido (más largo que "Breve")
    assert len(result[0].snippet) > len("Breve"), f"Snippet no enriquecido: {result[0].snippet}"
    # Debe contener datos del JSON-LD o meta description
    assert "Gerente" in result[0].snippet or "CODELCO" in result[0].snippet or "Mantenimiento" in result[0].snippet, \
        f"Datos de perfil no encontrados en snippet: {result[0].snippet}"
    # Title debe haberse enriquecido
    assert "Gerente" in result[0].title or "CODELCO" in result[0].title, \
        f"Title no enriquecido: {result[0].title}"
