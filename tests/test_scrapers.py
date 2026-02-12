"""Tests para scrapers con respuestas HTTP mockeadas."""
import pytest
from unittest.mock import AsyncMock, patch

from scraper.base import ScrapedItem
from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.orchestrator import ScraperOrchestrator


MOCK_GOOGLE_HTML = """
<html><body>
<div class="g">
    <a href="https://example.com/article1"><h3>Roberto Garcia - CODELCO Mining</h3></a>
    <div class="VwiC3b">Roberto Garcia es Gerente de Mantenimiento en CODELCO division norte.</div>
</div>
<div class="g">
    <a href="https://example.com/article2"><h3>CODELCO anuncia expansion</h3></a>
    <div class="VwiC3b">CODELCO anuncia inversion de USD 500M en nueva planta.</div>
</div>
</body></html>
"""

MOCK_NEWS_HTML = """
<html><body>
<div class="SoaBEf">
    <a href="https://news.example.com/noticia1">
        <div class="mCBkyc">CODELCO inaugura planta en Antofagasta</div>
    </a>
    <div class="GI74Re">La nueva planta procesara 50,000 toneladas anuales.</div>
    <span class="WG9SHc">hace 2 dias</span>
</div>
</body></html>
"""

MOCK_LINKEDIN_HTML = """
<html><body>
<div class="g">
    <a href="https://www.linkedin.com/in/roberto-garcia-123"><h3>Roberto Garcia - Gerente Mantenimiento | LinkedIn</h3></a>
    <div class="VwiC3b">Chile - Gerente de Mantenimiento en CODELCO. 15 anos de experiencia en mineria.</div>
</div>
</body></html>
"""

MOCK_CORPORATE_HTML = """
<html><body>
<title>CODELCO - Quienes Somos</title>
<div>
    <p>CODELCO es la empresa estatal de cobre de Chile, principal productor mundial.
    Con operaciones en el norte de Chile, produce mas de 1.5 millones de toneladas anuales.</p>
</div>
</body></html>
"""


@pytest.mark.asyncio
async def test_google_search_scraper():
    scraper = GoogleSearchScraper()
    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=MOCK_GOOGLE_HTML):
        results = await scraper.search("Roberto Garcia", "CODELCO", "Gerente Mantenimiento")

    assert len(results) == 2
    assert results[0].source == "google_search"
    assert "Roberto Garcia" in results[0].title
    assert results[0].url == "https://example.com/article1"
    assert results[1].snippet != ""


@pytest.mark.asyncio
async def test_google_news_scraper():
    scraper = GoogleNewsScraper()
    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=MOCK_NEWS_HTML):
        results = await scraper.search("Roberto Garcia", "CODELCO")

    assert len(results) >= 1
    assert results[0].source == "google_news"
    assert "CODELCO" in results[0].title


@pytest.mark.asyncio
async def test_linkedin_scraper():
    scraper = LinkedInScraper()
    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=MOCK_LINKEDIN_HTML):
        results = await scraper.search("Roberto Garcia", "CODELCO")

    assert len(results) == 1
    assert results[0].source == "linkedin"
    assert "linkedin.com" in results[0].url


@pytest.mark.asyncio
async def test_corporate_scraper():
    scraper = CorporateSiteScraper()

    async def mock_request(url, params=None):
        if "google.com" in url:
            return '<html><body><div class="g"><a href="https://codelco.com/about"><h3>CODELCO</h3></a></div></body></html>'
        elif "codelco.com" in url:
            return MOCK_CORPORATE_HTML
        return None

    with patch.object(scraper, "_make_request", side_effect=mock_request):
        results = await scraper.search("Roberto Garcia", "CODELCO")

    assert any(r.source == "corporate" for r in results)


@pytest.mark.asyncio
async def test_google_search_empty_response():
    scraper = GoogleSearchScraper()
    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value=None):
        results = await scraper.search("Test", "Test")

    assert results == []


@pytest.mark.asyncio
async def test_google_search_bad_html():
    scraper = GoogleSearchScraper()
    with patch.object(scraper, "_make_request", new_callable=AsyncMock, return_value="<html><body>No results</body></html>"):
        results = await scraper.search("Test", "Test")

    assert results == []


@pytest.mark.asyncio
async def test_orchestrator_parallel():
    orchestrator = ScraperOrchestrator()

    async def mock_search(self, name, company, role=""):
        return [ScrapedItem(url="https://test.com", title="Test", snippet="Test data", source=self.__class__.__name__)]

    with patch.object(GoogleSearchScraper, "search", mock_search), \
         patch.object(GoogleNewsScraper, "search", mock_search), \
         patch.object(LinkedInScraper, "search", mock_search), \
         patch.object(CorporateSiteScraper, "search", mock_search):
        results = await orchestrator.search_all("Test", "Test")

    assert len(results) == 4


@pytest.mark.asyncio
async def test_orchestrator_handles_errors():
    orchestrator = ScraperOrchestrator()

    async def mock_error(self, name, company, role=""):
        raise Exception("Connection failed")

    async def mock_success(self, name, company, role=""):
        return [ScrapedItem(url="https://ok.com", title="OK", snippet="Works", source="test")]

    with patch.object(GoogleSearchScraper, "search", mock_error), \
         patch.object(GoogleNewsScraper, "search", mock_success), \
         patch.object(LinkedInScraper, "search", mock_error), \
         patch.object(CorporateSiteScraper, "search", mock_success):
        results = await orchestrator.search_all("Test", "Test")

    assert len(results) == 2
