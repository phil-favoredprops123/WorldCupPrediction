"""
World Cup Qualifiers Scrapers Package

This package contains scrapers for collecting FIFA World Cup qualifying standings
from ESPN and calculating team qualification probabilities.
"""

from scrapers.confederation_scraper import (
    ConfederationScraper,
    ConfederationStandingsCollector,
    EspnStandingsScraper,
    GroupStanding,
    StandingEntry,
    build_default_scrapers,
)

__all__ = [
    "ConfederationScraper",
    "ConfederationStandingsCollector",
    "EspnStandingsScraper",
    "GroupStanding",
    "StandingEntry",
    "build_default_scrapers",
]


