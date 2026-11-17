"""
Base classes and interfaces for data sources.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseSource(ABC):
    """
    Abstract adapter for extracting articles/pages from any web source.
    """
    def __init__(self, base_url: str, config: Optional[Dict[str, Any]] = None):
        self.base_url = base_url.rstrip('/')
        self.config = config or {}

    @abstractmethod
    def detect_capabilities(self) -> Dict[str, Any]:
        """
        Probe source and return detected API capabilities:
        e.g., {'has_json_api': True, 'api_type': 'wordpress_rest', 'api_url': '...', 'post_count': 494}
        """
        pass

    @abstractmethod
    def fetch_items(self, count: int = 5, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Fetch raw items from the source.
        """
        pass

    @abstractmethod
    def fetch_tags(self) -> List[Dict[str, Any]]:
        """
        Fetch available tags/categories from the source.
        """
        pass
