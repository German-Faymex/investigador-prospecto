"""Scraper de LinkedIn vía Google/DuckDuckGo."""
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class LinkedInScraper(BaseScraper):
    """Busca perfiles de LinkedIn del prospecto a través de buscadores."""

    GOOGLE_URL = "https://www.google.com/search"

    @staticmethod
    def build_search_url(name: str, company: str) -> str:
        """Build a LinkedIn people search URL for the prospect."""
        from urllib.parse import quote_plus
        keywords = quote_plus(f"{name} {company}")
        return f"https://www.linkedin.com/search/results/people/?keywords={keywords}"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        query = f'site:linkedin.com/in/ "{name}" "{company}"'

        # Intentar Google primero
        items = await self._search_google(query)

        # Fallback a DuckDuckGo
        if not items:
            print("[LinkedInScraper] Google sin resultados, intentando DuckDuckGo")
            ddg_query = f'{name} {company} site:linkedin.com/in/'
            items = await self._search_duckduckgo(ddg_query)

        return items

    async def _search_google(self, query: str) -> list[ScrapedItem]:
        params = {"q": query, "num": "5", "hl": "es"}

        html = await self._make_request(self.GOOGLE_URL, params=params)
        if not html:
            return []

        return self._parse_google_results(html)

    async def _search_duckduckgo(self, query: str) -> list[ScrapedItem]:
        """Buscar perfiles LinkedIn en DuckDuckGo HTML."""
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

    def _parse_ddg_results(self, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        for title_el in soup.select("a.result__a"):
            url = title_el.get("href", "")
            if not url or "duckduckgo.com/y.js" in url:
                continue
            if "linkedin.com" not in url:
                continue

            title = title_el.get_text(strip=True)
            parent = title_el.find_parent("div", class_="result")
            snippet_el = parent.select_one("a.result__snippet") if parent else None
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
