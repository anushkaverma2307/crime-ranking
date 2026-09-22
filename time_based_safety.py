import pandas as pd
import streamlit as st

DATA_PATH = "data/articles.csv"

TIME_PERIODS = {
    "Morning": "6 AM – 12 PM",
    "Afternoon": "12 PM – 5 PM",
    "Evening": "5 PM – 9 PM",
    "Night": "9 PM – 6 AM",
}

@st.cache_data
def load_time_based_articles():
    articles = pd.read_csv(DATA_PATH)
    required_columns = {"location", "title", "crime_type", "time_period"}
    missing_columns = required_columns - set(articles.columns)
    if missing_columns:
        return articles, missing_columns
    articles["location"] = articles["location"].fillna("").astype(str).str.strip()
    articles["time_period"] = articles["time_period"].fillna("").astype(str).str.strip().str.title()
    return articles, set()

def get_activity_level(count, all_counts):
    if count == 0:
        return "green", "🟢", "No reported incidents"
    if not all_counts:
        return "yellow", "🟡", "Reported crime activity"
    series = pd.Series(all_counts)
    low_limit = series.quantile(0.33)
    high_limit = series.quantile(0.66)
    if count <= low_limit:
        return "green", "🟢", "Lower reported crime activity"
    elif count <= high_limit:
        return "yellow", "🟡", "Moderate reported crime activity"
    return "red", "🔴", "Higher reported crime activity"

def show_time_based_safety():
    st.subheader("Check crime activity by time")
    articles, missing_columns = load_time_based_articles()
    if missing_columns:
        st.warning("The dataset needs a 'time_period' column before the time-based questionnaire can be used.")
        st.info("Add one of these values to each reviewed record: Morning, Afternoon, Evening, or Night.")
        return

    locations = sorted(location for location in articles["location"].unique() if location)
    if not locations:
        st.info("No locations are available in the dataset.")
        return

    place = st.selectbox("Where are you going?", locations, index=None, placeholder="Choose a locality")
    selected_period = st.radio("What time are you planning to reach?", list(TIME_PERIODS.keys()), horizontal=True)

    if st.button("Check Safety", type="primary"):
        if not place:
            st.warning("Please choose a locality first.")
            return

        filtered = articles[
            (articles["location"].str.casefold() == place.casefold())
            & (articles["time_period"] == selected_period)
        ]
        crime_count = len(filtered)
        all_counts = articles.groupby(["location", "time_period"]).size().tolist()
        level, icon, label = get_activity_level(crime_count, all_counts)

        st.divider()
        st.subheader(place)
        st.caption(f"{selected_period} ({TIME_PERIODS[selected_period]})")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Reported incidents", crime_count)
        with col2:
            st.metric("Time period", selected_period)

        if level == "green":
            st.success(f"{icon} {label}")
        elif level == "yellow":
            st.warning(f"{icon} {label}")
        else:
            st.error(f"{icon} {label}")

        st.caption("This result is based on the crime reports available in the dataset for the selected locality and time period. It is not a guarantee of personal safety.")

        if crime_count > 0:
            st.subheader("Reported incidents")
            display_columns = [column for column in ["title", "crime_type"] if column in filtered.columns]
            st.dataframe(filtered[display_columns].reset_index(drop=True), use_container_width=True, hide_index=True)

if __name__ == "__main__":
    st.set_page_config(page_title="Time-Based Crime Activity", page_icon="🛡️", layout="wide")
    st.title("🛡️ Time-Based Crime Activity")
    show_time_based_safety()
