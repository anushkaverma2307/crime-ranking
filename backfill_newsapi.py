from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
import tomllib

import pandas as pd
import requests

from collector import (
    DATA_PATH,
    clean_text,
    classify_crime,
    find_location,
    load_existing_articles,
)

ALLOWED_DOMAINS = {
    "timesofindia.indiatimes.com",
    "thehindu.com",
    "www.thehindu.com",
}

with open(Path(".streamlit/secrets.toml"), "rb") as file:
    NEWSAPI_KEY = tomllib.load(file)["NEWSAPI_KEY"]

end_date = date.today()
start_date = end_date - timedelta(days=30)

params = {
    "q": (
        "Chennai AND "
        "(theft OR robbery OR assault OR murder OR harassment "
        "OR pickpocketing OR \"chain snatching\" OR hacked OR killed)"
    ),
    
    "from": start_date.isoformat(),
    "to": end_date.isoformat(),
    "language": "en",
    "sortBy": "publishedAt",
    "pageSize": 100,
    "apiKey": NEWSAPI_KEY,
}

response = requests.get(
    "https://newsapi.org/v2/everything",
    params=params,
    timeout=30,
)
response.raise_for_status()

payload = response.json()

if payload.get("status") != "ok":
    raise RuntimeError(payload.get("message", "NewsAPI request failed."))

existing = load_existing_articles()
existing_urls = set(existing["url"].dropna().astype(str))
new_records = []

for article in payload.get("articles", []):
    url = (article.get("url") or "").strip()
    domain = urlparse(url).netloc.lower()

    # Reject everything except the two approved newspaper domains.
    if domain not in ALLOWED_DOMAINS:
        continue

    title = clean_text(article.get("title", ""))
    description = clean_text(article.get("description", ""))
    combined_text = f"{title} {description}"

    crime_type = classify_crime(combined_text)

    if not title or not url or url in existing_urls or crime_type is None:
        continue

    new_records.append(
        {
            "title": title,
            "source": article.get("source", {}).get("name", domain),
            "published_at": (article.get("publishedAt") or "")[:10],
            "location": find_location(combined_text) or "Chennai (General)",
            "crime_type": crime_type,
            "url": url,
            "is_reviewed": False,
        }
    )

if not new_records:
    print("No matching TOI/The Hindu articles were returned for the past month.")
    print("This can mean NewsAPI does not currently carry these sources.")
else:
    new_data = pd.DataFrame(new_records)
    combined = pd.concat([existing, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=["url"], keep="first")
    combined["id"] = range(1, len(combined) + 1)
    combined.to_csv(DATA_PATH, index=False)

    print(f"Added {len(new_records)} real headline records for review.")
    print("They are not displayed until you set is_reviewed to True.")