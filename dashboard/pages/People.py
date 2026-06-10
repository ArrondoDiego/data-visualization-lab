import pandas as pd
import streamlit as st

from data_loader import DataLoader
from visualizations import Visualizer


st.set_page_config(
    page_title="People Dashboard",
    layout="wide",
)

st.title("People Dashboard")
st.caption(
    "Analysis of actors, actresses, directors, writers, producers, and other people "
    "linked to filtered IMDb titles."
)


data_loader = DataLoader()
visualizer = Visualizer()

_ = data_loader.load_data()

streaming_df = data_loader.load_streaming_memberships()
all_genres = data_loader.get_all_genres()
min_year, max_year = data_loader.get_year_range()
available_roles = data_loader.get_people_roles()


MEDIA_OPTIONS = {
    "movie": "Movie",
    "short": "Short",
    "tvseries": "TV Series",
}


# ─────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────

st.sidebar.header("Global filters")

selected_media_labels = st.sidebar.multiselect(
    "Media type",
    options=list(MEDIA_OPTIONS.values()),
    default=list(MEDIA_OPTIONS.values()),
)

selected_media_types = tuple(
    media_type
    for media_type, label in MEDIA_OPTIONS.items()
    if label in selected_media_labels
)

selected_roles = tuple(
    st.sidebar.multiselect(
        "Roles",
        options=available_roles,
        default=available_roles,
    )
)

selected_genres = tuple(
    st.sidebar.multiselect(
        "Genres",
        options=all_genres,
        default=[],
        help="If you do not select any genre, all genres are included.",
    )
)

global_year_range = tuple(
    st.sidebar.slider(
        "Historical Window",
        min_value=int(min_year),
        max_value=int(max_year),
        value=(int(min_year), int(max_year)),
        step=1,
    )
)

min_rating = st.sidebar.slider(
    "Minimum IMDb rating",
    min_value=0.0,
    max_value=10.0,
    value=0.0,
    step=0.1,
)

min_votes = st.sidebar.number_input(
    "Minimum IMDb vote count",
    min_value=0,
    value=0,
    step=100,
)

show_streaming_context = st.sidebar.toggle(
    "Show streaming platform context",
    value=True,
    help="Display transparent streaming subscriber bars and streaming-aware legend labels in historical charts.",
)

streaming_context_df = streaming_df if show_streaming_context else None

top_people_limit = st.sidebar.slider(
    "People shown in top charts",
    min_value=5,
    max_value=50,
    value=20,
    step=5,
)

st.sidebar.caption(
    "These filters affect the whole page. "
    "The year slider only affects the top section."
)


if not selected_media_types or not selected_roles:
    st.warning("Select at least one media type and at least one role.")
    st.stop()


filter_args = {
    "media_types": selected_media_types,
    "genres": selected_genres,
    "year_range": global_year_range,
    "min_rating": float(min_rating),
    "min_votes": int(min_votes),
    "roles": selected_roles,
}


# ─────────────────────────────────────────────
# Global KPIs
# ─────────────────────────────────────────────

global_kpis = data_loader.query_people_kpis(**filter_args)

st.divider()

kpi_1, kpi_2, kpi_3, kpi_4 = st.columns(4)

with kpi_1:
    st.metric("Filtered people", f"{global_kpis['people']:,}")

with kpi_2:
    st.metric("Filtered credits", f"{global_kpis['credits']:,}")

with kpi_3:
    st.metric("Titles involved", f"{global_kpis['titles']:,}")

with kpi_4:
    if global_kpis["avgRating"] is not None:
        st.metric("Average title rating", f"{global_kpis['avgRating']:.2f}")
    else:
        st.metric("Average title rating", "—")


# ─────────────────────────────────────────────
# Top section, single year
# ─────────────────────────────────────────────

st.divider()
st.header("1. Yearly people snapshot")

selected_year = st.slider(
    "Reference year",
    min_value=int(global_year_range[0]),
    max_value=int(global_year_range[1]),
    value=int(global_year_range[1]),
    step=1,
)

year_kpis = data_loader.query_people_kpis(
    **filter_args,
    year=int(selected_year),
)

