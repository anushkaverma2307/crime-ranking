from datetime import date
from pathlib import Path
import math
import sqlite3

import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

CSS_PATH = Path("style.css")

with open(CSS_PATH) as f:
    st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

st.set_page_config(page_title="Chennai Safety Dashboard", page_icon="🛡️", layout="wide")

DATA_PATH = Path("data/articles.csv")
DB_PATH = "users.db"
CRIME_TYPES = ["Pickpocketing", "Theft", "Harassment", "Assault", "Vandalism"]


def create_database():
    """Create a tiny local database for the prototype's user preferences."""
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS user_preferences (
                name TEXT PRIMARY KEY,
                pickpocketing INTEGER,
                theft INTEGER,
                harassment INTEGER,
                assault INTEGER,
                vandalism INTEGER
            )
            """
        )


def save_preferences(name, weights):
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            INSERT OR REPLACE INTO user_preferences
            (name, pickpocketing, theft, harassment, assault, vandalism)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (name, weights["Pickpocketing"], weights["Theft"], weights["Harassment"],
             weights["Assault"], weights["Vandalism"]),
        )

def load_preferences(name):
    """Return saved weights for this name, or None for a new user."""
    with sqlite3.connect(DB_PATH) as connection:
        row = connection.execute(
            """
            SELECT pickpocketing, theft, harassment, assault, vandalism
            FROM user_preferences
            WHERE name = ?
            """,
            (name,),
        ).fetchone()

    if row is None:
        return None

    return dict(zip(CRIME_TYPES, row))


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

    return articles


def recency_factor(published_on):
    """Newer reports matter more. A report loses half its influence every 180 days."""
    if pd.isna(published_on):
        return 0.5
    days_old = max((date.today() - published_on.date()).days, 0)
    return math.exp(-days_old / 180)

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

def calculate_score(place_articles, weights):
    """Return a 0–100 indicator: higher means lower reported-news risk."""
    risk = sum(
        weights.get(row.crime_type, 3) * recency_factor(row.published_on)
        for row in place_articles.itertuples()
    )
    # This is a transparent demo formula, not a real-world crime rate.
    score = max(0, round(100 - risk * 8))
    if score >= 70:
        tag, icon = "Green — lower reported-news risk", "🟢"
    elif score >= 40:
        tag, icon = "Yellow — review recent reports", "🟡"
    else:
        tag, icon = "Red — higher reported-news risk", "🔴"
    return score, tag, icon, risk


create_database()

if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "weights" not in st.session_state:
    st.session_state.weights = {crime: 3 for crime in CRIME_TYPES}

if "onboarding_step" not in st.session_state:
    st.session_state.onboarding_step = "name"

if "pending_name" not in st.session_state:
    st.session_state.pending_name = None

st.title("🛡️ Chennai Safety Dashboard")
st.caption("A personalised indicator based on reported news — not an official crime rate or a safety guarantee.")

if not st.session_state.user_name:

    # Step 1: Ask only for the name.
    if st.session_state.onboarding_step == "name":
        st.subheader("Welcome")
        st.write("Enter your name so we can look for saved safety preferences.")

        with st.form("name_form"):
            name = st.text_input("Your name", max_chars=50)
            submitted = st.form_submit_button("Continue")

        if submitted:
            if not name.strip():
                st.error("Please enter your name.")
            else:
                clean_name = name.strip()
                saved_weights = load_preferences(clean_name)

                st.session_state.pending_name = clean_name

                if saved_weights is not None:
                    st.session_state.weights = saved_weights
                    st.session_state.onboarding_step = "saved_found"
                else:
                    st.session_state.weights = {crime: 3 for crime in CRIME_TYPES}
                    st.session_state.onboarding_step = "edit_preferences"

                st.rerun()

    # Step 2A: Existing user — offer saved preferences or editing.
    elif st.session_state.onboarding_step == "saved_found":
        st.subheader(f"Welcome back, {st.session_state.pending_name}!")
        st.write("Your saved safety priorities were found:")

        saved_table = pd.DataFrame(
            {
                "Crime type": CRIME_TYPES,
                "Your rating": [
                    str(st.session_state.weights[crime]) for crime in CRIME_TYPES
                ],
            }
        )
        left, _ = st.columns([0.35, 0.90])

        with left:
            st.dataframe(saved_table, hide_index=True, use_container_width=True)

        accepted = st.checkbox(
            "I understand this app is an indicator based on news reports, not emergency advice."
        )

        first, second, _ = st.columns([0.2, 0.2, 0.8])

        with first:
            if st.button("Use saved preferences"):
                if not accepted:
                    st.error("Please confirm the limitation notice to continue.")
                else:
                    st.session_state.user_name = st.session_state.pending_name
                    st.rerun()

        with second:
            if st.button("Modify preferences"):
                # Clear old slider widget values before showing the edit screen.
                for crime in CRIME_TYPES:
                    st.session_state.pop(f"edit_{crime}", None)

                st.session_state.onboarding_step = "edit_preferences"
                st.rerun()

    # Step 2B: New user, or an existing user who chose to edit.
    elif st.session_state.onboarding_step == "edit_preferences":
        st.subheader("Set your safety preferences")
        st.write("Choose how serious each type of report feels to you: 1 = low concern, 5 = highest concern.")

        with st.form("preferences_form"):
            chosen_weights = {}

            for crime in CRIME_TYPES:
                chosen_weights[crime] = st.radio(
                crime,
                options=[1, 2, 3, 4, 5],
                index=st.session_state.weights[crime] - 1,
                horizontal=True,
                key=f"edit_{crime}",
            )

            accepted = st.checkbox(
                "I understand this app is an indicator based on news reports, not emergency advice."
            )
            submitted = st.form_submit_button("Save preferences and continue")

        if submitted:
            if not accepted:
                st.error("Please confirm the limitation notice to continue.")
            else:
                st.session_state.weights = chosen_weights
                st.session_state.user_name = st.session_state.pending_name
                save_preferences(
                    st.session_state.user_name,
                    st.session_state.weights,
                )
                st.rerun()

    st.stop()

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
    st.header(f"Hello, {st.session_state.user_name}")
    st.write("Adjust what matters to you. The score updates immediately.")
    for crime in CRIME_TYPES:
        st.session_state.weights[crime] = st.radio(
            crime,
            options=[1, 2, 3, 4, 5],
            index=st.session_state.weights[crime] - 1,
            horizontal=True,
            key=f"sidebar_{crime}"
        )
    if st.button("Save preferences"):
        save_preferences(st.session_state.user_name, st.session_state.weights)
        st.success("Saved locally for this prototype.")
    if st.button("Use another name"):
        st.session_state.user_name = None
        st.rerun()

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
        score, tag, icon, risk = calculate_score(results, st.session_state.weights)

        first, second, third = st.columns(3)
        first.metric("Personalised indicator", f"{score}/100")
        second.metric("Reports in this data", len(results))
        third.metric("Highest concern", results["crime_type"].mode().iat[0] if not results.empty else "No data")

        st.subheader(f"{icon} {tag}")
        st.write(
            f"This result is based on {len(results)} article record(s), your chosen severity weights, "
            "and a recency adjustment. More reported articles can reflect more coverage, not necessarily more crime."
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
        st.info("Choose a location to see its personalised indicator and the article records behind it.")