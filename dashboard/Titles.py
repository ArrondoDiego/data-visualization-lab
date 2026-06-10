import pandas as pd
import streamlit as st

from data_loader import DataLoader
from visualizations import Visualizer


st.set_page_config(
    page_title="Titles Dashboard",
    layout="wide",
)

st.title("Titles Dashboard")
st.caption(
    "Mapping the structural shift in global film and television production (IMDb) "
    "against the growth of Netflix and Prime Video."
)


data_loader = DataLoader()
visualizer = Visualizer()

df = data_loader.load_data()
streaming_df = data_loader.load_streaming_memberships()

all_genres = data_loader.get_all_genres()
min_year, max_year = data_loader.get_year_range()


MEDIA_OPTIONS = {
    "movie": "Movie",
    "short": "Short",
    "tvseries": "TV Series",
}


def apply_global_filters(
    data,
    selected_media_types,
    selected_genres,
    year_range,
    min_rating,
    min_votes,
):
    """Filter data by media type, genres, year, rating, and votes."""
    filtered = data.copy()

    if selected_media_types:
        filtered = filtered[filtered["mediaType"].isin(selected_media_types)]

    if year_range:
        filtered = filtered[
            (filtered["startYear"] >= year_range[0])
            & (filtered["startYear"] <= year_range[1])
        ]

    if min_rating is not None:
        filtered = filtered[filtered["averageRating"] >= min_rating]

    if min_votes is not None:
        filtered = filtered[filtered["numVotes"] >= min_votes]

    if selected_genres:
        selected_genres_set = set(selected_genres)

        def has_selected_genre(value):
            if pd.isna(value):
                return False

            title_genres = {g.strip() for g in str(value).split(",") if g.strip()}
            return bool(title_genres.intersection(selected_genres_set))

        filtered = filtered[filtered["genres"].apply(has_selected_genre)]

    return filtered



# Sidebar

st.sidebar.header("Analysis Parameters")

selected_media_labels = st.sidebar.multiselect(
    "Media type",
    options=list(MEDIA_OPTIONS.values()),
    default=list(MEDIA_OPTIONS.values()),
)

selected_media_types = [
    media_type
    for media_type, label in MEDIA_OPTIONS.items()
    if label in selected_media_labels
]

selected_genres = st.sidebar.multiselect(
    "Genres",
    options=all_genres,
    default=[],
    help="If no genre is selected, all genres are included.",
)