st.subheader(f"Selected year: {selected_year}")

year_col_1, year_col_2, year_col_3, year_col_4 = st.columns(4)

with year_col_1:
    st.metric("People in selected year", f"{year_kpis['people']:,}")

with year_col_2:
    st.metric("Credits in selected year", f"{year_kpis['credits']:,}")

with year_col_3:
    st.metric("Titles in selected year", f"{year_kpis['titles']:,}")

with year_col_4:
    if year_kpis["avgRating"] is not None:
        st.metric("Average rating", f"{year_kpis['avgRating']:.2f}")
    else:
        st.metric("Average rating", "—")


snapshot_people = data_loader.query_top_people_snapshot(
    year=int(selected_year),
    limit=int(top_people_limit),
    **filter_args,
)

snapshot_roles = data_loader.query_people_role_distribution(
    year=int(selected_year),
    **filter_args,
)

upper_col_1, upper_col_2 = st.columns(2)

with upper_col_1:
    st.plotly_chart(
        visualizer.people_role_distribution(snapshot_roles),
        use_container_width=True,
    )

with upper_col_2:
    st.plotly_chart(
        visualizer.people_bubble_snapshot(snapshot_people),
        use_container_width=True,
    )

st.plotly_chart(
    visualizer.top_people_bar(
        snapshot_people,
        metric="credits",
            title=f"Top people by credits in {selected_year}",
    ),
    use_container_width=True,
)

with st.expander(f"Top people table for {selected_year}", expanded=False):
    if snapshot_people.empty:
        st.info("No data available for this year.")
    else:
        table = snapshot_people.copy()
        table["avgRating"] = table["avgRating"].round(2)

        table = table.rename(
            columns={
                "primaryName": "Name",
                "roles": "Roles",
                "credits": "Credits",
                "titles": "Titles",
                "avgRating": "Average rating",
                "totalVotes": "Total votes",
                "maxVotes": "Max votes on a single title",
            }
        )

        st.dataframe(
            table[
                [
                    "Name",
                    "Roles",
                    "Credits",
                    "Titles",
                    "Average rating",
                    "Total votes",
                    "Max votes on a single title",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


# Bottom section, historical trends

st.divider()
st.header("2. Historical trends for people")
st.caption(
    "This section does not depend on the year slider. "
    "It only depends on the global sidebar filters. "
    "The historical charts reuse the same transparent streaming subscriber bars to keep the platform growth visible across the page."
)

yearly_people = data_loader.query_people_yearly_counts(**filter_args)
role_trends = data_loader.query_people_yearly_role_trends(**filter_args)
new_people = data_loader.query_new_people_over_time(**filter_args)
career_heatmap = data_loader.query_top_people_career_heatmap(
    limit=15,
    **filter_args,
)
top_people_overall = data_loader.query_top_people_overall(
    limit=int(top_people_limit),
    **filter_args,
)

st.plotly_chart(
    visualizer.people_vs_streaming(yearly_people, streaming_context_df),
    use_container_width=True,
)

trend_col_1, trend_col_2 = st.columns(2)

with trend_col_1:
    st.plotly_chart(
        visualizer.people_role_trends(
            role_trends,
            metric="people",
            streaming_df=streaming_context_df,
        ),
        use_container_width=True,
    )

with trend_col_2:
    st.plotly_chart(
        visualizer.people_role_trends(
            role_trends,
            metric="credits",
            streaming_df=streaming_context_df,
        ),
        use_container_width=True,
    )

trend_col_3, trend_col_4 = st.columns(2)

with trend_col_3:
    st.plotly_chart(
        visualizer.new_people_over_time(new_people, streaming_df=streaming_context_df),
        use_container_width=True,
    )

with trend_col_4:
    st.plotly_chart(
        visualizer.top_people_bar(
            top_people_overall,
            metric="credits",
            title="Top people across the full filtered period",
        ),
        use_container_width=True,
    )

st.plotly_chart(
    visualizer.top_people_heatmap(career_heatmap, streaming_df=streaming_context_df),
    use_container_width=True,
)


st.divider()
