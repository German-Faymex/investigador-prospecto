"""Scraper de noticias: Google News + DDG News API + DDG Text reciente."""
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class GoogleNewsScraper(BaseScraper):
    """Busca noticias recientes sobre la EMPRESA (no la persona).

    Las noticias de la empresa son las más útiles para generar emails
    de primer contacto (ej: "Vi que Anglo American reportó...")

    Estrategia de 3 niveles:
    1. Google News (bloqueado desde datacenter IPs)
    2. DDG News API (funciona con queries en inglés/simples)
    3. DDG Text reciente (timelimit=month, funciona con queries en español)
    """

    GOOGLE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        # Noticias de la EMPRESA, no de la persona (las noticias raramente mencionan empleados)
        max_results = self.settings.scraper.max_results_per_source

        # 1. Google News (probablemente bloqueado desde Railway)
        google_query = f'"{company}" noticias'
        items = await self._search_google_news(google_query)
        if items:
            return items[:max_results]

        # 2. DDG News API (funciona mejor con queries simples/inglés)
        print("[GoogleNewsScraper] Google News sin resultados, intentando DDG News API")
        items = await self._search_ddg_news_api(company)
        if items:
            return items[:max_results]

        # 3. DDG Text reciente (último mes, funciona con queries en español)
        print("[GoogleNewsScraper] DDG News sin resultados, intentando DDG Text reciente")
        location_ctx = f" {location}" if location else " Chile"
        items = await self._search_ddg_text_recent(company, location_ctx)
        return items[:max_results]

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

    async def _search_ddg_news_api(self, company: str) -> list[ScrapedItem]:
        """Search news via DDG news API. Works best with company name only."""
        max_results = self.settings.scraper.max_results_per_source
        results = await self._ddg_news_search(company, max_results=max_results)
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
        return items

    async def _search_ddg_text_recent(self, company: str, location_ctx: str) -> list[ScrapedItem]:
        """Search recent text results (last month) as news fallback."""
        query = f"{company} noticias{location_ctx}"
        max_results = self.settings.scraper.max_results_per_source
        results = await self._ddg_text_search_recent(query, max_results=max_results)
        items = []
        for r in results:
            url = r.get("href", "")
            if not url or not url.startswith("http"):
                continue
            # Skip corporate homepage and social media (not news)
            if url.rstrip("/").count("/") <= 3:
                continue
            items.append(ScrapedItem(
                url=url,
                title=r.get("title", ""),
                snippet=r.get("body", ""),
                source="duckduckgo_news",
            ))
        return items

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