global_year_range = st.sidebar.slider(
    "Historical Window",
    min_value=int(min_year),
    max_value=int(max_year),
    value=(int(min_year), int(max_year)),
    step=1,
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

min_titles_per_year = st.sidebar.number_input(
    "Minimum titles to show yearly trends",
    min_value=1,
    value=20,
    step=1,
)

st.sidebar.caption(
    "These filters affect the whole page. "
    "The year slider only affects the top section."
)


filtered = apply_global_filters(
    data=df,
    selected_media_types=selected_media_types,
    selected_genres=selected_genres,
    year_range=global_year_range,
    min_rating=min_rating,
    min_votes=min_votes,
)


# Filter state

st.divider()

metric_1, metric_2, metric_3, metric_4 = st.columns(4)

with metric_1:
    st.metric("Total Catalog Size", f"{len(df):,}")

with metric_2:
    st.metric("Filtered titles", f"{len(filtered):,}")

with metric_3:
    if not filtered.empty:
        st.metric("Filtered average rating", f"{filtered['averageRating'].mean():.2f}")
    else:
        st.metric("Filtered average rating", "—")

with metric_4:
    if not filtered.empty:
        st.metric("Min / max year", f"{filtered['startYear'].min()}–{filtered['startYear'].max()}")
    else:
        st.metric("Min / max year", "—")


# Top section, single year

st.divider()
st.header("1. Yearly snapshot")

if filtered.empty:
    st.warning("No data available for the selected filters.")
    st.stop()

selected_year = st.slider(
    "Reference year",
    min_value=int(global_year_range[0]),
    max_value=int(global_year_range[1]),
    value=int(global_year_range[1]),
    step=1,
)

df_year = filtered[filtered["startYear"] == selected_year].copy()

st.subheader(f"Selected year: {selected_year}")

year_metric_1, year_metric_2, year_metric_3, year_metric_4 = st.columns(4)

with year_metric_1:
    st.metric("Titles in selected year", f"{len(df_year):,}")

with year_metric_2:
    if not df_year.empty:
        st.metric("Average rating", f"{df_year['averageRating'].mean():.2f}")
    else:
        st.metric("Average rating", "—")

with year_metric_3:
    if not df_year.empty:
        st.metric("Median votes", f"{df_year['numVotes'].median():,.0f}")
    else:
        st.metric("Median votes", "—")

with year_metric_4:
    if not df_year.empty and df_year["runtimeMinutes"].notna().any():
        st.metric("Median runtime", f"{df_year['runtimeMinutes'].median():.0f} min")
    else:
        st.metric("Median runtime", "—")


top_col_1, top_col_2, top_col_3 = st.columns(3)

with top_col_1:
    st.plotly_chart(
        visualizer.genre_donut(df_year),
        use_container_width=True,
    )

with top_col_2:
    st.plotly_chart(
        visualizer.media_type_distribution(df_year),
        use_container_width=True,
    )

with top_col_3:
    st.plotly_chart(
        visualizer.rating_distribution(df_year),
        use_container_width=True,
    )

st.plotly_chart(
    visualizer.rating_vs_votes(df_year),
    use_container_width=True,
)

with st.expander(f"Top titles in {selected_year}", expanded=False):
    if df_year.empty:
        st.info("No titles available for this year.")
    else:
        top_titles = (
            df_year.sort_values(
                by=["numVotes", "averageRating"],
                ascending=[False, False],
            )
            .head(30)
            [
                [
                    "primaryTitle",
                    "mediaType",
                    "startYear",
                    "genres",
                    "averageRating",
                    "numVotes",
                    "runtimeMinutes",
                ]
            ]
        )

        top_titles = top_titles.rename(
            columns={
                "primaryTitle": "Title",
                "mediaType": "Type",
                "startYear": "Year",
                "genres": "Genres",
                "averageRating": "Rating IMDb",
                "numVotes": "IMDb Votes",
                "runtimeMinutes": "Runtime (min)",
            }
        )

        st.dataframe(
            top_titles,
            use_container_width=True,
            hide_index=True,
        )


# Bottom section, historical trends

st.divider()
st.header("2. Historical trends")
st.caption(
    "This section does not depend on the year slider above. "
    "It only depends on the global sidebar filters. "
    "The historical charts also include transparent streaming subscriber bars so the platform growth stays visible across the page."
)

st.plotly_chart(
    visualizer.streaming_vs_titles(filtered, streaming_context_df),
    use_container_width=True,
)

hist_col_1, hist_col_2 = st.columns(2)

with hist_col_1:
    st.plotly_chart(
        visualizer.titles_over_time_by_type(filtered, streaming_df=streaming_context_df),
        use_container_width=True,
    )

with hist_col_2:
    st.plotly_chart(
        visualizer.media_type_share_over_time(filtered, streaming_df=streaming_context_df),
        use_container_width=True,
    )

hist_col_3, hist_col_4 = st.columns(2)

with hist_col_3:
    st.plotly_chart(
        visualizer.weighted_rating_over_time(
            filtered,
            min_titles_per_year=int(min_titles_per_year),
            streaming_df=streaming_context_df,
        ),
        use_container_width=True,
    )

with hist_col_4:
    st.plotly_chart(
        visualizer.median_votes_over_time(
            filtered,
            min_titles_per_year=int(min_titles_per_year),
            streaming_df=streaming_context_df,
        ),
        use_container_width=True,
    )

st.plotly_chart(
    visualizer.genre_trends(
        filtered,
        selected_genres=selected_genres,
        streaming_df=streaming_context_df,
    ),
    use_container_width=True,
)

st.plotly_chart(
    visualizer.average_runtime_over_time_by_type(
        filtered,
        min_titles_per_year=int(min_titles_per_year),
        streaming_df=streaming_context_df,
    ),
    use_container_width=True,
)

st.divider()

st.caption(
    f"Filtered dataset: {len(filtered):,} titles out of {len(df):,} total. "
    f"Included types: movie, short, tvseries."
)
