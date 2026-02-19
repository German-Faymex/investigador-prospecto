"""Scraper de sitios web corporativos."""
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


CORPORATE_PATHS = ["/about", "/about-us", "/nosotros", "/quienes-somos",
                   "/news", "/noticias", "/team", "/equipo", "/empresa"]


class CorporateSiteScraper(BaseScraper):
    """Busca y extrae información del sitio web corporativo."""

    BASE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        # Primero buscar el sitio web de la empresa
        domain = await self._find_company_domain(company)
        items = []

        if domain:
            # Scrape páginas relevantes del sitio corporativo
            corp_items = await self._scrape_corporate_pages(domain, name, company)
            items.extend(corp_items)

        # También buscar menciones en Google
        google_items = await self._google_corporate_search(name, company)
        items.extend(google_items)

        return items[:self.settings.scraper.max_results_per_source]

    async def _find_company_domain(self, company: str) -> str | None:
        """Buscar dominio web de la empresa."""
        query = f'"{company}" sitio oficial'
        params = {"q": query, "num": "3", "hl": "es"}

        html = await self._make_request(self.BASE_URL, params=params)
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        for g in soup.select("div.g"):
            link_el = g.select_one("a[href]")
            if not link_el:
                continue
            url = link_el.get("href", "")
            if url.startswith("http"):
                parsed = urlparse(url)
                # Excluir redes sociales y directorios
                skip = ["linkedin.com", "facebook.com", "twitter.com",
                        "instagram.com", "youtube.com", "wikipedia.org",
                        "bloomberg.com", "crunchbase.com"]
                if not any(s in parsed.netloc for s in skip):
                    return f"{parsed.scheme}://{parsed.netloc}"

        return None

    async def _scrape_corporate_pages(self, domain: str, name: str, company: str) -> list[ScrapedItem]:
        """Scrape páginas relevantes del sitio corporativo."""
        items = []

        for path in CORPORATE_PATHS:
            url = urljoin(domain, path)
            html = await self._make_request(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Remover scripts y estilos
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()

            text = soup.get_text(separator=" ", strip=True)
            # Tomar los primeros 500 chars relevantes
            text = " ".join(text.split())[:500]

            if len(text) > 50:
                title_tag = soup.find("title")
                title = title_tag.get_text(strip=True) if title_tag else path

                items.append(ScrapedItem(
                    url=url,
                    title=title,
                    snippet=text,
                    source="corporate",
                ))

        return items

    async def _google_corporate_search(self, name: str, company: str) -> list[ScrapedItem]:
        """Buscar info corporativa vía Google."""
        query = f'"{company}" about us OR equipo OR noticias {name}'
        params = {"q": query, "num": "5", "hl": "es"}

        html = await self._make_request(self.BASE_URL, params=params)
        if not html:
            return []

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
                source="corporate",
            ))

        return items
