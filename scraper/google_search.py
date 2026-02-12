"""Scraper de búsqueda general de Google."""
from urllib.parse import quote_plus, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class GoogleSearchScraper(BaseScraper):
    """Busca resultados generales en Google sobre el prospecto."""

    BASE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "") -> list[ScrapedItem]:
        query_parts = [f'"{name}"', f'"{company}"']
        if role:
            query_parts.append(role)
        query = " ".join(query_parts)

        params = {
            "q": query,
            "num": str(self.settings.scraper.max_results_per_source),
            "hl": "es",
        }

        html = await self._make_request(self.BASE_URL, params=params)
        if not html:
            return []

        return self._parse_results(html)

    def _parse_results(self, html: str) -> list[ScrapedItem]:
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
