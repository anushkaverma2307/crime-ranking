from pathlib import Path
import hashlib

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

CSS_PATH = Path("style.css")

with open(CSS_PATH) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Chennai Safety Dashboard", page_icon="🛡️", layout="wide")

DATA_PATH = Path("data/articles.csv")

TIME_WINDOWS = [
    "Morning (6 AM – 12 PM)",
    "Afternoon (12 PM – 5 PM)",
    "Evening (5 PM – 9 PM)",
    "Night (9 PM – 6 AM)",
]


def assign_time_window(row_key):
    """Assign an article a stable, ILLUSTRATIVE time-of-day window.

    The underlying news data only records a publish DATE, not the time a
    crime actually occurred. Until real incident timestamps are collected
    (e.g. from police FIR data), this deterministically spreads articles
    across the four windows above for demo purposes only. It is NOT derived
    from real reported crime times.
    """
    digest = hashlib.md5(str(row_key).encode()).hexdigest()
    return TIME_WINDOWS[int(digest, 16) % len(TIME_WINDOWS)]


@st.cache_data
def load_articles(file_modified_at):
    """Load only reviewed collector records.

    file_modified_at changes whenever collector.py updates the CSV,
    which refreshes Streamlit's cache automatically.
    """
    if not DATA_PATH.exists():
        return pd.DataFrame()

    articles = pd.read_csv(DATA_PATH)

    required_columns = {
        "title",
        "source",
        "published_on",
        "location",
        "crime_type",
        "url",
        "is_reviewed",
    }

    missing_columns = required_columns - set(articles.columns)
    if missing_columns:
        raise ValueError(
            "articles.csv is missing: " + ", ".join(sorted(missing_columns))
        )

    articles = articles.copy()

    articles["published_on"] = pd.to_datetime(
        articles["published_on"],
        errors="coerce",
    )

    # Stable per-article key so each row always lands in the same
    # illustrative time window across reruns, instead of jumping around.
    articles["time_window"] = articles["url"].astype(str).apply(assign_time_window)

    return articles


CHENNAI_LOCATIONS = {
    "Adyar": (13.0012, 80.2565),
    "Ambattur": (13.1143, 80.1548),
    "Anna Nagar": (13.0878, 80.2081),
    "Avadi": (13.1147, 80.1098),
    "Besant Nagar": (13.0003, 80.2668),
    "Chengalpattu": (12.6819, 79.9888),
    "Chengalpet": (12.6819, 79.9888),
    "Chromepet": (12.9516, 80.1462),
    "Chintadripet": (13.0732, 80.2695),
    "Egmore": (13.0732, 80.2609),
    "Guindy": (13.0067, 80.2206),
    "Kodambakkam": (13.0518, 80.2210),
    "Madhavaram": (13.1480, 80.2310),
    "Medavakkam": (12.9229, 80.1926),
    "Mylapore": (13.0339, 80.2676),
    "Nanganallur": (12.9784, 80.1847),
    "Nungambakkam": (13.0569, 80.2425),
    "Pallavaram": (12.9675, 80.1491),
    "Perambur": (13.1075, 80.2336),
    "Porur": (13.0359, 80.1565),
    "Royapettah": (13.0526, 80.2636),
    "Saidapet": (13.0213, 80.2231),
    "Sholinganallur": (12.9010, 80.2279),
    "Tambaram": (12.9249, 80.1000),
    "T. Nagar": (13.0418, 80.2341),
    "T Nagar": (13.0418, 80.2341),
    "Teynampet": (13.0410, 80.2560),
    "Thiruvanmiyur": (12.9830, 80.2594),
    "Triplicane": (13.0588, 80.2756),
    "Velachery": (12.9750, 80.2212),
}


def show_location_map(place):
    if place not in CHENNAI_LOCATIONS:
        return

    latitude, longitude = CHENNAI_LOCATIONS[place]

    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=13,
        tiles="OpenStreetMap",
    )

    folium.CircleMarker(
        location=[latitude, longitude],
        radius=120,
        color="#FFE200",
        weight=2,
        fill=True,
        fill_color="#FFE200",
        fill_opacity=0.25,
        tooltip=place,
    ).add_to(m)

    folium.Marker(
        location=[latitude, longitude],
        tooltip=place,
        popup=f"<b>{place}</b>",
    ).add_to(m)

    st_folium(
        m,
        width="100%",
        height=450,
        returned_objects=[],
    )


def rate_time_window(window_count):
    """Return a Red/Yellow/Green illustrative rating for a chosen time window.

    These are simple demo cutoffs, not a calibrated risk model -- they exist
    to show how the interface would behave once real incident-time data is
    available.
    """
    if window_count == 0:
        return "Green — comparatively safer, no reports in this window", "🟢"
    elif window_count <= 2:
        return "Yellow — comparatively safer, a few reports in this window", "🟡"
    else:
        return "Red — higher reported activity in this window", "🔴"


