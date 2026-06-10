import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots


class Visualizer:
    """Generate Plotly charts for the dashboard."""

    STREAMING_PLATFORM_COLORS = {
        "Netflix": "rgba(126, 87, 194, 0.26)",      # viola trasparente
        "Prime Video": "rgba(245, 158, 11, 0.24)", # ambra trasparente
    }

    STREAMING_PLATFORM_BORDER_COLORS = {
        "Netflix": "rgba(126, 87, 194, 0.55)",
        "Prime Video": "rgba(245, 158, 11, 0.50)",
    }

    MEDIA_LABELS = {
        "movie": "Movie",
        "short": "Short",
        "tvseries": "TV Series",
    }

    YOUTUBE_FOUNDING_YEAR = 2005
    YOUTUBE_FOUNDING_LABEL = "2005, YouTube founded"
    YOUTUBE_FOUNDING_COLOR = "rgba(80, 80, 80, 0.32)"

    def _empty_figure(self, title, message="No data available"):
        fig = go.Figure()

        fig.update_layout(
            title=title,
            height=360,
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": message,
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16},
                }
            ],
        )

        return fig

    def _add_media_label(self, df):
        df = df.copy()
        df["mediaLabel"] = df["mediaType"].map(self.MEDIA_LABELS).fillna(df["mediaType"])
        return df

    def _streaming_legend_title(self, streaming_df, enabled_title, disabled_title=None):
        if streaming_df is None or streaming_df.empty:
            return disabled_title if disabled_title is not None else enabled_title

        return enabled_title

    def _streaming_bar_trace(self, platform, platform_df, showlegend=True, yaxis=None):
        trace = go.Bar(
            x=platform_df["year"],
            y=platform_df["memberships_mln"],
            name=f"{platform} subscribers (M)",
            marker={
                "color": self.STREAMING_PLATFORM_COLORS.get(
                    platform,
                    "rgba(120, 120, 120, 0.22)",
                ),
                "line": {
                    "color": self.STREAMING_PLATFORM_BORDER_COLORS.get(
                        platform,
                        "rgba(120, 120, 120, 0.45)",
                    ),
                    "width": 0.5,
                },
            },
            width=0.7,
            showlegend=showlegend,
            legendgroup="streaming",
            hovertemplate=(
                f"{platform}<br>"
                "Year=%{x}<br>"
                "Subscribers=%{y:.0f}M"
                "<extra></extra>"
            ),
        )

        if yaxis is not None:
            trace.update(yaxis=yaxis)

        return trace

    def _add_youtube_founding_marker(self, fig, showlegend=True):
        """Add a light vertical marker for YouTube's founding year."""

        # Evita duplicati nel caso il metodo venga chiamato piu' volte sullo stesso grafico
        if any(
            getattr(trace, "name", None) == self.YOUTUBE_FOUNDING_LABEL
            for trace in fig.data
        ):
            return fig

        fig.add_shape(
            type="line",
            x0=self.YOUTUBE_FOUNDING_YEAR,
            x1=self.YOUTUBE_FOUNDING_YEAR,
            y0=0,
            y1=1,
            xref="x",
            yref="paper",
            line={
                "color": self.YOUTUBE_FOUNDING_COLOR,
                "width": 1,
                "dash": "dash",
            },
            layer="below",
        )

        if showlegend:
            fig.add_trace(
                go.Scatter(
                    x=[None],
                    y=[None],
                    mode="lines",
                    name=self.YOUTUBE_FOUNDING_LABEL,
                    line={
                        "color": self.YOUTUBE_FOUNDING_COLOR,
                        "width": 1,
                        "dash": "dash",
                    },
                    showlegend=True,
                    legendgroup="events",
                    hoverinfo="skip",
                )
            )

        return fig

    def _legend_below(self, fig, bottom=120):
        fig.update_layout(
            legend={
                "orientation": "h",
                "x": 0.5,
                "xanchor": "center",
                "y": -0.25,
                "yanchor": "top",
                "bgcolor": "rgba(255,255,255,0.75)",
            },
            margin={
                "l": 70,
                "r": 70,
                "t": 70,
                "b": bottom,
            },
        )

        return fig

    def _add_streaming_context(
        self,
        fig,
        streaming_df,
        showlegend=False,
        show_youtube_marker=True,
    ):
        """Add transparent streaming subscriber bars to year-based charts."""
        if streaming_df is None or streaming_df.empty:
            return fig

        context_df = streaming_df.dropna(subset=["year", "memberships_mln"]).copy()

        if context_df.empty:
            return fig

        context_df["year"] = pd.to_numeric(context_df["year"], errors="coerce")
        context_df = context_df.dropna(subset=["year"])

        if context_df.empty:
            return fig

        context_df["year"] = context_df["year"].astype(int)

        fig.update_layout(
            yaxis2={
                "title": "Subscribers (millions)",
                "overlaying": "y",
                "side": "right",
                "showgrid": False,
                "rangemode": "tozero",
            },
            barmode="overlay",
        )

        for platform in context_df["platform"].dropna().unique():
            platform_df = context_df[context_df["platform"] == platform].sort_values("year")

            fig.add_trace(
                self._streaming_bar_trace(
                    platform,
                    platform_df,
                    showlegend=showlegend,
                    yaxis="y2",
                )
            )

        if show_youtube_marker:
            self._add_youtube_founding_marker(fig, showlegend=True)

        return fig

    def genre_donut(self, df, limit=8):
        """Genre distribution for the selected subset."""
        if df.empty or "genres" not in df.columns:
            return self._empty_figure("Genre distribution")

        genres = (
            df["genres"]
            .dropna()
            .astype(str)
            .str.split(",")
            .explode()
            .str.strip()
        )

        genres = genres[genres != ""]

        if genres.empty:
            return self._empty_figure("Genre distribution")

        genre_counts = genres.value_counts()

        main_genres = genre_counts.head(limit).copy()

        if len(genre_counts) > limit:
            main_genres.loc["Other"] = genre_counts.iloc[limit:].sum()

        fig = px.pie(
            names=main_genres.index,
            values=main_genres.values,
            title=f"Top {limit} genre distribution",
            hole=0.42,
        )

        fig.update_layout(height=360)
        fig.update_traces(textposition="inside", textinfo="percent+label")

        return fig

    def media_type_distribution(self, df):
        """Distribution by media type."""
        if df.empty:
            return self._empty_figure("Distribution by media type")

        df = self._add_media_label(df)

        counts = (
            df.groupby("mediaLabel")
            .size()
            .reset_index(name="titles")
            .sort_values("titles", ascending=False)
        )

        fig = px.bar(
            counts,
            x="mediaLabel",
            y="titles",
            text="titles",
            title="Titles by media type",
        )

        fig.update_layout(
            height=360,
            xaxis_title="Type",
            yaxis_title="Number of titles",
        )

        fig.update_traces(textposition="outside")

        return fig

    def rating_distribution(self, df):
        """IMDb rating distribution."""
        if df.empty:
            return self._empty_figure("IMDb rating distribution")

        fig = px.histogram(
            df,
            x="averageRating",
            nbins=25,
            title="IMDb rating distribution",
        )

        fig.update_layout(
            height=360,
            xaxis_title="Rating IMDb",
            yaxis_title="Number of titles",
        )

        return fig

    def rating_vs_votes(self, df):
        """Scatter plot: rating vs vote count."""
        if df.empty:
            return self._empty_figure("Rating vs votes")

        df = self._add_media_label(df)

        fig = px.scatter(
            df,
            x="numVotes",
            y="averageRating",
            color="mediaLabel",
            hover_name="primaryTitle",
            hover_data={
                "startYear": True,
                "genres": True,
                "runtimeMinutes": True,
                "numVotes": ":,",
                "averageRating": ":.1f",
                "mediaLabel": False,
            },
            title="IMDb rating vs vote count",
            opacity=0.55,
        )

        fig.update_xaxes(type="log")
        fig.update_layout(
            height=430,
            xaxis_title="Vote count (log scale)",
            yaxis_title="Rating IMDb",
            legend_title="Type",
        )

        return fig

    def titles_over_time_by_type(self, df, streaming_df=None):
        """Number of titles over time by type."""
        if df.empty:
            return self._empty_figure("Titles over time by type")

        df = self._add_media_label(df)

        yearly = (
            df.groupby(["startYear", "mediaLabel"])
            .size()
            .reset_index(name="titles")
            .sort_values("startYear")
        )

        fig = px.line(
            yearly,
            x="startYear",
            y="titles",
            color="mediaLabel",
            markers=True,
            title="IMDb production over time by type",
        )

        fig.update_layout(
            height=520,
            xaxis_title="Year",
            yaxis_title="Number of titles",
            legend_title="Type",
        )

        self._add_streaming_context(fig, streaming_df, showlegend=False)
        self._legend_below(fig, bottom=120)

        return fig

    def streaming_vs_titles(self, df, streaming_df):
        """
        Compare IMDb production with streaming subscriber growth.

        Left axis:
        - number of filtered IMDb titles

        Right axis:
        - Netflix / Prime Video subscribers in millions
        """
        if df.empty:
            return self._empty_figure("IMDb production vs streaming growth")

        yearly_titles = (
            df.groupby("startYear")
            .size()
            .reset_index(name="titles")
            .sort_values("startYear")
        )

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(
                x=yearly_titles["startYear"],
                y=yearly_titles["titles"],
                name="Filtered IMDb titles",
                opacity=0.55,
            ),
            secondary_y=False,
        )

        if streaming_df is not None and not streaming_df.empty:
            for platform in streaming_df["platform"].dropna().unique():
                platform_df = streaming_df[streaming_df["platform"] == platform]

                fig.add_trace(
                    self._streaming_bar_trace(
                        platform,
                        platform_df,
                        showlegend=True,
                    ),
                    secondary_y=True,
                )

            self._add_youtube_founding_marker(fig, showlegend=True)

        fig.update_layout(
            title="IMDb production vs streaming subscriber growth",
            height=500,
            legend_title=self._streaming_legend_title(
                streaming_df,
                "Titles / streaming platforms",
                "Titles",
            ),
            barmode="overlay",
        )

        fig.update_xaxes(title_text="Year")
        fig.update_yaxes(title_text="IMDb title count", secondary_y=False)
        fig.update_yaxes(title_text="Subscribers (millions)", secondary_y=True)

        return fig

    def weighted_rating_over_time(self, df, min_titles_per_year=20, streaming_df=None):
        """Rating weighted by vote count per year."""
        if df.empty:
            return self._empty_figure("Weighted average rating over time")

        tmp = df.dropna(subset=["averageRating", "numVotes"]).copy()
        tmp = tmp[tmp["numVotes"] > 0]

        if tmp.empty:
            return self._empty_figure("Weighted average rating over time")

        tmp["weighted_rating_sum"] = tmp["averageRating"] * tmp["numVotes"]

        yearly = (
            tmp.groupby("startYear")
            .agg(
                weighted_rating_sum=("weighted_rating_sum", "sum"),
                votes_sum=("numVotes", "sum"),
                titles=("tconst", "count"),
            )
            .reset_index()
        )

        yearly = yearly[yearly["titles"] >= min_titles_per_year]

        if yearly.empty:
            return self._empty_figure(
                "Weighted average rating over time",
                f"No year with at least {min_titles_per_year} titles",
            )

        yearly["weightedRating"] = yearly["weighted_rating_sum"] / yearly["votes_sum"]

        fig = px.line(
            yearly,
            x="startYear",
            y="weightedRating",
            markers=True,
            title="IMDb vote-weighted average rating",
            hover_data={
                "titles": True,
                "votes_sum": ":,",
                "weighted_rating_sum": False,
            },
        )

        fig.update_layout(
            height=430,
            xaxis_title="Year",
            yaxis_title="Weighted average rating",
        )

        fig.update_yaxes(range=[0, 10])

        self._add_streaming_context(fig, streaming_df)

        return fig

    def median_votes_over_time(self, df, min_titles_per_year=20, streaming_df=None):
        """Median IMDb votes per year."""
        if df.empty:
            return self._empty_figure("Median IMDb votes over time")

        tmp = df.dropna(subset=["numVotes"]).copy()

        yearly = (
            tmp.groupby("startYear")
            .agg(
                medianVotes=("numVotes", "median"),
                titles=("tconst", "count"),
            )
            .reset_index()
        )

        yearly = yearly[yearly["titles"] >= min_titles_per_year]

        if yearly.empty:
            return self._empty_figure(
                "Median IMDb votes over time",
                f"No year with at least {min_titles_per_year} titles",
            )

        fig = px.line(
            yearly,
            x="startYear",
            y="medianVotes",
            markers=True,
            title="Median IMDb votes per title",
            hover_data={
                "titles": True,
                "medianVotes": ":,.0f",
            },
        )

        fig.update_yaxes(type="log")
        fig.update_layout(
            height=430,
            xaxis_title="Year",
            yaxis_title="Median votes (log scale)",
            legend_title=self._streaming_legend_title(
                streaming_df,
                "Streaming platforms",
                None,
            ),
        )

        self._add_streaming_context(fig, streaming_df)

        return fig

    def genre_trends(self, df, limit=8, selected_genres=None, streaming_df=None):
        """Genre trends, top N or selected genres."""
        if df.empty or "genres" not in df.columns:
            return self._empty_figure("Genre trends over time")

        df_genres = df[df["genres"].notna()].copy()

        if df_genres.empty:
            return self._empty_figure("Genre trends over time")

        df_genres["genre"] = df_genres["genres"].astype(str).str.split(",")
        df_genres = df_genres.explode("genre")
        df_genres["genre"] = df_genres["genre"].str.strip()
        df_genres = df_genres[df_genres["genre"] != ""]

        selected_genres = [
            genre.strip()
            for genre in (selected_genres or [])
            if str(genre).strip()
        ]

        if selected_genres:
            genres_to_show = selected_genres
            df_genres = df_genres[df_genres["genre"].isin(genres_to_show)]

            title = (
                "Selected genre trend over time"
                if len(genres_to_show) == 1
                else "Selected genre trends over time"
            )
        else:
            genres_to_show = df_genres["genre"].value_counts().head(limit).index.tolist()
            df_genres = df_genres[df_genres["genre"].isin(genres_to_show)]
            title = f"Top {limit} genre trends over time"

        genre_by_year = (
            df_genres
            .groupby(["startYear", "genre"])
            .size()
            .reset_index(name="titles")
            .sort_values("startYear")
        )

        if genre_by_year.empty:
            return self._empty_figure(
                "Genre trends over time",
                "No data available for the selected genres",
            )

        fig = px.line(
            genre_by_year,
            x="startYear",
            y="titles",
            color="genre",
            markers=True,
            title=title,
            category_orders={"genre": genres_to_show},
        )

        fig.update_layout(
            height=540,
            xaxis_title="Year",
            yaxis_title="Number of titles",
            legend_title="Genre",
        )

        self._add_streaming_context(fig, streaming_df, showlegend=False)
        self._legend_below(fig, bottom=150)

        return fig

    def media_type_share_over_time(self, df, streaming_df=None):
        """Percentage share of media types over time."""
        if df.empty:
            return self._empty_figure("Media type share over time")

        df = self._add_media_label(df)

        yearly = (
            df.groupby(["startYear", "mediaLabel"])
            .size()
            .reset_index(name="titles")
        )

        yearly["sharePct"] = (
            yearly["titles"]
            / yearly.groupby("startYear")["titles"].transform("sum")
            * 100
        )

        fig = px.area(
            yearly,
            x="startYear",
            y="sharePct",
            color="mediaLabel",
            title="Percentage composition by media type over time",
        )

        fig.update_layout(
            height=520,
            xaxis_title="Year",
            yaxis_title="Percentage share",
            legend_title="Type",
        )

        fig.update_yaxes(range=[0, 100])

        self._add_streaming_context(fig, streaming_df, showlegend=False)
        self._legend_below(fig, bottom=120)

        return fig

    def people_role_distribution(self, df):
        if df.empty:
            return self._empty_figure("Role distribution")

        melted = df.melt(
            id_vars="category",
            value_vars=["credits", "people", "titles"],
            var_name="metric",
            value_name="value",
        )

        label_map = {
            "credits": "Credits",
            "people": "People",
            "titles": "Titles",
        }

        melted["metric"] = melted["metric"].map(label_map)

        fig = px.bar(
            melted,
            x="category",
            y="value",
            color="metric",
            barmode="group",
            title="Role distribution",
        )

        fig.update_layout(
            height=380,
            xaxis_title="Role",
            yaxis_title="Count",
            legend_title="Metric",
        )

        return fig

    def top_people_bar(self, df, metric="credits", title="Top people"):
        if df.empty:
            return self._empty_figure(title)

        df = df.copy()
        df = df.sort_values(metric, ascending=True)

        fig = px.bar(
            df,
            x=metric,
            y="primaryName",
            orientation="h",
            hover_data={
                "roles": True,
                "titles": True,
                "avgRating": ":.2f",
                "totalVotes": ":,",
            },
            title=title,
        )

        fig.update_layout(
            height=max(420, len(df) * 24),
            xaxis_title=metric,
            yaxis_title="Person",
        )

        return fig

    def average_runtime_over_time_by_type(self, df, min_titles_per_year=20, streaming_df=None):
        """Median runtime over time by media type."""
        if df.empty or "runtimeMinutes" not in df.columns:
            return self._empty_figure("Median runtime over time by type")

        tmp = df.dropna(subset=["runtimeMinutes"]).copy()
        tmp = tmp[(tmp["runtimeMinutes"] > 0) & (tmp["runtimeMinutes"] <= 1000)]

        if tmp.empty:
            return self._empty_figure("Median runtime over time by type")

        tmp = self._add_media_label(tmp)

        yearly = (
            tmp.groupby(["startYear", "mediaLabel"])
            .agg(
                averageRuntime=("runtimeMinutes", "mean"),
                medianRuntime=("runtimeMinutes", "median"),
                titles=("tconst", "count"),
            )
            .reset_index()
            .sort_values("startYear")
        )

        yearly = yearly[yearly["titles"] >= min_titles_per_year]

        if yearly.empty:
            return self._empty_figure(
                "Median runtime over time by type",
                f"No year/type with at least {min_titles_per_year} titles",
            )

        fig = px.bar(
            yearly,
            x="startYear",
            y="medianRuntime",
            color="mediaLabel",
            barmode="group",
            title="Median runtime over time by type",
            hover_data={
                "titles": True,
                "medianRuntime": ":.1f",
                "mediaLabel": False,
            },
        )

        fig.update_layout(
            height=500,
            xaxis_title="Year",
            yaxis_title="Median runtime (minutes)",
            legend_title=self._streaming_legend_title(
                streaming_df,
                "Type / streaming platforms",
                "Type",
            ),
        )

        self._add_streaming_context(fig, streaming_df)

        return fig


    def people_bubble_snapshot(self, df):
        if df.empty:
            return self._empty_figure("People: credits, ratings, and popularity")

        df = df.copy()
        df["mainRole"] = df["roles"].fillna("").str.split(",").str[0]
        df["bubbleVotes"] = df["totalVotes"].fillna(0).clip(lower=1)

        fig = px.scatter(
            df,
            x="credits",
            y="avgRating",
            size="bubbleVotes",
            color="mainRole",
            hover_name="primaryName",
            hover_data={
                "roles": True,
                "titles": True,
                "totalVotes": ":,",
                "avgRating": ":.2f",
                "bubbleVotes": False,
                "mainRole": False,
            },
            title="People in selected year: credits, average rating, and total votes",
            size_max=55,
        )

        fig.update_layout(
            height=430,
            xaxis_title="Credits in selected year",
            yaxis_title="Average title rating",
            legend_title="Main role",
        )

        fig.update_yaxes(range=[0, 10])

        return fig


    def people_vs_streaming(self, yearly_people, streaming_df):
        if yearly_people.empty:
            return self._empty_figure("Credited people vs streaming growth")

        fig = make_subplots(specs=[[{"secondary_y": True}]])

        fig.add_trace(
            go.Bar(
                x=yearly_people["startYear"],
                y=yearly_people["people"],
                name="Credited people",
                opacity=0.55,
            ),
            secondary_y=False,
        )

        fig.add_trace(
            go.Scatter(
                x=yearly_people["startYear"],
                y=yearly_people["credits"],
                name="IMDb credits",
                mode="lines+markers",
            ),
            secondary_y=False,
        )
        if streaming_df is not None and not streaming_df.empty:
            for platform in streaming_df["platform"].dropna().unique():
                platform_df = streaming_df[streaming_df["platform"] == platform]

                fig.add_trace(
                    self._streaming_bar_trace(
                        platform,
                        platform_df,
                        showlegend=True,
                    ),
                    secondary_y=True,
                )

            self._add_youtube_founding_marker(fig, showlegend=True)

        fig.update_layout(
            title="Credited people and streaming subscription growth",
            height=500,
            legend_title=self._streaming_legend_title(
                streaming_df,
                "People / streaming platforms",
                "People",
            ),
            barmode="overlay",
        )

        fig.update_xaxes(title_text="Year")
        fig.update_yaxes(title_text="People / IMDb credits", secondary_y=False)
        fig.update_yaxes(title_text="Subscriptions (millions)", secondary_y=True)

        return fig


    def people_role_trends(self, df, metric="people", streaming_df=None):
        if df.empty:
            return self._empty_figure("Roles over time")

        metric_label = {
            "people": "People",
            "credits": "Credits",
            "titles": "Titles",
        }.get(metric, metric)

        fig = px.line(
            df,
            x="startYear",
            y=metric,
            color="category",
            markers=True,
            title=f"{metric_label} by role over time",
        )

        fig.update_layout(
            height=520,
            xaxis_title="Year",
            yaxis_title=metric_label,
            legend_title="Role / streaming platforms",
        )

        self._add_streaming_context(fig, streaming_df, showlegend=False)
        self._legend_below(fig, bottom=140)

        return fig

    def new_people_over_time(self, df, streaming_df=None):
        if df.empty:
            return self._empty_figure("New people over time")

        fig = px.area(
            df,
            x="startYear",
            y="newPeople",
            title="First appearances in the filtered subset",
        )

        fig.update_layout(
            height=420,
            xaxis_title="Year",
            yaxis_title="New people",
        )

        self._add_streaming_context(fig, streaming_df)

        return fig


    def top_people_heatmap(self, df, streaming_df=None):
        if df.empty:
            return self._empty_figure("Careers of the most featured people")

        pivot = df.pivot_table(
            index="primaryName",
            columns="startYear",
            values="credits",
            aggfunc="sum",
            fill_value=0,
        )

        order = pivot.sum(axis=1).sort_values(ascending=False).index
        pivot = pivot.loc[order]

        fig = px.imshow(
            pivot,
            aspect="auto",
            title="Career heatmap, credits by year",
            labels={
                "x": "Year",
                "y": "Person",
                "color": "Credits",
            },
        )

        fig.update_layout(height=max(450, len(pivot) * 28))

        return fig
