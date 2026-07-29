import feedparser

RSS_FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://krebsonsecurity.com/feed/",
    "https://www.darkreading.com/rss.xml",
]

def fetch_articles():

    articles = []
    seen_links = set()

    for url in RSS_FEEDS:

        feed = feedparser.parse(url)

        for entry in feed.entries:

            link = entry.get("link")

            # Skip duplicates
            if link in seen_links:
                continue
            
            seen_links.add(link)
            
            article = {
                "title": entry.get("title"),
                "link": entry.get("link"),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": feed.feed.get("title", "Unknown")
            }

            articles.append(article)
        
    return articles