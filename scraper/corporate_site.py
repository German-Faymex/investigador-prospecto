"""Scraper de sitios web corporativos."""
import asyncio
import re
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class CorporateSiteScraper(BaseScraper):
    """Busca y extrae información del sitio web corporativo."""

    # Dominio encontrado, accesible para el researcher
    discovered_domain: str | None = None

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        items = []

        # 1. Intentar dominios directamente (no depende de Google)
        domain = await self._guess_company_domain(company)

        # 2. Si no funciona, intentar DDG
        if not domain:
            domain = await self._find_domain_via_ddg(company)

        if domain:
            self.discovered_domain = domain
            print(f"[CorporateSiteScraper] Dominio encontrado: {domain}")
            corp_items = await self._scrape_homepage_and_links(domain)
            items.extend(corp_items)

        return items[:self.settings.scraper.max_results_per_source]

    async def _guess_company_domain(self, company: str) -> str | None:
        """Intentar adivinar el dominio probando TLDs comunes."""
        clean = re.sub(r'\b(s\.?a\.?|ltda\.?|spa|s\.?r\.?l\.?|inc\.?|corp\.?|llc)\b', '', company, flags=re.IGNORECASE)
        clean = re.sub(r'[^a-zA-Z0-9]', '', clean).lower().strip()

        if not clean:
            return None

        # Probar en paralelo para velocidad
        candidates = [
            f"https://www.{clean}.cl",
            f"https://{clean}.cl",
            f"https://www.{clean}.com",
            f"https://{clean}.com",
        ]

        async def try_url(url):
            try:
                html = await self._make_request(url)
                if html and len(html) > 500:
                    return url
            except Exception:
                pass
            return None

        results = await asyncio.gather(*[try_url(u) for u in candidates])
        for result in results:
            if result:
                parsed = urlparse(result)
                return f"{parsed.scheme}://{parsed.netloc}"

        return None

    async def _find_domain_via_ddg(self, company: str) -> str | None:
        """Buscar dominio vía DuckDuckGo."""
        html = await self._ddg_post(f'"{company}" sitio web oficial')
        if not html:
            return None

        soup = BeautifulSoup(html, "html.parser")
        skip = {"linkedin.com", "facebook.com", "twitter.com", "instagram.com",
                "youtube.com", "wikipedia.org", "google.com"}

        for a in soup.select("a.result__a"):
            url = a.get("href", "")
            if not url or "duckduckgo.com" in url or not url.startswith("http"):
                continue
            parsed = urlparse(url)
            if not any(s in parsed.netloc for s in skip):
                return f"{parsed.scheme}://{parsed.netloc}"

        return None

    async def _scrape_homepage_and_links(self, domain: str) -> list[ScrapedItem]:
        """Scrape homepage y luego links internos descubiertos (sin paths hardcodeados)."""
        items = []
        internal_urls = []

        # 1. Scrape homepage
        homepage_url = domain + "/"
        html = await self._make_request(homepage_url)
        if not html:
            return items

        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(domain).netloc.replace("www.", "")

        # Descubrir links internos
        seen = {homepage_url, domain}
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            full_url = urljoin(domain, href)
            link_domain = urlparse(full_url).netloc.replace("www.", "")

            if (link_domain == base_domain
                and full_url not in seen
                and not any(full_url.endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip'])
                and '#' not in href and 'mailto' not in href and 'tel:' not in href):
                seen.add(full_url)
                internal_urls.append(full_url)

        item = self._extract_page_content(soup, homepage_url)
        if item:
            items.append(item)

        # 2. Scrape links internos en paralelo (máx 4 para velocidad)
        async def scrape_url(url):
            page_html = await self._make_request(url)
            if not page_html:
                return None
            page_soup = BeautifulSoup(page_html, "html.parser")
            return self._extract_page_content(page_soup, url)

        if internal_urls:
            results = await asyncio.gather(*[scrape_url(u) for u in internal_urls[:4]])
            for r in results:
                if r:
                    items.append(r)

        return items

    def _extract_page_content(self, soup: BeautifulSoup, url: str) -> ScrapedItem | None:
        """Extraer contenido de texto de una página HTML, incluyendo meta tags."""
        # 1. Extraer meta tags ANTES de strip (sobreviven SPAs)
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url

        meta_parts = []
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc and meta_desc.get("content"):
            meta_parts.append(meta_desc["content"])
        og_desc = soup.find("meta", {"property": "og:description"})
        if og_desc and og_desc.get("content") and og_desc["content"] not in meta_parts:
            meta_parts.append(og_desc["content"])
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title and og_title.get("content"):
            meta_parts.append(og_title["content"])

        # JSON-LD (datos estructurados de la empresa)
        ld_script = soup.find("script", type="application/ld+json")
        if ld_script:
            try:
                import json
                ld_data = json.loads(ld_script.string or "")
                if isinstance(ld_data, dict):
                    ld_bits = []
                    for key in ("name", "description", "industry", "numberOfEmployees", "foundingDate", "address"):
                        val = ld_data.get(key)
                        if val and isinstance(val, str):
                            ld_bits.append(f"{key}: {val}")
                        elif val and isinstance(val, dict):
                            ld_bits.append(f"{key}: {val.get('name', val.get('value', str(val)))}")
                    if ld_bits:
                        meta_parts.append(" | ".join(ld_bits))
                elif isinstance(ld_data, list):
                    for item in ld_data[:2]:
                        if isinstance(item, dict) and item.get("description"):
                            meta_parts.append(item["description"])
            except Exception:
                pass

        # 2. Extraer links del nav ANTES de eliminarlo (servicios/productos)
        nav_items = []
        for nav in soup.find_all("nav"):
            for a in nav.find_all("a"):
                text = a.get_text(strip=True)
                if text and len(text) > 2 and len(text) < 50:
                    nav_items.append(text)
        if nav_items:
            # Deduplicar preservando orden
            seen_nav = set()
            unique_nav = []
            for item in nav_items:
                if item.lower() not in seen_nav:
                    seen_nav.add(item.lower())
                    unique_nav.append(item)
            meta_parts.append(f"Secciones/Servicios: {', '.join(unique_nav[:15])}")

        # 3. Extraer body text (sin nav/header/footer para evitar ruido)
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()

        body_text = soup.get_text(separator=" ", strip=True)
        body_text = " ".join(body_text.split())[:1000]

        # 4. Combinar meta + body
        meta_text = " | ".join(meta_parts) if meta_parts else ""
        if meta_text and body_text:
            text = f"{meta_text}. {body_text}"
        elif meta_text:
            text = meta_text
        else:
            text = body_text

        if len(text) > 50:
            return ScrapedItem(
                url=url,
                title=title,
                snippet=text[:1500],
                source="corporate",
            )
        return None
