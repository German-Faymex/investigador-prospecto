"""Scraper de sitios web corporativos."""
import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


CORPORATE_PATHS = ["/", "/about", "/about-us", "/nosotros", "/quienes-somos",
                   "/news", "/noticias", "/team", "/equipo", "/empresa",
                   "/servicios", "/services", "/productos", "/products"]


class CorporateSiteScraper(BaseScraper):
    """Busca y extrae información del sitio web corporativo."""

    BASE_URL = "https://www.google.com/search"

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        items = []

        # 1. Intentar dominios directamente (no depende de Google)
        domain = await self._guess_company_domain(company)

        # 2. Si no funciona, intentar vía Google
        if not domain:
            domain = await self._find_company_domain_google(company)

        if domain:
            print(f"[CorporateSiteScraper] Dominio encontrado: {domain}")
            corp_items = await self._scrape_corporate_pages(domain, name, company)
            items.extend(corp_items)

        # 3. También buscar menciones en Google
        google_items = await self._google_corporate_search(name, company)
        items.extend(google_items)

        return items[:self.settings.scraper.max_results_per_source]

    async def _guess_company_domain(self, company: str) -> str | None:
        """Intentar adivinar el dominio de la empresa probando TLDs comunes."""
        # Limpiar nombre: "Faymex S.A." -> "faymex", "Anglo American" -> "angloamerican"
        clean = re.sub(r'\b(s\.?a\.?|ltda\.?|spa|s\.?r\.?l\.?|inc\.?|corp\.?|llc)\b', '', company, flags=re.IGNORECASE)
        clean = re.sub(r'[^a-zA-Z0-9]', '', clean).lower().strip()

        if not clean:
            return None

        # TLDs comunes para empresas chilenas y latinoamericanas
        candidates = [
            f"https://www.{clean}.cl",
            f"https://{clean}.cl",
            f"https://www.{clean}.com",
            f"https://{clean}.com",
            f"https://www.{clean}.com.cl",
            f"https://{clean}.com.cl",
        ]

        for url in candidates:
            try:
                html = await self._make_request(url)
                if html and len(html) > 500:
                    print(f"[CorporateSiteScraper] Dominio adivinado: {url}")
                    parsed = urlparse(url)
                    return f"{parsed.scheme}://{parsed.netloc}"
            except Exception:
                continue

        return None

    async def _find_company_domain_google(self, company: str) -> str | None:
        """Buscar dominio web de la empresa vía Google (fallback)."""
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
                skip = ["linkedin.com", "facebook.com", "twitter.com",
                        "instagram.com", "youtube.com", "wikipedia.org",
                        "bloomberg.com", "crunchbase.com", "google.com"]
                if not any(s in parsed.netloc for s in skip):
                    return f"{parsed.scheme}://{parsed.netloc}"

        return None

    async def _scrape_corporate_pages(self, domain: str, name: str, company: str) -> list[ScrapedItem]:
        """Scrape páginas relevantes del sitio corporativo: paths comunes + links internos."""
        items = []
        visited = set()
        parsed_domain = urlparse(domain)

        # 1. Intentar paths conocidos + homepage
        for path in CORPORATE_PATHS:
            url = urljoin(domain, path)
            if url in visited:
                continue
            visited.add(url)

            html = await self._make_request(url)
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            # Descubrir links internos desde la homepage
            if path == "/":
                base_domain = parsed_domain.netloc.replace("www.", "")
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    full_url = urljoin(domain, href)
                    link_parsed = urlparse(full_url)
                    link_domain = link_parsed.netloc.replace("www.", "")
                    # Solo links del mismo dominio, no anchors ni archivos
                    if (link_domain == base_domain
                        and full_url not in visited
                        and not any(full_url.endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip'])
                        and '#' not in href
                        and 'mailto' not in href
                        and 'tel:' not in href):
                        visited.add(full_url)

            item = self._extract_page_content(soup, url)
            if item:
                items.append(item)

        # 2. Scrapear links internos descubiertos (máx 5 extras)
        extra_urls = [u for u in visited if u not in {urljoin(domain, p) for p in CORPORATE_PATHS}]
        for url in extra_urls[:5]:
            html = await self._make_request(url)
            if not html:
                continue
            soup = BeautifulSoup(html, "html.parser")
            item = self._extract_page_content(soup, url)
            if item:
                items.append(item)

        return items

    def _extract_page_content(self, soup: BeautifulSoup, url: str) -> ScrapedItem | None:
        """Extraer contenido de texto de una página HTML."""
        # Clonar para no mutar el original
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        text = soup.get_text(separator=" ", strip=True)
        text = " ".join(text.split())[:1000]

        if len(text) > 50:
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else url

            return ScrapedItem(
                url=url,
                title=title,
                snippet=text,
                source="corporate",
            )
        return None

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
