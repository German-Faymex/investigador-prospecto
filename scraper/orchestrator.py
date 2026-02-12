"""Ejecuta los 4 scrapers en paralelo."""
import asyncio

from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.base import ScrapedItem


class ScraperOrchestrator:
    def __init__(self):
        self.scrapers = [
            GoogleSearchScraper(),
            GoogleNewsScraper(),
            LinkedInScraper(),
            CorporateSiteScraper(),
        ]

    async def search_all(self, name: str, company: str, role: str = "") -> list[ScrapedItem]:
        """Ejecuta todos los scrapers en paralelo y combina resultados."""
        tasks = [s.search(name, company, role) for s in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_items.extend(result)
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__}: {len(result)} resultados")
            elif isinstance(result, Exception):
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__} error: {result}")

        print(f"[Orchestrator] Total: {len(all_items)} resultados combinados")
        return all_items
