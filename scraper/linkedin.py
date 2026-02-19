"""Scraper de LinkedIn vía búsqueda en Google."""
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class LinkedInScraper(BaseScraper):
    """Busca perfiles de LinkedIn del prospecto a través de Google."""

    BASE_URL = "https://www.google.com/search"

    @staticmethod
    def build_search_url(name: str, company: str) -> str:
        """Build a LinkedIn people search URL for the prospect."""
        from urllib.parse import quote_plus
        keywords = quote_plus(f"{name} {company}")
        return f"https://www.linkedin.com/search/results/people/?keywords={keywords}"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        query = f'site:linkedin.com/in/ "{name}" "{company}"'

        params = {
            "q": query,
            "num": "5",
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
            if "linkedin.com" not in url:
                continue

            title = title_el.get_text(strip=True)
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""

            items.append(ScrapedItem(
                url=url,
                title=title,
                snippet=snippet,
                source="linkedin",
            ))

            if len(items) >= 3:
                break

        return items
