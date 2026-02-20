"""Scraper de búsqueda general: Google con fallback a DuckDuckGo (ddgs API)."""
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

        # Fallback a DDG API (ddgs library, funciona desde datacenter IPs)
        if not items:
            print("[GoogleSearchScraper] Google sin resultados, intentando DDG API")
            items = await self._search_ddg_api(query)

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

    async def _search_ddg_api(self, query: str) -> list[ScrapedItem]:
        """Search via ddgs library (API-based, works from datacenter IPs)."""
        max_results = self.settings.scraper.max_results_per_source
        results = await self._ddg_text_search(query, max_results=max_results)
        items = []
        for r in results:
            url = r.get("href", "")
            if not url or not url.startswith("http"):
                continue
            items.append(ScrapedItem(
                url=url,
                title=r.get("title", ""),
                snippet=r.get("body", ""),
                source="duckduckgo",
            ))
        return items[:max_results]

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
