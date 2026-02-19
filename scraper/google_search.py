"""Scraper de búsqueda general: Google con fallback a DuckDuckGo."""
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class GoogleSearchScraper(BaseScraper):
    """Busca resultados generales sobre el prospecto."""

    GOOGLE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        query_parts = [f'"{name}"', f'"{company}"']
        if role:
            query_parts.append(role)
        query = " ".join(query_parts)

        # Intentar Google primero
        items = await self._search_google(query)

        # Fallback a DuckDuckGo si Google no devuelve resultados
        if not items:
            print("[GoogleSearchScraper] Google sin resultados, intentando DuckDuckGo")
            items = await self._search_duckduckgo(query)

        return items

    async def _search_google(self, query: str) -> list[ScrapedItem]:
        params = {
            "q": query,
            "num": str(self.settings.scraper.max_results_per_source),
            "hl": "es",
        }

        html = await self._make_request(self.GOOGLE_URL, params=params)
        if not html:
            return []

        return self._parse_google_results(html)

    async def _search_duckduckgo(self, query: str) -> list[ScrapedItem]:
        """Buscar en DuckDuckGo HTML (más permisivo que Google)."""
        html = await self._ddg_post(query)
        if not html:
            return []
        return self._parse_ddg_results(html)

    def _parse_google_results(self, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        for g in soup.select("div.g"):
            link_el = g.select_one("a[href]")
            title_el = g.select_one("h3")
            snippet_el = g.select_one("div[data-sncf], div.VwiC3b, span.aCOpRe")

            if not link_el or not title_el:
                continue

            url = link_el.get("href", "")
            if not url or not url.startswith("http"):
                continue

            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            items.append(ScrapedItem(
                url=url,
                title=title,
                snippet=snippet,
                source="google_search",
            ))

            if len(items) >= self.settings.scraper.max_results_per_source:
                break

        return items

    def _parse_ddg_results(self, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        for title_el in soup.select("a.result__a"):
            url = title_el.get("href", "")
            # Filtrar ads de DDG y URLs no válidas
            if not url or "duckduckgo.com/y.js" in url or not url.startswith("http"):
                continue

            title = title_el.get_text(strip=True)
            # Buscar snippet en el mismo contenedor padre
            parent = title_el.find_parent("div", class_="result")
            snippet_el = parent.select_one("a.result__snippet") if parent else None
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            items.append(ScrapedItem(
                url=url,
                title=title,
                snippet=snippet,
                source="duckduckgo",
            ))

            if len(items) >= self.settings.scraper.max_results_per_source:
                break

        return items
