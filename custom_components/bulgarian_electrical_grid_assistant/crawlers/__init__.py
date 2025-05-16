"""Crawler package for power interruption providers."""

from .erp import ERPCrawler
from .eryug import ERYUGCrawler

__all__ = ["ERPCrawler", "ERYUGCrawler"]