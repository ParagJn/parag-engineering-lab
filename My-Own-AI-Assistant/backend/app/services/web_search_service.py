"""Web search service using DuckDuckGo (no API key required)."""


class WebSearchService:
    """Service for performing web searches."""

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """
        Search the web for a query.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of dicts with 'title', 'url', 'snippet'
        """
        try:
            from ddgs import DDGS

            results = DDGS().text(query, max_results=max_results)
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                }
                for r in results
            ]
        except Exception as e:
            return [{"title": "Search error", "url": "", "snippet": f"Web search failed: {str(e)}"}]

    def format_results(self, query: str, results: list[dict]) -> str:
        """Format search results as text for the model."""
        if not results:
            return f'No web search results found for "{query}".'

        parts = [f'Web search results for "{query}":\n']
        for i, r in enumerate(results, 1):
            parts.append(f"{i}. {r['title']}\n   {r['url']}\n   {r['snippet']}")
        return "\n\n".join(parts)


# Singleton instance
_web_search_service: WebSearchService | None = None


def get_web_search_service() -> WebSearchService:
    """Get web search service singleton."""
    global _web_search_service
    if _web_search_service is None:
        _web_search_service = WebSearchService()
    return _web_search_service
