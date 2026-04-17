"""Tech news sources configuration."""

SOURCES = {
    "hackernews": {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com",
        "feed_url": "https://hnrss.org/frontpage",
        "type": "rss",
        "description": "Top stories from Y Combinator's Hacker News"
    },
    "techcrunch": {
        "name": "TechCrunch",
        "url": "https://techcrunch.com",
        "feed_url": "https://techcrunch.com/feed/",
        "type": "rss",
        "description": "Startup and technology news"
    },
    "theverge": {
        "name": "The Verge",
        "url": "https://www.theverge.com",
        "feed_url": "https://www.theverge.com/rss/index.xml",
        "type": "rss",
        "description": "Technology, science, art, and culture"
    },
    "arstechnica": {
        "name": "Ars Technica",
        "url": "https://arstechnica.com",
        "feed_url": "https://feeds.arstechnica.com/arstechnica/index",
        "type": "rss",
        "description": "Technology news and analysis"
    },
    "wired": {
        "name": "Wired",
        "url": "https://www.wired.com",
        "feed_url": "https://www.wired.com/feed/rss",
        "type": "rss",
        "description": "Ideas, science, technology, and culture"
    },
    "thenewstack": {
        "name": "The New Stack",
        "url": "https://thenewstack.io",
        "feed_url": "https://thenewstack.io/feed/",
        "type": "rss",
        "description": "Dev tools, infrastructure, and cloud native"
    },
    "bleepingcomputer": {
        "name": "BleepingComputer",
        "url": "https://www.bleepingcomputer.com",
        "feed_url": "https://www.bleepingcomputer.com/feed/",
        "type": "rss",
        "description": "Cybersecurity and technology news"
    },
    "mittech": {
        "name": "MIT Technology Review",
        "url": "https://www.technologyreview.com",
        "feed_url": "https://www.technologyreview.com/feed/",
        "type": "rss",
        "description": "Emerging technology insights from MIT"
    },
    "venturebeat": {
        "name": "VentureBeat",
        "url": "https://venturebeat.com",
        "feed_url": "https://venturebeat.com/feed/",
        "type": "rss",
        "description": "AI, gaming, and transformative tech"
    },
    "darkread": {
        "name": "Dark Reading",
        "url": "https://www.darkreading.com",
        "feed_url": "https://www.darkreading.com/rss.xml",
        "type": "rss",
        "description": "Cybersecurity news and threat intelligence"
    }
}


def get_all_sources():
    return [
        {"id": key, "name": val["name"], "description": val["description"]}
        for key, val in SOURCES.items()
    ]


def get_source(source_id: str):
    return SOURCES.get(source_id)
