"""Base scraper abstract class."""
import abc
import logging

from crawler.smartcart.models.product import ScrapedProspekt


class BaseScraper(abc.ABC):
    chain: str = ""

    def __init__(self):
        self.logger = logging.getLogger(f"scraper.{self.chain}")

    @abc.abstractmethod
    async def scrape(self) -> ScrapedProspekt:
        ...
