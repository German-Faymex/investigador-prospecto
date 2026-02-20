"""Ejecuta los 5 scrapers en paralelo con timeout diferenciado."""
import asyncio
import time

from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.perplexity import PerplexityScraper
from scraper.base import BaseScraper, ScrapedItem

# Timeouts diferenciados: Perplexity es API (confiable, lenta),
# el resto son scrapers web (poco confiables desde datacenter IPs).
WEB_SCRAPE_TIMEOUT = 12  # Google/DDG/LinkedIn (a menudo bloqueados)
PERPLEXITY_TIMEOUT = 30  # API confiable, necesita más tiempo


class ScraperOrchestrator:
    def __init__(self):
        self.linkedin_scraper = LinkedInScraper()
        self.corporate_scraper = CorporateSiteScraper()
        self.google_scraper = GoogleSearchScraper()
        self.news_scraper = GoogleNewsScraper()
        self.perplexity_scraper = PerplexityScraper()

        # Scrapers web (pueden bloquearse, timeout corto)
        self.web_scrapers = [
            self.linkedin_scraper,
            self.corporate_scraper,
            self.google_scraper,
            self.news_scraper,
        ]

    @property
    def discovered_domain(self) -> str | None:
        """Dominio corporativo descubierto durante el scraping."""
        return self.corporate_scraper.discovered_domain

    async def search_all(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        """Ejecuta scrapers web y Perplexity API con timeouts diferenciados.

        - Scrapers web (Google, DDG, LinkedIn, Corporate): 12s timeout
        - Perplexity API: 30s timeout (más confiable, más lenta)

        Esto asegura que Perplexity complete incluso si los scrapers web fallan.
        """
        t0 = time.perf_counter()

        # Lanzar todos en paralelo
        web_tasks = {
            asyncio.create_task(s.search(name, company, role, location)): s
            for s in self.web_scrapers
        }
        pplx_task = asyncio.create_task(
            self.perplexity_scraper.search(name, company, role, location)
        )

        # Esperar scrapers web con timeout corto
        done_web, pending_web = await asyncio.wait(
            web_tasks.keys(), timeout=WEB_SCRAPE_TIMEOUT
        )

        # Cancelar web scrapers lentos
        for task in pending_web:
            scraper = web_tasks[task]
            task.cancel()
            print(f"[Orchestrator] {scraper.__class__.__name__} cancelado (timeout {WEB_SCRAPE_TIMEOUT}s)")

        # Recopilar resultados web
        all_items = []
        for task in done_web:
            scraper = web_tasks[task]
            try:
                result = task.result()
                if isinstance(result, list):
                    all_items.extend(result)
                    print(f"[Orchestrator] {scraper.__class__.__name__}: {len(result)} items")
                else:
                    print(f"[Orchestrator] {scraper.__class__.__name__}: 0 items")
            except Exception as e:
                print(f"[Orchestrator] {scraper.__class__.__name__} error: {e}")

        web_elapsed = time.perf_counter() - t0
        print(f"[Orchestrator] Web scrapers: {len(all_items)} items en {web_elapsed:.1f}s")

        # Esperar Perplexity con timeout generoso
        remaining_pplx_time = max(PERPLEXITY_TIMEOUT - web_elapsed, 10)
        try:
            done_pplx, pending_pplx = await asyncio.wait(
                {pplx_task}, timeout=remaining_pplx_time
            )
            if pplx_task in done_pplx:
                try:
                    pplx_result = pplx_task.result()
                    if isinstance(pplx_result, list):
                        all_items.extend(pplx_result)
                        print(f"[Orchestrator] PerplexityScraper: {len(pplx_result)} items")
                    else:
                        print(f"[Orchestrator] PerplexityScraper: 0 items")
                except Exception as e:
                    print(f"[Orchestrator] PerplexityScraper error: {e}")
            else:
                pplx_task.cancel()
                print(f"[Orchestrator] PerplexityScraper cancelado (timeout {remaining_pplx_time:.0f}s)")
        except Exception as e:
            print(f"[Orchestrator] Error esperando Perplexity: {e}")

        elapsed = time.perf_counter() - t0
        print(f"[Orchestrator] Total: {len(all_items)} items en {elapsed:.1f}s")

        await BaseScraper.cleanup()

        return all_items
