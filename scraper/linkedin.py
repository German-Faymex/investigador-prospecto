"""Scraper de LinkedIn con TLS fingerprinting para perfiles públicos.

Pipeline:
  1. DDG API busca URL del perfil (nombre + empresa)
  2. curl_cffi con TLS impersonation fetch el perfil público real
  3. Extrae datos frescos: headline, empresa actual, ubicación, educación, about
"""

import json
import re
import unicodedata
from typing import Optional

from bs4 import BeautifulSoup

from scraper.base import BaseScraper, ScrapedItem
from scraper.tls_client import tls_fetch


class LinkedInScraper(BaseScraper):
    """Busca perfiles de LinkedIn y extrae datos frescos con TLS impersonation.

    Usa DDG para descubrir la URL del perfil, luego curl_cffi con fingerprint
    de browser real para fetch del perfil público sin authwall.
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
        name_parts = name_clean.split()
        name_short = " ".join(name_parts[:2]) if len(name_parts) >= 2 else name_clean

        # Busqueda multi-motor para descubrir URL del perfil LinkedIn
        search_attempts = [
            # DDG: nombre exacto + empresa + rol (mejor match)
            ("ddg", f'"{name}" "{company}" linkedin' + (f' {role}' if role else '')),
            # DDG: nombre corto + empresa + ubicacion
            ("ddg", f'"{name_short}" {company} linkedin' + (f' {location}' if location else ' chile')),
            # DDG: solo nombre + empresa en LinkedIn
            ("ddg", f'"{name_clean}" "{company}" site:linkedin.com/in/'),
            # DDG: nombre corto site filter
            ("ddg", f'"{name_short}" "{company}" site:linkedin.com/in/'),
            # Google como ultimo recurso
            ("google", f'site:linkedin.com/in/ "{name_clean}" "{company}"'),
        ]

        items = []
        for engine, query in search_attempts:
            if engine == "google":
                items = await self._search_google(query)
            else:
                items = await self._search_ddg_api(query, company=company)

            if items:
                print(f"[LinkedInScraper] Encontrado con: {engine} - {query[:60]}...")
                break
            print(f"[LinkedInScraper] Sin resultados: {engine} - {query[:60]}...")

        # Ultimo recurso: URLs directas con TLS
        if not items:
            print("[LinkedInScraper] Buscadores sin resultados, intentando URLs directas")
            items = await self._try_direct_profile(name)

        # Enriquecer con datos frescos del perfil via TLS impersonation
        if items:
            items = await self._deep_enrich_profile(items, name, company)

        return items

    async def _search_google(self, query: str) -> list[ScrapedItem]:
        params = {"q": query, "num": "5", "hl": "es"}
        html = await self._make_request(self.GOOGLE_URL, params=params)
        if not html:
            return []
        return self._parse_google_results(html)

    async def _search_ddg_api(self, query: str, company: str = "") -> list[ScrapedItem]:
        """Search LinkedIn profiles via ddgs library with company filtering."""
        results = await self._ddg_text_search(query, max_results=8)
        company_lower = company.lower().strip() if company else ""
        company_words = [w for w in company_lower.split() if len(w) > 3] if company_lower else []

        matching = []
        non_matching = []
        for r in results:
            url = r.get("href", "")
            if "linkedin.com/in/" not in url:
                continue
            raw_title = r.get("title", "")
            # DDG sometimes returns concatenated titles for LinkedIn results
            # e.g. "Name - Role | LinkedIn Other Title..." — sanitize
            raw_title = self._sanitize_ddg_title(raw_title)

            item = ScrapedItem(
                url=url,
                title=raw_title,
                snippet=r.get("body", ""),
                source="linkedin",
            )
            item_text = f"{item.title} {item.snippet}".lower()
            if company_lower and (company_lower in item_text or any(w in item_text for w in company_words)):
                matching.append(item)
            else:
                non_matching.append(item)

        items = matching[:3] if matching else non_matching[:2]
        if matching and non_matching:
            print(f"[LinkedInScraper] Filtrado anti-homonimia: {len(matching)} match, {len(non_matching)} descartados")
        return items

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
            items.append(ScrapedItem(url=url, title=title, snippet=snippet, source="linkedin"))
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
            slugs.append(f"{parts[0]}-{parts[2]}")
        base_slugs = list(slugs)
        for slug in base_slugs:
            for suffix in ["1", "2", "a", "b"]:
                slugs.append(f"{slug}-{suffix}")
        return list(dict.fromkeys(slugs))

    async def _try_direct_profile(self, name: str) -> list[ScrapedItem]:
        """Ultimo recurso: construir URLs y fetch directo con TLS impersonation."""
        slugs = self._name_to_slugs(name)
        if not slugs:
            return []

        authwall_count = 0
        for slug in slugs[:6]:
            for domain in ["www.linkedin.com", "cl.linkedin.com"]:
                url = f"https://{domain}/in/{slug}"
                try:
                    status, html = await tls_fetch(url, timeout=10)
                    if status == 0 or not html or len(html) < 500:
                        continue

                    if self._is_authwall(html):
                        authwall_count += 1
                        print(f"[LinkedInScraper] Authwall en perfil directo: {url}")
                        if authwall_count >= 2:
                            print("[LinkedInScraper] Multiples authwalls, abortando")
                            return []
                        continue

                    profile_data = self._extract_profile_data(html)
                    if profile_data["title"] or profile_data["snippet"]:
                        print(f"[LinkedInScraper] Perfil directo encontrado: {url}")
                        return [ScrapedItem(
                            url=url,
                            title=profile_data["title"],
                            snippet=profile_data["snippet"],
                            source="linkedin",
                        )]
                except Exception as e:
                    print(f"[LinkedInScraper] Error en perfil directo {url}: {e}")
                    continue
        return []

    async def _deep_enrich_profile(self, items: list[ScrapedItem], name: str, company: str) -> list[ScrapedItem]:
        """Fetch perfil LinkedIn con TLS impersonation para datos frescos.

        Estrategia multi-capa:
          1. TLS fetch con hasta 3 reintentos (distintos fingerprints)
          2. Si authwall (status 999): extraer cargo de DDG snippet titles
          3. Fallback httpx (legacy)

        Desde IP residencial funciona para la mayoria de perfiles.
        Desde datacenter (Railway) solo perfiles publicos pasaran.
        """
        for item in items:
            if "/in/" not in item.url:
                continue

            profile_url = self._normalize_profile_url(item.url)

            # Intentar TLS fetch con hasta 3 profiles distintos
            enriched = False
            for attempt in range(3):
                try:
                    status, html = await tls_fetch(profile_url, timeout=10)

                    if status == 999 or (status == 0 and not html):
                        if attempt < 2:
                            continue  # Reintentar con otro TLS profile
                        print(f"[LinkedInScraper] TLS blocked after {attempt + 1} attempts (status {status})")
                        break

                    if not html or len(html) < 500:
                        continue

                    if self._is_authwall(html):
                        if attempt < 2:
                            continue
                        print("[LinkedInScraper] Authwall persistente, usando datos de busqueda")
                        break

                    profile_data = self._extract_profile_data(html)

                    if profile_data["snippet"] and len(profile_data["snippet"]) > len(item.snippet):
                        item.snippet = profile_data["snippet"]
                        enriched = True
                        print(f"[LinkedInScraper] Perfil enriquecido via TLS (intento {attempt + 1}): {len(item.snippet)} chars")

                    if profile_data["title"] and len(profile_data["title"]) > len(item.title):
                        item.title = profile_data["title"]
                        enriched = True

                    if enriched:
                        break

                except Exception as e:
                    print(f"[LinkedInScraper] TLS attempt {attempt + 1} error: {e}")
                    continue

            # Si TLS no funciono, intentar extraer cargo del titulo DDG
            if not enriched:
                self._enrich_from_ddg_title(item)

            # Solo enriquecer el primer perfil (el mas relevante)
            break

        return items

    @staticmethod
    def _enrich_from_ddg_title(item: ScrapedItem) -> None:
        """Extraer cargo actual del titulo DDG que sigue el patron LinkedIn.

        DDG titles de LinkedIn suelen ser:
          'Nombre Apellido - Cargo actual - Empresa | LinkedIn'
          'Nombre Apellido - Cargo | LinkedIn'
        """
        if not item.title:
            return

        # Parsear titulo como og:title de LinkedIn
        parsed = LinkedInScraper._parse_og_title(item.title)
        if parsed and parsed.get("headline"):
            headline = parsed["headline"]
            # Agregar al snippet si no esta ya
            if headline.lower() not in item.snippet.lower():
                prefix = f"Cargo actual (LinkedIn): {headline}"
                item.snippet = f"{prefix} | {item.snippet}" if item.snippet else prefix
                print(f"[LinkedInScraper] Cargo extraido de titulo DDG: {headline}")

    @staticmethod
    def _is_authwall(html: str) -> bool:
        """Detectar si LinkedIn muestra authwall."""
        lower = html[:3000].lower()
        return any(marker in lower for marker in [
            "authwall", "sign-in", "login-form", "signin", "join linkedin",
        ])

    @staticmethod
    def _normalize_profile_url(url: str) -> str:
        """Normalizar URL de perfil LinkedIn."""
        # Quitar query params y fragments
        url = url.split("?")[0].split("#")[0]
        # Asegurar trailing slash removido
        url = url.rstrip("/")
        # Preferir www.linkedin.com
        url = url.replace("://cl.linkedin.com/", "://www.linkedin.com/")
        url = url.replace("://es.linkedin.com/", "://www.linkedin.com/")
        url = url.replace("://ar.linkedin.com/", "://www.linkedin.com/")
        url = url.replace("://mx.linkedin.com/", "://www.linkedin.com/")
        url = url.replace("://br.linkedin.com/", "://www.linkedin.com/")
        return url

    @staticmethod
    def _extract_profile_data(html: str) -> dict:
        """Extraer datos estructurados de un perfil LinkedIn público.

        LinkedIn expone datos en múltiples capas (prioridad):
          1. JSON-LD @graph: puede tener Person con jobTitle/worksFor, o Articles
          2. og:title: patron "Nombre - Cargo en Empresa | LinkedIn"
          3. Meta description: headline completo con experiencia
          4. og:description: similar a meta description

        Retorna dict con keys: title, snippet, structured (campos individuales).
        """
        soup = BeautifulSoup(html, "html.parser")
        structured: dict = {}
        enriched_parts: list[str] = []

        # 1. JSON-LD (puede ser Person directo o @graph con Articles)
        ld_scripts = soup.find_all("script", type="application/ld+json")
        for ld_script in ld_scripts:
            try:
                ld_data = json.loads(ld_script.string or "")

                # Handle @graph format (LinkedIn 2025+)
                if isinstance(ld_data, dict) and "@graph" in ld_data:
                    for node in ld_data["@graph"]:
                        if not isinstance(node, dict):
                            continue
                        # Extract person info from Article authors
                        author = node.get("author", {})
                        if isinstance(author, dict) and author.get("name"):
                            if not structured.get("name"):
                                structured["name"] = author["name"]

                # Handle direct Person format (legacy)
                elif isinstance(ld_data, dict) and ld_data.get("@type") == "Person":
                    if ld_data.get("name"):
                        structured["name"] = ld_data["name"]
                    if ld_data.get("jobTitle"):
                        structured["headline"] = ld_data["jobTitle"]
                        enriched_parts.append(f"Cargo actual: {ld_data['jobTitle']}")
                    works_for = ld_data.get("worksFor")
                    if isinstance(works_for, dict) and works_for.get("name"):
                        structured["company"] = works_for["name"]
                        enriched_parts.append(f"Empresa: {works_for['name']}")
                    elif isinstance(works_for, list):
                        companies = [wf["name"] for wf in works_for[:2] if isinstance(wf, dict) and wf.get("name")]
                        if companies:
                            structured["company"] = companies[0]
                            enriched_parts.append(f"Empresa: {', '.join(companies)}")
                    if ld_data.get("address") and isinstance(ld_data["address"], dict):
                        loc_parts = [ld_data["address"].get("addressLocality", ""),
                                     ld_data["address"].get("addressRegion", "")]
                        loc = ", ".join(p for p in loc_parts if p)
                        if loc:
                            structured["location"] = loc
                            enriched_parts.append(f"Ubicacion: {loc}")
                    alumni = ld_data.get("alumniOf")
                    if isinstance(alumni, list):
                        schools = [s["name"] for s in alumni[:3] if isinstance(s, dict) and s.get("name")]
                        if schools:
                            structured["education"] = schools
                            enriched_parts.append(f"Educacion: {', '.join(schools)}")

            except (json.JSONDecodeError, TypeError):
                pass

        # 2. og:title — "Nombre - Cargo en Empresa | LinkedIn" (muy confiable)
        og_title = soup.find("meta", {"property": "og:title"})
        if og_title and og_title.get("content"):
            og_title_text = og_title["content"]
            parsed = LinkedInScraper._parse_og_title(og_title_text)
            if parsed:
                if parsed.get("headline") and not structured.get("headline"):
                    structured["headline"] = parsed["headline"]
                    enriched_parts.insert(0, f"Cargo actual: {parsed['headline']}")
                if parsed.get("name") and not structured.get("name"):
                    structured["name"] = parsed["name"]

        # 3. Meta description (resumen del perfil con experiencia)
        meta_desc = soup.find("meta", {"name": "description"})
        if meta_desc and meta_desc.get("content"):
            desc = meta_desc["content"]
            enriched_parts.append(desc)
            if not structured.get("about"):
                structured["about_meta"] = desc

        # 4. OG description (similar, evitar duplicar)
        og_desc = soup.find("meta", {"property": "og:description"})
        if og_desc and og_desc.get("content"):
            og = og_desc["content"]
            if og not in enriched_parts:
                enriched_parts.append(og)

        # 5. Title tag
        title = ""
        title_tag = soup.find("title")
        if title_tag:
            title = title_tag.get_text(strip=True)

        # Construir snippet combinado
        snippet = " | ".join(enriched_parts) if enriched_parts else ""

        return {
            "title": title,
            "snippet": snippet,
            "structured": structured,
        }

    @staticmethod
    def _parse_og_title(og_title: str) -> Optional[dict]:
        """Parsear og:title de LinkedIn: 'Nombre - Cargo en Empresa | LinkedIn'.

        Ejemplos reales:
          'Bill Gates - Chair, Gates Foundation and Founder, Breakthrough Energy | LinkedIn'
          'Germán Peralta - Jefe de Inteligencia de Negocios - Faymex | LinkedIn'
        """
        # Quitar " | LinkedIn" del final
        cleaned = re.sub(r"\s*\|\s*LinkedIn\s*$", "", og_title).strip()
        if not cleaned:
            return None

        # Separar nombre del cargo: "Nombre - Cargo" o "Nombre – Cargo"
        parts = re.split(r"\s*[-–]\s*", cleaned, maxsplit=1)
        if len(parts) < 2:
            return {"name": cleaned}

        name = parts[0].strip()
        headline = parts[1].strip()

        return {"name": name, "headline": headline} if headline else {"name": name}

    @staticmethod
    def _sanitize_ddg_title(title: str) -> str:
        """Clean up DDG title that may contain concatenated results.

        DDG sometimes returns multiple page titles mashed together:
          "Name - Role | LinkedIn Other Page Title - Wikipedia ..."
          "Name - Role at Company ... Name - Other Title"
        """
        if not title or len(title) < 80:
            return title

        # Cut at "| LinkedIn" (clean marker)
        li_pipe = title.find("| LinkedIn")
        if li_pipe > 0:
            return title[:li_pipe + len("| LinkedIn")]

        # Cut at " - LinkedIn" (alternative marker)
        li_dash = title.find(" - LinkedIn")
        if li_dash > 0:
            return title[:li_dash + len(" - LinkedIn")]

        # If title is very long, it's likely concatenated — cap at first meaningful break
        # Look for known junk markers (Wikipedia, Forbes, etc.)
        for marker in [" - Wikipedia", " - Forbes", " - CEO.wiki", " - The Org",
                        " - Source", " - Business Standard", "Who is "]:
            idx = title.find(marker)
            if idx > 20:
                return title[:idx].rstrip()

        # Fallback: cap at 120 chars at word boundary
        if len(title) > 120:
            cut = title[:120].rfind(" ")
            if cut > 40:
                return title[:cut] + "..."

        return title

    async def _enrich_with_profile_page(self, items: list[ScrapedItem]) -> list[ScrapedItem]:
        """Fallback: enriquecer con httpx (sin TLS impersonation)."""
        for item in items:
            if "/in/" not in item.url:
                continue
            try:
                html = await self._make_request(item.url)
                if not html or len(html) < 500:
                    continue

                if self._is_authwall(html):
                    print("[LinkedInScraper] Authwall detectada (httpx fallback), usando datos de busqueda")
                    break

                profile_data = self._extract_profile_data(html)
                if profile_data["snippet"] and len(profile_data["snippet"]) > len(item.snippet):
                    item.snippet = profile_data["snippet"]

                if profile_data["title"] and len(profile_data["title"]) > len(item.title):
                    item.title = profile_data["title"]

            except Exception as e:
                print(f"[LinkedInScraper] Error enriqueciendo perfil (fallback): {e}")
                continue
        return items
