from datetime import datetime
from html import unescape
from pathlib import Path
import re
import time

import feedparser
import pandas as pd

DATA_PATH = Path("data/articles.csv")

# Use only RSS/API sources you are permitted to collect and display.
FEEDS = {
    "Times of India — Chennai": "https://timesofindia.indiatimes.com/rssfeeds/2950623.cms",
    "The Hindu — Chennai": "https://www.thehindu.com/news/cities/chennai/feeder/default.rss",
}

CHENNAI_AREAS = [
    "Adyar",
    "Ambattur",
    "Anna Nagar",
    "Avadi",
    "Besant Nagar",
    "Chromepet",
    "Chengalpattu",
    "Chengalpet",
    "Chintadripet",
    "Egmore",
    "Guindy",
    "Kodambakkam",
    "Madhavaram",
    "Medavakkam",
    "Mylapore",
    "Nanganallur",
    "Nungambakkam",
    "Pallavaram",
    "Perambur",
    "Porur",
    "Royapettah",
    "Saidapet",
    "Sholinganallur",
    "Tambaram",
    "T. Nagar",
    "T Nagar",
    "Teynampet",
    "Thiruvanmiyur",
    "Triplicane",
    "Velachery",
]

CRIME_KEYWORDS = {
    "Pickpocketing": ["pickpocket", "pickpocketing", "wallet stolen"],
    "Theft": ["theft", "stolen", "robbery", "robbed", "chain snatching", "burglary"],
    "Harassment": ["harassment", "eve teasing", "molestation", "stalking"],
    "Assault": ["assault", "attacked", "attack", "murder", "homicide"],
    "Vandalism": ["vandalism", "damaged property", "defaced"],
}


def clean_text(text):
    """Remove basic HTML from RSS summaries."""
    no_html = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", unescape(no_html)).strip()


def find_location(text):
    for area in CHENNAI_AREAS:
        if re.search(rf"\b{re.escape(area)}\b", text, flags=re.IGNORECASE):
            return area
    return None


def classify_crime(text):
    text = text.lower()

    for crime_type, keywords in CRIME_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return crime_type

    return None


def get_date(entry):
    """Use the RSS publication date when available."""
    if entry.get("published_parsed"):
        timestamp = time.mktime(entry.published_parsed)
        return datetime.fromtimestamp(timestamp).date().isoformat()

    return datetime.today().date().isoformat()


def load_existing_articles():
    if DATA_PATH.exists():
        return pd.read_csv(DATA_PATH)

    return pd.DataFrame(
        columns=[
            "id",
            "title",
            "source",
            "published_at",
            "location",
            "crime_type",
            "url",
            "is_reviewed",
        ]
    )


def collect_articles():
    existing = load_existing_articles()
    existing_urls = set(existing["url"].dropna().astype(str))
    new_records = []

    for source, feed_url in FEEDS.items():
        if "PASTE_A_PERMITTED" in feed_url:
            print(f"Skipping {source}: add a permitted RSS URL first.")
            continue

        feed = feedparser.parse(feed_url)

        if feed.bozo:
            print(f"Warning: {source} may not be a valid RSS feed: {feed.bozo_exception}")

        for entry in feed.entries:
            title = clean_text(entry.get("title", ""))
            summary = clean_text(entry.get("summary", ""))
            url = entry.get("link", "").strip()

            if not title or not url or url in existing_urls:
                continue

            combined_text = f"{title} {summary}"
            crime_type = classify_crime(combined_text)
            location = find_location(combined_text)
            if crime_type is None:
                print(f"Skipped — no crime category: {title}")
                continue

            if location is None:
                print(f"Needs location review: {title}")
                continue

            new_records.append(
                {
                    "title": title,
                    "source": source,
                    "published_at": get_date(entry),
                    "location": location,
                    "crime_type": crime_type,
                    "url": url,
                    "is_reviewed": False,
                }
            )

    if not new_records:
        print("No new matching records found.")
        return

    new_articles = pd.DataFrame(new_records)
    combined = pd.concat([existing, new_articles], ignore_index=True)
    combined = combined.drop_duplicates(subset=["url"], keep="first")
    combined["id"] = range(1, len(combined) + 1)

    combined.to_csv(DATA_PATH, index=False)
    print(f"Added {len(new_articles)} new record(s).")
    print("Review data/articles.csv before setting is_reviewed to True.")


if __name__ == "__main__":
    collect_articles()