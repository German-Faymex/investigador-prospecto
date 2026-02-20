"""Scraper de noticias: Google News con fallback a DuckDuckGo (ddgs API)."""
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class GoogleNewsScraper(BaseScraper):
    """Busca noticias recientes sobre la empresa y prospecto."""

    GOOGLE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        query = f'"{company}" {name} {location}'.strip() if location else f'"{company}" {name}'

        # Intentar Google News primero
        items = await self._search_google_news(query)

        # Fallback a DDG news API (ddgs library, funciona desde datacenter IPs)
        if not items:
            print("[GoogleNewsScraper] Google News sin resultados, intentando DDG News API")
            items = await self._search_ddg_news_api(query)

        return items

    async def _search_google_news(self, query: str) -> list[ScrapedItem]:
        params = {
            "q": query,
            "tbm": "nws",
            "tbs": "qdr:m6",  # últimos 6 meses
            "num": str(self.settings.scraper.max_results_per_source),
            "hl": "es",
        }

        html = await self._make_request(self.GOOGLE_URL, params=params)
        if not html:
            return []

        return self._parse_google_results(html)

    async def _search_ddg_news_api(self, query: str) -> list[ScrapedItem]:
        """Search news via ddgs library (API-based, works from datacenter IPs)."""
        max_results = self.settings.scraper.max_results_per_source
        results = await self._ddg_news_search(query, max_results=max_results)
        items = []
        for r in results:
            url = r.get("url", "")
            if not url:
                continue
            items.append(ScrapedItem(
                url=url,
                title=r.get("title", ""),
                snippet=r.get("body", ""),
                source="duckduckgo_news",
                timestamp=r.get("date", ""),
            ))
        return items[:max_results]

    def _parse_google_results(self, html: str) -> list[ScrapedItem]:
        soup = BeautifulSoup(html, "html.parser")
        items = []

        for article in soup.select("div.SoaBEf, div.dbsr, div.g"):
            link_el = article.select_one("a[href]")
            title_el = article.select_one("div.mCBkyc, div.JheGif, h3")
            snippet_el = article.select_one("div.GI74Re, div.Y3v8qd, div.VwiC3b")
            time_el = article.select_one("span.WG9SHc, div.OSrXXb span, span.f")

            if not link_el:
                continue

            url = link_el.get("href", "")
            if not url or not url.startswith("http"):
                continue

            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            timestamp = time_el.get_text(strip=True) if time_el else ""

            if not title and not snippet:
                continue

            items.append(ScrapedItem(
                url=url,
                title=title,
                snippet=snippet,
                source="google_news",
                timestamp=timestamp,
            ))

            if len(items) >= self.settings.scraper.max_results_per_source:
                break

        return items
