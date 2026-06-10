from pathlib import Path
from datetime import date

import duckdb
import pandas as pd
import streamlit as st


class DataLoader:
    """
    Handles loading IMDb and streaming datasets.

    Datasets used:
    - title.basics.tsv.gz
    - title.ratings.tsv.gz
    - netflix.csv
    - primevideo.csv

    The files title.principals.tsv.gz and name.basics.tsv.gz are no longer used
    in the new dashboard because the analysis is focused on production,
    ratings, votes, and streaming platform growth.
    """

    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR.parent / "data"

    DB_PATH = DATA_DIR / "movies.duckdb"
    TABLE_NAME = "movies"
    CURRENT_YEAR = date.today().year

    ALLOWED_IMDB_TYPES = ["movie", "short", "tvSeries"]

    PEOPLE_TABLE_NAME = "people_credits"
    PEOPLE_ROLE_OPTIONS = [
        "actor",
        "actress",
        "self",
        "director",
        "writer",
        "producer",
        "composer",
        "cinematographer",
        "editor",
        "production_designer",
    ]

    @st.cache_resource
    def get_connection(_self):
        """Keep a persistent cached DuckDB connection."""
        return duckdb.connect(str(_self.DB_PATH))

    def _table_exists(self, con) -> bool:
        result = con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [self.TABLE_NAME],
        ).fetchone()[0]

        return result > 0

    def _table_has_expected_schema(self, con) -> bool:
        """Check if existing table is compatible."""
        if not self._table_exists(con):
            return False

        columns = con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            [self.TABLE_NAME],
        ).df()["column_name"].tolist()

        required_columns = {
            "tconst",
            "titleType",
            "mediaType",
            "primaryTitle",
            "originalTitle",
            "startYear",
            "runtimeMinutes",
            "genres",
            "averageRating",
            "numVotes",
        }

        if not required_columns.issubset(set(columns)):
            return False

        available_types = con.execute(
            f"""
            SELECT DISTINCT titleType
            FROM {self.TABLE_NAME}
            """
        ).df()["titleType"].dropna().tolist()

        available_types = set(available_types)

        # If the old table only contained movies, rebuild it.
        return set(self.ALLOWED_IMDB_TYPES).issubset(available_types)

    def _create_movies_table(self, con):
        basics_path = (self.DATA_DIR / "title.basics.tsv.gz").as_posix()
        ratings_path = (self.DATA_DIR / "title.ratings.tsv.gz").as_posix()

        con.execute(f"""
            CREATE OR REPLACE TABLE {self.TABLE_NAME} AS
            WITH base_titles AS (
                SELECT
                    tconst,
                    titleType,

                    CASE
                        WHEN titleType = 'tvSeries' THEN 'tvseries'
                        ELSE LOWER(titleType)
                    END AS mediaType,

                    primaryTitle,
                    originalTitle,
                    TRY_CAST(isAdult AS INTEGER) AS isAdult,
                    TRY_CAST(startYear AS INTEGER) AS startYear,
                    TRY_CAST(endYear AS INTEGER) AS endYear,
                    TRY_CAST(runtimeMinutes AS INTEGER) AS runtimeMinutes,
                    genres
                FROM read_csv_auto(
                    '{basics_path}',
                    delim = '\t',
                    nullstr = '\\N',
                    sample_size = -1
                )
                WHERE titleType IN ('movie', 'short', 'tvSeries')
                  AND TRY_CAST(startYear AS INTEGER) IS NOT NULL
                  AND TRY_CAST(startYear AS INTEGER) >= 1900
                  AND TRY_CAST(isAdult AS INTEGER) = 0
            ),

            rated_titles AS (
                SELECT
                    b.*,
                    TRY_CAST(r.averageRating AS DOUBLE) AS averageRating,
                    TRY_CAST(r.numVotes AS BIGINT) AS numVotes
                FROM base_titles b
                INNER JOIN read_csv_auto(
                    '{ratings_path}',
                    delim = '\t',
                    nullstr = '\\N',
                    sample_size = -1
                ) r
                ON b.tconst = r.tconst
            )

            SELECT *
            FROM rated_titles
        """)

    @st.cache_data(ttl=3600)
    def load_data(_self):
        """Load IMDb titles, ratings, and votes from DuckDB."""
        con = _self.get_connection()

        if not _self._table_has_expected_schema(con):
            _self._create_movies_table(con)

        df = con.execute(f"""
            SELECT *
            FROM {_self.TABLE_NAME}
            WHERE mediaType IN ('movie', 'short', 'tvseries')
              AND startYear < {_self.CURRENT_YEAR}
        """).df()

        df["startYear"] = pd.to_numeric(df["startYear"], errors="coerce").astype("Int64")
        df["runtimeMinutes"] = pd.to_numeric(df["runtimeMinutes"], errors="coerce")
        df["averageRating"] = pd.to_numeric(df["averageRating"], errors="coerce")
        df["numVotes"] = pd.to_numeric(df["numVotes"], errors="coerce")

        df = df.dropna(subset=["startYear"])
        df["startYear"] = df["startYear"].astype(int)

        return df

    @st.cache_data(ttl=3600)
    def load_streaming_memberships(_self):
        """
        Load Netflix and Prime Video subscription data.

        Expected format:
        year,memberships_mln
        2011,21.60
        2012,30.36
        ...
        """
        frames = []

        files = {
            "Netflix": "netflix.csv",
            "Prime Video": "primevideo.csv",
        }

        for platform, filename in files.items():
            path = _self.DATA_DIR / filename

            if not path.exists():
                continue

            platform_df = pd.read_csv(path)
            platform_df["platform"] = platform

            platform_df["year"] = pd.to_numeric(platform_df["year"], errors="coerce")
            platform_df["memberships_mln"] = pd.to_numeric(
                platform_df["memberships_mln"],
                errors="coerce",
            )

            platform_df = platform_df.dropna(subset=["year", "memberships_mln"])
            platform_df["year"] = platform_df["year"].astype(int)
            platform_df = platform_df[platform_df["year"] < _self.CURRENT_YEAR]

            frames.append(platform_df)

        if not frames:
            return pd.DataFrame(columns=["year", "memberships_mln", "platform"])

        return pd.concat(frames, ignore_index=True)

    @st.cache_data(ttl=3600)
    def get_all_genres(_self):
        """Get all genres in IMDb dataset."""
        con = _self.get_connection()

        result = con.execute(f"""
            SELECT DISTINCT UNNEST(STRING_SPLIT(genres, ',')) AS genre
            FROM {_self.TABLE_NAME}
            WHERE genres IS NOT NULL
              AND genres <> ''
            ORDER BY genre
        """).fetchall()

        return [r[0] for r in result if r[0]]

    @st.cache_data(ttl=3600)
    def get_year_range(_self):
        """Get min/max year range in dataset."""
        con = _self.get_connection()

        result = con.execute(f"""
            SELECT
                MIN(startYear) AS min_year,
                MAX(startYear) AS max_year
            FROM {_self.TABLE_NAME}
            WHERE mediaType IN ('movie', 'short', 'tvseries')
              AND startYear < {_self.CURRENT_YEAR}
        """).fetchone()

        return int(result[0]), int(result[1])

    def _people_table_has_expected_schema(self, con) -> bool:
        result = con.execute(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_name = ?
            """,
            [self.PEOPLE_TABLE_NAME],
        ).fetchone()[0]

        if result == 0:
            return False

        columns = con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = ?
            """,
            [self.PEOPLE_TABLE_NAME],
        ).df()["column_name"].tolist()

        required_columns = {
            "tconst",
            "nconst",
            "primaryName",
            "category",
            "mediaType",
            "primaryTitle",
            "startYear",
            "genres",
            "averageRating",
            "numVotes",
        }

        return required_columns.issubset(set(columns))


    def _create_people_table(self, con):
        principals_path = (self.DATA_DIR / "title.principals.tsv.gz").as_posix()
        names_path = (self.DATA_DIR / "name.basics.tsv.gz").as_posix()

        roles_sql = ", ".join([f"'{role}'" for role in self.PEOPLE_ROLE_OPTIONS])

        con.execute(f"""
            CREATE OR REPLACE TABLE {self.PEOPLE_TABLE_NAME} AS
            SELECT
                m.tconst,
                m.mediaType,
                m.primaryTitle,
                m.startYear,
                m.genres,
                m.runtimeMinutes,
                m.averageRating,
                m.numVotes,

                p.nconst,
                TRY_CAST(p.ordering AS INTEGER) AS ordering,
                p.category,
                p.job,

                n.primaryName,
                TRY_CAST(n.birthYear AS INTEGER) AS birthYear,
                TRY_CAST(n.deathYear AS INTEGER) AS deathYear,
                n.primaryProfession
            FROM {self.TABLE_NAME} m
            INNER JOIN read_csv_auto(
                '{principals_path}',
                delim = '\t',
                nullstr = '\\N',
                sample_size = -1
            ) p
            ON m.tconst = p.tconst
            LEFT JOIN read_csv_auto(
                '{names_path}',
                delim = '\t',
                nullstr = '\\N',
                sample_size = -1
            ) n
            ON p.nconst = n.nconst
            WHERE p.category IN ({roles_sql})
            AND n.primaryName IS NOT NULL
        """)


    def _ensure_people_table(self, con):
        if not self._people_table_has_expected_schema(con):
            self._create_people_table(con)


    def _build_people_filter_sql(
        self,
        media_types=None,
        genres=None,
        year_range=None,
        min_rating=0.0,
        min_votes=0,
        roles=None,
        year=None,
    ):
        """Build WHERE clause for people queries."""
        conditions = ["1 = 1"]
        params = []

        if media_types is not None:
            if len(media_types) == 0:
                conditions.append("1 = 0")
            else:
                placeholders = ", ".join(["?"] * len(media_types))
                conditions.append(f"mediaType IN ({placeholders})")
                params.extend(media_types)

        if roles is not None:
            if len(roles) == 0:
                conditions.append("1 = 0")
            else:
                placeholders = ", ".join(["?"] * len(roles))
                conditions.append(f"category IN ({placeholders})")
                params.extend(roles)

        if year is not None:
            conditions.append("startYear = ?")
            params.append(int(year))

        elif year_range is not None:
            conditions.append("startYear BETWEEN ? AND ?")
            params.extend([int(year_range[0]), int(year_range[1])])

        if min_rating is not None:
            conditions.append("averageRating >= ?")
            params.append(float(min_rating))

        if min_votes is not None:
            conditions.append("numVotes >= ?")
            params.append(int(min_votes))

        if genres:
            genre_conditions = []
            for genre in genres:
                genre_conditions.append("list_contains(string_split(genres, ','), ?)")
                params.append(genre)

            conditions.append("(" + " OR ".join(genre_conditions) + ")")

        return " AND ".join(conditions), params


    @st.cache_data(ttl=3600)
    def get_people_roles(_self):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        result = con.execute(f"""
            SELECT DISTINCT category
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE category IS NOT NULL
            ORDER BY category
        """).fetchall()

        return [r[0] for r in result]


    @st.cache_data(ttl=3600)
    def query_people_kpis(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
        year=None,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
            year=year,
        )

        row = con.execute(f"""
            SELECT
                COUNT(*) AS credits,
                COUNT(DISTINCT nconst) AS people,
                COUNT(DISTINCT tconst) AS titles,
                AVG(averageRating) AS avgRating,
                SUM(numVotes) AS totalVotes
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
        """, params).fetchone()

        return {
            "credits": row[0] or 0,
            "people": row[1] or 0,
            "titles": row[2] or 0,
            "avgRating": row[3],
            "totalVotes": row[4] or 0,
        }


    @st.cache_data(ttl=3600)
    def query_top_people_snapshot(
        _self,
        year,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
        limit=25,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
            year=year,
        )

        params.append(int(limit))

        return con.execute(f"""
            SELECT
                nconst,
                primaryName,
                STRING_AGG(DISTINCT category, ', ') AS roles,
                COUNT(*) AS credits,
                COUNT(DISTINCT tconst) AS titles,
                AVG(averageRating) AS avgRating,
                SUM(numVotes) AS totalVotes,
                MAX(numVotes) AS maxVotes
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
            GROUP BY nconst, primaryName
            ORDER BY credits DESC, totalVotes DESC
            LIMIT ?
        """, params).df()


    @st.cache_data(ttl=3600)
    def query_people_role_distribution(
        _self,
        year,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
            year=year,
        )

        return con.execute(f"""
            SELECT
                category,
                COUNT(*) AS credits,
                COUNT(DISTINCT nconst) AS people,
                COUNT(DISTINCT tconst) AS titles
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
            GROUP BY category
            ORDER BY credits DESC
        """, params).df()


    @st.cache_data(ttl=3600)
    def query_people_yearly_counts(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
        )

        return con.execute(f"""
            SELECT
                startYear,
                COUNT(*) AS credits,
                COUNT(DISTINCT nconst) AS people,
                COUNT(DISTINCT tconst) AS titles
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
            GROUP BY startYear
            ORDER BY startYear
        """, params).df()


    @st.cache_data(ttl=3600)
    def query_people_yearly_role_trends(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
        )

        return con.execute(f"""
            SELECT
                startYear,
                category,
                COUNT(*) AS credits,
                COUNT(DISTINCT nconst) AS people,
                COUNT(DISTINCT tconst) AS titles
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
            GROUP BY startYear, category
            ORDER BY startYear, category
        """, params).df()


    @st.cache_data(ttl=3600)
    def query_new_people_over_time(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
        )

        return con.execute(f"""
            WITH filtered AS (
                SELECT DISTINCT
                    nconst,
                    startYear
                FROM {_self.PEOPLE_TABLE_NAME}
                WHERE {where_sql}
            ),
            first_year AS (
                SELECT
                    nconst,
                    MIN(startYear) AS firstYear
                FROM filtered
                GROUP BY nconst
            )
            SELECT
                firstYear AS startYear,
                COUNT(*) AS newPeople
            FROM first_year
            GROUP BY firstYear
            ORDER BY firstYear
        """, params).df()


    @st.cache_data(ttl=3600)
    def query_top_people_career_heatmap(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
        limit=15,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
        )

        params_with_limit = params + [int(limit)]

        return con.execute(f"""
            WITH filtered AS (
                SELECT
                    nconst,
                    primaryName,
                    startYear,
                    tconst
                FROM {_self.PEOPLE_TABLE_NAME}
                WHERE {where_sql}
            ),
            top_people AS (
                SELECT
                    nconst,
                    MIN(primaryName) AS primaryName,
                    COUNT(*) AS totalCredits
                FROM filtered
                GROUP BY nconst
                ORDER BY totalCredits DESC
                LIMIT ?
            )
            SELECT
                f.startYear,
                t.primaryName,
                COUNT(*) AS credits
            FROM filtered f
            INNER JOIN top_people t
            ON f.nconst = t.nconst
            GROUP BY f.startYear, t.primaryName
            ORDER BY f.startYear, t.primaryName
        """, params_with_limit).df()


    @st.cache_data(ttl=3600)
    def query_top_people_overall(
        _self,
        media_types,
        genres,
        year_range,
        min_rating,
        min_votes,
        roles,
        limit=30,
    ):
        con = _self.get_connection()
        _self._ensure_people_table(con)

        where_sql, params = _self._build_people_filter_sql(
            media_types=media_types,
            genres=genres,
            year_range=year_range,
            min_rating=min_rating,
            min_votes=min_votes,
            roles=roles,
        )

        params.append(int(limit))

        return con.execute(f"""
            SELECT
                nconst,
                primaryName,
                STRING_AGG(DISTINCT category, ', ') AS roles,
                COUNT(*) AS credits,
                COUNT(DISTINCT tconst) AS titles,
                AVG(averageRating) AS avgRating,
                SUM(numVotes) AS totalVotes
            FROM {_self.PEOPLE_TABLE_NAME}
            WHERE {where_sql}
            GROUP BY nconst, primaryName
            ORDER BY credits DESC, totalVotes DESC
            LIMIT ?
        """, params).df()