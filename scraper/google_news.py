"""Scraper de Google News para noticias recientes."""
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class GoogleNewsScraper(BaseScraper):
    """Busca noticias recientes sobre la empresa y prospecto."""

    BASE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "") -> list[ScrapedItem]:
        query = f'"{company}" {name}'

        params = {
            "q": query,
            "tbm": "nws",
            "tbs": "qdr:m6",  # últimos 6 meses
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

        # Noticias aparecen en divs con clase diferente
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
