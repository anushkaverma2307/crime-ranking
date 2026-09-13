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

QUERIES = [
    (
        "Chennai AND "
        "(theft OR robbery OR assault OR murder OR harassment "
        "OR pickpocketing OR \"chain snatching\" OR burglary "
        "OR arrested OR attacked OR killed OR crime)"
    ),
    (
        "Chennai AND "
        "(police OR crime OR criminal OR accused OR suspect)"
    ),
]

THE_HINDU_SOURCE = "the-hindu"

params = {
    "q": "",
    
    "from": start_date.isoformat(),
    "to": end_date.isoformat(),
    "language": "en",
    "sortBy": "publishedAt",
    "pageSize": 100,
    "apiKey": NEWSAPI_KEY,
}

all_articles = []

for query in QUERIES:
    params["q"] = query

    response = requests.get(
        "https://newsapi.org/v2/everything",
        params=params,
        timeout=30,
    )
    response.raise_for_status()

    payload = response.json()

    if payload.get("status") != "ok":
        raise RuntimeError(
            payload.get("message", "NewsAPI request failed.")
        )

    all_articles.extend(payload.get("articles", []))

hindu_params = params.copy()
hindu_params.pop("q", None)
hindu_params["sources"] = THE_HINDU_SOURCE

response = requests.get(
    "https://newsapi.org/v2/everything",
    params=hindu_params,
    timeout=30,
)
response.raise_for_status()

payload = response.json()

if payload.get("status") != "ok":
    raise RuntimeError(
        payload.get("message", "NewsAPI The Hindu request failed.")
    )

all_articles.extend(payload.get("articles", []))

existing = load_existing_articles()
existing_urls = set(existing["url"].dropna().astype(str))
new_records = []

toi_count = 0
hindu_count = 0

for article in all_articles:
    url = (article.get("url") or "").strip()
    domain = urlparse(url).netloc.lower()

    # Reject everything except the two approved newspaper domains.
    if domain not in ALLOWED_DOMAINS:
        continue

    if domain == "timesofindia.indiatimes.com":
        toi_count += 1
    elif domain in {"thehindu.com", "www.thehindu.com"}:
        hindu_count += 1

    title = clean_text(article.get("title", ""))
    description = clean_text(article.get("description", ""))
    combined_text = f"{title} {description}"

    crime_type = classify_crime(combined_text)

    if not title or not url or url in existing_urls or crime_type is None:
        continue

    location = find_location(combined_text)

    if location is None:
        continue

    new_records.append(
        {
            "title": title,
            "source": article.get("source", {}).get("name", domain),
            "published_at": (article.get("publishedAt") or "")[:10],
            "location": location,
            "crime_type": crime_type,
            "url": url,
            "is_reviewed": False,
        }
    )

if not new_records:
    print("No new articles were accepted.")
    print(f"TOI articles found: {toi_count}")
    print(f"The Hindu articles found: {hindu_count}")
    print("No changes were made to articles.csv.")
else:
    print(f"TOI articles found: {toi_count}")
    print(f"The Hindu articles found: {hindu_count}")
    new_data = pd.DataFrame(new_records)
    combined = pd.concat([existing, new_data], ignore_index=True)
    combined = combined.drop_duplicates(subset=["url"], keep="first")
    combined["id"] = range(1, len(combined) + 1)
    combined.to_csv(DATA_PATH, index=False)

    print(f"Added {len(new_records)} real headline records for review.")
    print("They are not displayed until you set is_reviewed to True.")