st.title("🛡️ Chennai Safety Dashboard")
st.caption(
    "A safety indicator based on reported news and your planned arrival time "
    "— not an official crime rate or a safety guarantee."
)

articles = load_articles(DATA_PATH.stat().st_mtime)

if articles.empty:
    st.info(
        "No reviewed news records are available yet. "
        "Run collector.py, review the rows in data/articles.csv, "
        "then set is_reviewed to True."
    )
    st.stop()

st.caption(
    f"Showing {len(articles)} reviewed reported-news record(s)."
)

with st.sidebar:
    st.header("About the time-window rating")
    st.write(
        "The underlying news data only records a publish date, not the time "
        "a crime occurred. Morning / Afternoon / Evening / Night windows are "
        "currently assigned illustratively for demo purposes, not from real "
        "reported crime times."
    )

st.subheader("Search a Chennai locality")
left, spacer, right = st.columns([0.41, 0.04, 0.55])

with left:
    locations = sorted(articles["location"].dropna().unique())
    place = st.selectbox(
        "Location",
        locations,
        index=None,
        placeholder="Choose a location"
    )

    if place:
        show_location_map(place)

with right:
    if place:
        results = articles[
            articles["location"].str.lower() == place.lower()
        ].copy()

        st.subheader(f"When are you planning to reach {place}?")
        selected_window = st.radio(
            "Arrival time window",
            TIME_WINDOWS,
            horizontal=True,
            label_visibility="collapsed",
        )
        st.caption(
            "⚠️ Time windows are illustrative placeholders for this demo — "
            "they are not derived from real reported crime times."
        )

        window_results = results[results["time_window"] == selected_window]
        window_count = len(window_results)
        tag, icon = rate_time_window(window_count)

        first, second, third = st.columns(3)
        first.metric("Reports in this window", window_count)
        second.metric("Total reports at this place", len(results))
        third.metric(
            "Highest concern (all-time)",
            results["crime_type"].mode().iat[0] if not results.empty else "No data",
        )

        st.subheader(f"{icon} {tag}")
        st.write(
            f"Based on {window_count} illustratively-windowed article record(s) out of "
            f"{len(results)} total reports for {place} during the "
            f"'{selected_window}' window."
        )

        breakdown = (
            results.groupby("crime_type").size().reset_index(name="reported_articles")
            .sort_values("reported_articles", ascending=False)
        )

        if not breakdown.empty:
            top_row = breakdown.iloc[0]
            top_crime_type = top_row["crime_type"]
            top_crime_count = int(top_row["reported_articles"])
            top_crime_share = top_crime_count / len(results)

            # Only call a crime type "frequent" when it's a real pattern, not
            # just one or two stray reports: a minimum count and a clear lead
            # over the other categories.
            if top_crime_count >= 3 and top_crime_share >= 0.4:
                st.warning(
                    f"📌 This place has frequently observed **{top_crime_type}** — "
                    f"{top_crime_count} of {len(results)} reported article(s) "
                    f"({top_crime_share:.0%}) for {place} are about {top_crime_type.lower()}."
                )

        st.subheader("Why this tag?")
        breakdown["reported_articles"] = breakdown["reported_articles"].astype(str)

        st.dataframe(
            breakdown,
            hide_index=True,
            use_container_width=True,
        )

        st.subheader("Source articles")

        filter_option = st.radio(
            "Show reports from",
            ["All reports", "Past 1 week", "Past 2 weeks", "Past 1 month"],
            horizontal=True,
            label_visibility="collapsed",
        )

        report_data = results.copy()
        report_data["published_on"] = pd.to_datetime(report_data["published_on"])

        if filter_option == "Past 1 week":
            cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=7)
            report_data = report_data[report_data["published_on"] >= cutoff]

        elif filter_option == "Past 2 weeks":
            cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=14)
            report_data = report_data[report_data["published_on"] >= cutoff]

        elif filter_option == "Past 1 month":
            cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=30)
            report_data = report_data[report_data["published_on"] >= cutoff]

        st.dataframe(
            report_data.assign(
                published_on=report_data["published_on"].dt.strftime("%Y-%m-%d")
            )[["published_on", "crime_type", "source", "title", "url"]]
            .sort_values("published_on", ascending=False),
            hide_index=True,
            use_container_width=True,
            column_config={"url": st.column_config.LinkColumn("Source link")},
        )
    else:
        st.info("Choose a location to see its time-window rating and the article records behind it.")
