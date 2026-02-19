"""Ejecuta los 5 scrapers en paralelo con timeout global."""
import asyncio
import time

from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.perplexity import PerplexityScraper
from scraper.base import BaseScraper, ScrapedItem

# Timeout global para la fase de scraping (segundos).
# Si un scraper no termina a tiempo, se cancela sin bloquear el pipeline.
SCRAPE_TIMEOUT = 15


class ScraperOrchestrator:
    def __init__(self):
        self.linkedin_scraper = LinkedInScraper()
        self.corporate_scraper = CorporateSiteScraper()
        self.google_scraper = GoogleSearchScraper()
        self.news_scraper = GoogleNewsScraper()
        self.perplexity_scraper = PerplexityScraper()
        self.scrapers = [
            self.linkedin_scraper,
            self.corporate_scraper,
            self.google_scraper,
            self.news_scraper,
            self.perplexity_scraper,
        ]

    @property
    def discovered_domain(self) -> str | None:
        """Dominio corporativo descubierto durante el scraping."""
        return self.corporate_scraper.discovered_domain

    async def search_all(self, name: str, company: str, role: str = "", location: str = "") -> list[ScrapedItem]:
        """Ejecuta todos los scrapers en paralelo con timeout global.

        Scrapers que no terminan dentro del timeout se cancelan silenciosamente
        para no bloquear el pipeline. Perplexity y Corporate son los más valiosos;
        Google/DDG/LinkedIn a menudo están bloqueados y pueden descartarse.
        """
        t0 = time.perf_counter()

        task_map = {
            asyncio.create_task(s.search(name, company, role, location)): s
            for s in self.scrapers
        }

        done, pending = await asyncio.wait(task_map.keys(), timeout=SCRAPE_TIMEOUT)

        # Cancelar scrapers lentos
        for task in pending:
            scraper = task_map[task]
            task.cancel()
            print(f"[Orchestrator] {scraper.__class__.__name__} cancelado (timeout {SCRAPE_TIMEOUT}s)")

        all_items = []
        for task in done:
            scraper = task_map[task]
            try:
                result = task.result()
                if isinstance(result, list):
                    all_items.extend(result)
                    print(f"[Orchestrator] {scraper.__class__.__name__}: {len(result)} resultados")
            except Exception as e:
                print(f"[Orchestrator] {scraper.__class__.__name__} error: {e}")

        elapsed = time.perf_counter() - t0
        print(f"[Orchestrator] Total: {len(all_items)} resultados en {elapsed:.1f}s")

        await BaseScraper.cleanup()

        return all_items
