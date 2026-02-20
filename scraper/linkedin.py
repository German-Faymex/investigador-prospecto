"""Scraper de LinkedIn vía DuckDuckGo/Google."""
import json
import re
import unicodedata

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem


class LinkedInScraper(BaseScraper):
    """Busca perfiles de LinkedIn del prospecto.

    Prioriza DuckDuckGo sobre Google porque Google bloquea IPs de datacenter
    (Railway, AWS, etc.) mientras DDG es más permisivo.
    """

    GOOGLE_URL = "https://www.google.com/search"

    @staticmethod
    def build_search_url(name: str, company: str) -> str:
        """Build a LinkedIn people search URL for the prospect."""
        from urllib.parse import quote_plus
        keywords = quote_plus(f"{name} {company}")
        return f"https://www.linkedin.com/search/results/people/?keywords={keywords}"

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Remove accents from text: 'Juliá' → 'Julia'."""
        normalized = unicodedata.normalize("NFKD", text)
        return "".join(c for c in normalized if not unicodedata.combining(c))

    async def search(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        name_clean = self._strip_accents(name)

        # DDG PRIMERO (funciona desde datacenter IPs), Google después (a menudo bloqueado)
        search_attempts = [
            # 1. DDG con site: (MÁS CONFIABLE desde datacenter)
            ("ddg", f'{name_clean} {company} site:linkedin.com/in/'),
            # 2. Google con site: (fallback, a menudo bloqueado)
            ("google", f'site:linkedin.com/in/ "{name_clean}" "{company}"'),
            # 3. DDG flexible (sin site:)
            ("ddg", f'"{name_clean}" "{company}" linkedin'),
            # 4. DDG ultra flexible
            ("ddg", f'{name_clean} {company} linkedin perfil'),
        ]

        items = []
        for engine, query in search_attempts:
            if engine == "google":
                items = await self._search_google(query)
            else:
                items = await self._search_duckduckgo(query)

            if items:
                print(f"[LinkedInScraper] Encontrado con: {engine} - {query[:60]}...")
                break
            print(f"[LinkedInScraper] Sin resultados: {engine} - {query[:60]}...")

        # Último recurso: intentar URLs directas de perfil LinkedIn
        if not items:
            print("[LinkedInScraper] Buscadores sin resultados, intentando URLs directas")
            items = await self._try_direct_profile(name)

        # Enriquecer con datos del perfil público
        if items:
            items = await self._enrich_with_profile_page(items)

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

        # Selector principal de DDG HTML
        result_links = soup.select("a.result__a")
        # Fallback: DDG cambia selectores ocasionalmente
        if not result_links:
            result_links = soup.select("h2 a[href*='linkedin.com']")
        if not result_links:
            result_links = soup.select("a[href*='linkedin.com']")

        for title_el in result_links:
            url = title_el.get("href", "")
            if not url or "duckduckgo.com/y.js" in url:
                continue
            if "linkedin.com" not in url:
                continue

            title = title_el.get_text(strip=True)
            # Buscar snippet en el mismo contenedor padre
            parent = title_el.find_parent("div", class_="result")
            if not parent:
                parent = title_el.find_parent("div")
            snippet_el = None
            if parent:
                snippet_el = (
                    parent.select_one("a.result__snippet")
                    or parent.select_one(".result__snippet")
                    or parent.select_one("span.result__snippet")
                )
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

    @staticmethod
    def _name_to_slugs(name: str) -> list[str]:
        """Convertir nombre a posibles slugs de LinkedIn URL."""
        normalized = unicodedata.normalize("NFKD", name)
        normalized = "".join(c for c in normalized if not unicodedata.combining(c))
        normalized = normalized.lower().strip()
        normalized = re.sub(r"[^a-z\s]", "", normalized)
        parts = normalized.split()
        if len(parts) < 2:
            return []

        slugs = []
        slugs.append("-".join(parts))
        if len(parts) >= 3:
            slugs.append(f"{parts[0]}-{parts[1]}")
        if len(parts) >= 3:
            slugs.append(f"{parts[0]}-{parts[2]}")
        # Variantes con sufijo numérico
        base_slugs = list(slugs)
        for slug in base_slugs:
            for suffix in ["1", "2", "a", "b"]:
                slugs.append(f"{slug}-{suffix}")

        return list(dict.fromkeys(slugs))

    async def _try_direct_profile(self, name: str) -> list[ScrapedItem]:
        """Último recurso: construir URLs de LinkedIn del nombre y hacer fetch directo."""
        slugs = self._name_to_slugs(name)
        if not slugs:
            return []

        authwall_count = 0
        for slug in slugs[:6]:
            for domain in ["www.linkedin.com", "cl.linkedin.com"]:
                url = f"https://{domain}/in/{slug}"
                try:
                    html = await self._make_request(url)
                    if not html or len(html) < 500:
                        continue

                    if "authwall" in html.lower() or "sign-in" in html[:2000].lower():
                        authwall_count += 1
                        print(f"[LinkedInScraper] Authwall en perfil directo: {url}")
                        if authwall_count >= 2:
                            print("[LinkedInScraper] Multiples authwalls, abortando")
                            return []
                        continue

                    soup = BeautifulSoup(html, "html.parser")

                    title_tag = soup.find("title")
                    title = title_tag.get_text(strip=True) if title_tag else ""

                    snippet_parts = []
                    meta_desc = soup.find("meta", {"name": "description"})
                    if meta_desc and meta_desc.get("content"):
                        snippet_parts.append(meta_desc["content"])
                    og_desc = soup.find("meta", {"property": "og:description"})
                    if og_desc and og_desc.get("content"):
                        snippet_parts.append(og_desc["content"])

                    snippet = " | ".join(snippet_parts) if snippet_parts else ""

                    if title or snippet:
                        print(f"[LinkedInScraper] Perfil directo encontrado: {url}")
                        return [ScrapedItem(
                            url=url,
                            title=title,
                            snippet=snippet,
                            source="linkedin",
                        )]

                except Exception as e:
                    print(f"[LinkedInScraper] Error en perfil directo {url}: {e}")
                    continue
        return []

    async def _enrich_with_profile_page(self, items: list[ScrapedItem]) -> list[ScrapedItem]:
        """Intentar fetch de perfil LinkedIn público para datos más ricos."""
        for item in items:
            if "/in/" not in item.url:
                continue
            try:
                html = await self._make_request(item.url)
                if not html or len(html) < 500:
                    continue

                if "authwall" in html.lower() or "sign-in" in html[:2000].lower():
                    print("[LinkedInScraper] Authwall detectada, usando datos de busqueda")
                    break

                soup = BeautifulSoup(html, "html.parser")
                enriched_parts = []

                # 1. JSON-LD (más rico)
                ld_script = soup.find("script", type="application/ld+json")
                if ld_script:
                    try:
                        ld_data = json.loads(ld_script.string or "")
                        ld_parts = []
                        if isinstance(ld_data, dict):
                            if ld_data.get("name"):
                                ld_parts.append(ld_data["name"])
                            if ld_data.get("jobTitle"):
                                ld_parts.append(ld_data["jobTitle"])
                            works_for = ld_data.get("worksFor")
                            if isinstance(works_for, dict) and works_for.get("name"):
                                ld_parts.append(works_for["name"])
                            elif isinstance(works_for, list):
                                for wf in works_for[:2]:
                                    if isinstance(wf, dict) and wf.get("name"):
                                        ld_parts.append(wf["name"])
                            if ld_data.get("address"):
                                addr = ld_data["address"]
                                if isinstance(addr, dict):
                                    loc = addr.get("addressLocality", "")
                                    region = addr.get("addressRegion", "")
                                    if loc or region:
                                        ld_parts.append(f"Ubicacion: {loc}, {region}".strip(", "))
                            alumni = ld_data.get("alumniOf")
                            if isinstance(alumni, list):
                                for school in alumni[:2]:
                                    if isinstance(school, dict) and school.get("name"):
                                        ld_parts.append(f"Educacion: {school['name']}")
                        if ld_parts:
                            enriched_parts.append(" | ".join(ld_parts))
                    except (json.JSONDecodeError, TypeError):
                        pass

                # 2. Meta description
                meta_desc = soup.find("meta", {"name": "description"})
                if meta_desc and meta_desc.get("content"):
                    enriched_parts.append(meta_desc["content"])

                # 3. OG description
                og_desc = soup.find("meta", {"property": "og:description"})
                if og_desc and og_desc.get("content"):
                    enriched_parts.append(og_desc["content"])

                if enriched_parts:
                    combined = " | ".join(enriched_parts)
                    if len(combined) > len(item.snippet):
                        item.snippet = combined

                title_tag = soup.find("title")
                if title_tag and len(title_tag.get_text(strip=True)) > len(item.title):
                    item.title = title_tag.get_text(strip=True)

            except Exception as e:
                print(f"[LinkedInScraper] Error enriqueciendo perfil: {e}")
                continue
        return items
