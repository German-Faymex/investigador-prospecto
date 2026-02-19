"""Ejecuta los 5 scrapers en paralelo."""
import asyncio

from scraper.google_search import GoogleSearchScraper
from scraper.google_news import GoogleNewsScraper
from scraper.linkedin import LinkedInScraper
from scraper.corporate_site import CorporateSiteScraper
from scraper.perplexity import PerplexityScraper
from scraper.base import BaseScraper, ScrapedItem


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
        """Ejecuta todos los scrapers en paralelo y combina resultados."""
        tasks = [s.search(name, company, role, location) for s in self.scrapers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_items = []
        for i, result in enumerate(results):
            if isinstance(result, list):
                all_items.extend(result)
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__}: {len(result)} resultados")
            elif isinstance(result, Exception):
                print(f"[Orchestrator] {self.scrapers[i].__class__.__name__} error: {result}")

        print(f"[Orchestrator] Total: {len(all_items)} resultados combinados")

        await BaseScraper.cleanup()

        return all_items
