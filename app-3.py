from pathlib import Path
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Chennai Safety Dashboard",
    page_icon="🛡️",
    layout="wide"
)

DATA_PATH = Path("data/articles.csv")

TIME_PERIODS = {
    "Morning": "6 AM – 12 PM",
    "Afternoon": "12 PM – 5 PM",
    "Evening": "5 PM – 9 PM",
    "Night": "9 PM – 6 AM"
}

CHENNAI_LOCATIONS = {
    "Adyar": (13.0012, 80.2565),
    "Ambattur": (13.1143, 80.1548),
    "Anna Nagar": (13.0878, 80.2081),
    "Avadi": (13.1147, 80.1098),
    "Besant Nagar": (13.0003, 80.2668),
    "Chengalpet": (12.6819, 79.9888),
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
    "Velachery": (12.9750, 80.2212)
}


@st.cache_data
def load_articles():
    if not DATA_PATH.exists():
        st.error("Could not find data/articles.csv")
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
        "time_period"
    }

    missing_columns = required_columns - set(articles.columns)

    if missing_columns:
        st.error(
            "articles.csv is missing these columns: "
            + ", ".join(sorted(missing_columns))
        )
        st.info(
            "Add a time_period column containing Morning, Afternoon, "
            "Evening, or Night for each record."
        )
        return pd.DataFrame()

    articles["location"] = (
        articles["location"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    articles["time_period"] = (
        articles["time_period"]
        .fillna("")
        .astype(str)
        .str.strip()
        .str.title()
    )

    articles["published_on"] = pd.to_datetime(
        articles["published_on"],
        errors="coerce"
    )

    return articles


def get_activity_level(count):
    if count == 0:
        return "green", "🟢", "No reported incidents"
    elif count <= 2:
        return "green", "🟢", "Lower reported crime activity"
    elif count <= 5:
        return "yellow", "🟡", "Moderate reported crime activity"
    else:
        return "red", "🔴", "Higher reported crime activity"


def show_location_map(place):
    if place not in CHENNAI_LOCATIONS:
        return

    latitude, longitude = CHENNAI_LOCATIONS[place]

    m = folium.Map(
        location=[latitude, longitude],
        zoom_start=13,
        tiles="OpenStreetMap"
    )

    folium.Marker(
        location=[latitude, longitude],
        tooltip=place,
        popup=f"<b>{place}</b>"
    ).add_to(m)

    st_folium(
        m,
        width="100%",
        height=450,
        returned_objects=[]
    )


st.title("🛡️ Chennai Safety Dashboard")

st.caption(
    "Crime activity indicator based on available reported-news records. "
    "It is not an official crime rate or a safety guarantee."
)

articles = load_articles()

if articles.empty:
    st.stop()

st.subheader("Check crime activity by time")

locations = sorted(
    location
    for location in articles["location"].unique()
    if location
)

place = st.selectbox(
    "Where are you going?",
    locations,
    index=None,
    placeholder="Choose a locality"
)

selected_period = st.radio(
    "What time are you planning to reach?",
    list(TIME_PERIODS.keys()),
    horizontal=True
)

st.caption(f"{selected_period}: {TIME_PERIODS[selected_period]}")

if st.button("Check Safety", type="primary"):
    if not place:
        st.warning("Please choose a locality first.")
        st.stop()

    results = articles[
        (articles["location"].str.casefold() == place.casefold())
        &
        (articles["time_period"].str.casefold() == selected_period.casefold())
    ].copy()

    crime_count = len(results)
    level, icon, message = get_activity_level(crime_count)

    st.divider()
    st.subheader(f"{place} — {selected_period}")

    first, second = st.columns(2)

    with first:
        st.metric("Reported incidents", crime_count)

    with second:
        st.metric("Time period", selected_period)

    if level == "green":
        st.success(f"{icon} {message}")
    elif level == "yellow":
        st.warning(f"{icon} {message}")
    else:
        st.error(f"{icon} {message}")

    st.caption(
        "This result is based on the reported crime records available "
        "for the selected locality and time period."
    )

    if not results.empty:
        st.subheader("Reported incidents")

        display_columns = [
            column
            for column in [
                "published_on",
                "crime_type",
                "source",
                "title",
                "url"
            ]
            if column in results.columns
        ]

        report_data = results[display_columns].copy()

        if "published_on" in report_data.columns:
            report_data["published_on"] = (
                report_data["published_on"].dt.strftime("%Y-%m-%d")
            )

        st.dataframe(
            report_data,
            hide_index=True,
            use_container_width=True,
            column_config={
                "url": st.column_config.LinkColumn("Source link")
            }
        )
    else:
        st.info(
            f"No reported incidents were found for {place} "
            f"during the selected time period."
        )

    st.divider()
    show_location_map(place)
