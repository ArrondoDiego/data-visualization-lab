from pathlib import Path
import argparse
import urllib.request
import datetime

import duckdb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch


IMDB_FILES = {
    "name_basics": "name.basics.tsv.gz",
    "title_basics": "title.basics.tsv.gz",
    "title_ratings": "title.ratings.tsv.gz",
    "title_principals": "title.principals.tsv.gz",
}

IMDB_BASE_URL = "https://datasets.imdbws.com"


# ============================================================
# Utility functions
# ============================================================

def ensure_dirs(figures_dir: Path, tables_dir: Path):
    figures_dir.mkdir(parents=True, exist_ok=True)
    tables_dir.mkdir(parents=True, exist_ok=True)


def download_files(data_dir: Path):
    data_dir.mkdir(parents=True, exist_ok=True)

    for filename in IMDB_FILES.values():
        url = f"{IMDB_BASE_URL}/{filename}"
        output_path = data_dir / filename

        if output_path.exists():
            print(f"[OK] Already exists: {output_path}")
            continue

        print(f"[DOWNLOAD] {url}")
        urllib.request.urlretrieve(url, output_path)
        print(f"[SAVED] {output_path}")


def sql_path(path: Path) -> str:
    """
    Escape path for SQL string.
    """
    return str(path.resolve()).replace("'", "''")

def imdb_csv_relation(path: Path) -> str:
    """
    Returns a DuckDB read_csv_auto expression for IMDb TSV files.

    IMDb files:
    - are TSV files;
    - have a header row;
    - use \\N for missing values;
    - are compressed as .gz.
    """
    p = sql_path(path)

    return (
        f"read_csv_auto("
        f"'{p}', "
        f"delim='\\t', "
        f"header=true, "
        f"nullstr='\\N', "
        f"all_varchar=true"
        f")"
    )

def save_current_figure(path: Path):
    plt.tight_layout()
    plt.savefig(path, bbox_inches="tight")
    plt.close()
    print(f"[FIGURE] Saved {path}")


# ============================================================
# Plot functions
# ============================================================

def plot_bar(df, x_col, y_col, title, xlabel, ylabel, output_path, horizontal=False):
    plt.figure(figsize=(9, 5))

    if horizontal:
        plt.barh(df[x_col], df[y_col])
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.gca().invert_yaxis()
    else:
        plt.bar(df[x_col], df[y_col])
        plt.xlabel(xlabel)
        plt.ylabel(ylabel)
        plt.xticks(rotation=45, ha="right")

    plt.title(title)
    save_current_figure(output_path)


def plot_er_diagram(output_path: Path):
    """
    Simple ER-style diagram generated with matplotlib.
    No external Graphviz dependency required.
    """

    fig, ax = plt.subplots(figsize=(11, 6))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")

    boxes = {
        "title.basics": {
            "xy": (0.7, 3.2),
            "text": "title.basics\n\nPK: tconst\n\ntitleType\nstartYear\nruntimeMinutes\ngenres",
        },
        "title.ratings": {
            "xy": (7.0, 4.0),
            "text": "title.ratings\n\nFK: tconst\n\naverageRating\nnumVotes",
        },
        "title.principals": {
            "xy": (7.0, 2.0),
            "text": "title.principals\n\nFK: tconst\nFK: nconst\n\ncategory\njob\ncharacters",
        },
        "name.basics": {
            "xy": (0.7, 0.7),
            "text": "name.basics\n\nPK: nconst\n\nprimaryName\nbirthYear\ndeathYear\nprimaryProfession",
        },
    }

    box_width = 3.1
    box_height = 1.65

    for _, item in boxes.items():
        x, y = item["xy"]
        patch = FancyBboxPatch(
            (x, y),
            box_width,
            box_height,
            boxstyle="round,pad=0.03",
            linewidth=1.2,
            facecolor="white",
            edgecolor="black",
        )
        ax.add_patch(patch)
        ax.text(
            x + 0.15,
            y + box_height - 0.15,
            item["text"],
            va="top",
            ha="left",
            fontsize=9,
            family="monospace",
        )

    def arrow(start, end, label):
        arr = FancyArrowPatch(
            start,
            end,
            arrowstyle="->",
            mutation_scale=15,
            linewidth=1.2,
        )
        ax.add_patch(arr)
        mid_x = (start[0] + end[0]) / 2
        mid_y = (start[1] + end[1]) / 2
        ax.text(mid_x, mid_y + 0.15, label, fontsize=9, ha="center")

    arrow((3.8, 4.0), (7.0, 4.8), "tconst")
    arrow((3.8, 3.6), (7.0, 2.8), "tconst")
    arrow((7.0, 2.1), (3.8, 1.4), "nconst")

    plt.title("Relational structure of the selected IMDb datasets", fontsize=13)
    save_current_figure(output_path)


# ============================================================
# Main EDA generation
# ============================================================

def create_views(con, data_dir: Path):
    paths = {
        key: data_dir / filename
        for key, filename in IMDB_FILES.items()
    }

    for key, path in paths.items():
        if not path.exists():
            raise FileNotFoundError(
                f"Missing file: {path}\n"
                f"Run with --download or manually place the file in the data directory."
            )

    con.execute(
        f"""
        CREATE OR REPLACE VIEW title_basics AS
        SELECT *
        FROM {imdb_csv_relation(paths["title_basics"])}
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE VIEW title_ratings AS
        SELECT *
        FROM {imdb_csv_relation(paths["title_ratings"])}
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE VIEW title_principals AS
        SELECT *
        FROM {imdb_csv_relation(paths["title_principals"])}
        """
    )

    con.execute(
        f"""
        CREATE OR REPLACE VIEW name_basics AS
        SELECT *
        FROM {imdb_csv_relation(paths["name_basics"])}
        """
    )


def generate_dataset_size_table(con, tables_dir: Path):
    rows = []

    datasets = [
        "title_basics",
        "title_ratings",
        "title_principals",
        "name_basics",
    ]

    for dataset in datasets:
        print(f"[TABLE] Counting rows for {dataset}...")
        n_rows = con.execute(f"SELECT COUNT(*) FROM {dataset}").fetchone()[0]
        columns = con.execute(f"DESCRIBE SELECT * FROM {dataset}").fetchdf()
        n_cols = len(columns)

        rows.append({
            "dataset": dataset.replace("_", "."),
            "rows": n_rows,
            "columns": n_cols,
        })

    df = pd.DataFrame(rows)
    output_path = tables_dir / "dataset_size.csv"
    df.to_csv(output_path, index=False)
    print(f"[TABLE] Saved {output_path}")


def generate_title_type_distribution(con, figures_dir: Path):
    df = con.execute(
        """
        SELECT 
            titleType,
            COUNT(*) AS n
        FROM title_basics
        GROUP BY titleType
        ORDER BY n DESC
        """
    ).fetchdf()

    plot_bar(
        df=df,
        x_col="titleType",
        y_col="n",
        title="Distribution of IMDb titles by title type",
        xlabel="Title type",
        ylabel="Number of titles",
        output_path=figures_dir / "title_type_distribution.pdf",
    )


def generate_start_year_distribution(con, figures_dir: Path):
    current_year = datetime.datetime.now().year

    df = con.execute(
        f"""
        SELECT
            TRY_CAST(startYear AS INTEGER) AS year,
            COUNT(*) AS n
        FROM title_basics
        WHERE TRY_CAST(startYear AS INTEGER) IS NOT NULL
          AND TRY_CAST(startYear AS INTEGER) BETWEEN 1870 AND {current_year + 5}
        GROUP BY year
        ORDER BY year
        """
    ).fetchdf()

    plt.figure(figsize=(10, 5))
    plt.plot(df["year"], df["n"])
    plt.title("Temporal distribution of IMDb titles")
    plt.xlabel("Start year")
    plt.ylabel("Number of titles")
    save_current_figure(figures_dir / "start_year_distribution.pdf")


def generate_genre_distribution(con, figures_dir: Path, top_n: int = 20):
    df = con.execute(
        f"""
        SELECT
            genre,
            COUNT(*) AS n
        FROM (
            SELECT UNNEST(STRING_SPLIT(genres, ',')) AS genre
            FROM title_basics
            WHERE genres IS NOT NULL
        )
        WHERE genre IS NOT NULL
          AND genre <> ''
          AND genre <> '\\N'
        GROUP BY genre
        ORDER BY n DESC
        LIMIT {top_n}
        """
    ).fetchdf()

    plot_bar(
        df=df,
        x_col="genre",
        y_col="n",
        title=f"Top {top_n} IMDb genres",
        xlabel="Genre",
        ylabel="Number of titles",
        output_path=figures_dir / "genre_distribution.pdf",
        horizontal=True,
    )


def generate_runtime_distribution(con, figures_dir: Path):
    df = con.execute(
        """
        SELECT
            FLOOR(TRY_CAST(runtimeMinutes AS INTEGER) / 10) * 10 AS runtime_bin,
            COUNT(*) AS n
        FROM title_basics
        WHERE TRY_CAST(runtimeMinutes AS INTEGER) IS NOT NULL
          AND TRY_CAST(runtimeMinutes AS INTEGER) BETWEEN 1 AND 300
        GROUP BY runtime_bin
        ORDER BY runtime_bin
        """
    ).fetchdf()

    plt.figure(figsize=(10, 5))
    plt.bar(df["runtime_bin"], df["n"], width=8)
    plt.title("Distribution of title runtimes")
    plt.xlabel("Runtime bin, minutes")
    plt.ylabel("Number of titles")
    save_current_figure(figures_dir / "runtime_distribution.pdf")


def load_ratings_dataframe(con):
    df = con.execute(
        """
        SELECT
            tconst,
            TRY_CAST(averageRating AS DOUBLE) AS averageRating,
            TRY_CAST(numVotes AS BIGINT) AS numVotes
        FROM title_ratings
        WHERE TRY_CAST(averageRating AS DOUBLE) IS NOT NULL
          AND TRY_CAST(numVotes AS BIGINT) IS NOT NULL
        """
    ).fetchdf()

    return df


def generate_rating_distribution(ratings_df: pd.DataFrame, figures_dir: Path):
    plt.figure(figsize=(9, 5))
    plt.hist(ratings_df["averageRating"], bins=np.arange(0, 10.25, 0.25))
    plt.title("Distribution of IMDb average ratings")
    plt.xlabel("Average rating")
    plt.ylabel("Number of titles")
    save_current_figure(figures_dir / "rating_distribution.pdf")


def generate_num_votes_distribution(ratings_df: pd.DataFrame, figures_dir: Path):
    votes = ratings_df["numVotes"]
    votes = votes[votes > 0]

    bins = np.logspace(0, np.log10(votes.max()), 60)

    plt.figure(figsize=(9, 5))
    plt.hist(votes, bins=bins)
    plt.xscale("log")
    plt.title("Distribution of number of votes")
    plt.xlabel("Number of votes, log scale")
    plt.ylabel("Number of titles")
    save_current_figure(figures_dir / "num_votes_distribution.pdf")


def generate_rating_vs_votes_scatter(
    ratings_df: pd.DataFrame,
    figures_dir: Path,
    sample_size: int = 100_000,
):
    if len(ratings_df) > sample_size:
        plot_df = ratings_df.sample(sample_size, random_state=42)
    else:
        plot_df = ratings_df.copy()

    plot_df = plot_df[plot_df["numVotes"] > 0]

    plt.figure(figsize=(9, 5))
    plt.scatter(
        plot_df["numVotes"],
        plot_df["averageRating"],
        s=4,
        alpha=0.15,
    )
    plt.xscale("log")
    plt.title("IMDb average rating versus number of votes")
    plt.xlabel("Number of votes, log scale")
    plt.ylabel("Average rating")
    save_current_figure(figures_dir / "rating_vs_votes_scatter.pdf")


def generate_principal_category_distribution(con, figures_dir: Path):
    print("[FIGURE] Aggregating title.principals categories. This may take some time...")

    df = con.execute(
        """
        SELECT
            category,
            COUNT(*) AS n
        FROM title_principals
        WHERE category IS NOT NULL
        GROUP BY category
        ORDER BY n DESC
        """
    ).fetchdf()

    plot_bar(
        df=df,
        x_col="category",
        y_col="n",
        title="Distribution of principal role categories",
        xlabel="Role category",
        ylabel="Number of records",
        output_path=figures_dir / "principal_categories.pdf",
        horizontal=True,
    )


def generate_missing_values_table(con, tables_dir: Path):
    checks = {
        "title.basics": {
            "view": "title_basics",
            "columns": [
                "tconst",
                "titleType",
                "primaryTitle",
                "originalTitle",
                "isAdult",
                "startYear",
                "endYear",
                "runtimeMinutes",
                "genres",
            ],
        },
        "title.ratings": {
            "view": "title_ratings",
            "columns": [
                "tconst",
                "averageRating",
                "numVotes",
            ],
        },
        "title.principals": {
            "view": "title_principals",
            "columns": [
                "tconst",
                "ordering",
                "nconst",
                "category",
                "job",
                "characters",
            ],
        },
        "name.basics": {
            "view": "name_basics",
            "columns": [
                "nconst",
                "primaryName",
                "birthYear",
                "deathYear",
                "primaryProfession",
                "knownForTitles",
            ],
        },
    }

    rows = []

    for dataset_name, info in checks.items():
        view = info["view"]
        columns = info["columns"]

        print(f"[TABLE] Missing values for {dataset_name}...")

        total = con.execute(f"SELECT COUNT(*) FROM {view}").fetchone()[0]

        select_parts = []
        for col in columns:
            select_parts.append(
                f"""
                SUM(
                    CASE 
                        WHEN {col} IS NULL OR TRIM({col}) = '' THEN 1 
                        ELSE 0 
                    END
                ) AS {col}
                """
            )

        query = f"""
        SELECT
            {",".join(select_parts)}
        FROM {view}
        """

        result = con.execute(query).fetchone()

        for col, missing in zip(columns, result):
            print(missing)
            rows.append({
                "dataset": dataset_name,
                "variable": col,
                "total_rows": total,
                "missing_values": int(missing),
                "missing_percentage": round(100 * missing / total, 4) if total > 0 else None,
            })

    df = pd.DataFrame(rows)
    output_path = tables_dir / "missing_values.csv"
    df.to_csv(output_path, index=False)
    print(f"[TABLE] Saved {output_path}")


def generate_missing_values_plot(tables_dir: Path, figures_dir: Path):
    df = pd.read_csv(tables_dir / "missing_values.csv")

    selected = df[
        df["variable"].isin([
            "startYear",
            "endYear",
            "runtimeMinutes",
            "genres",
            "averageRating",
            "numVotes",
            "job",
            "characters",
            "birthYear",
            "deathYear",
            "primaryProfession",
            "knownForTitles",
        ])
    ].copy()

    selected["label"] = selected["dataset"] + "." + selected["variable"]
    selected = selected.sort_values("missing_percentage", ascending=True)

    plt.figure(figsize=(9, 6))
    plt.barh(selected["label"], selected["missing_percentage"])
    plt.title("Missing values in selected IMDb variables")
    plt.xlabel("Missing values, percentage")
    plt.ylabel("Variable")
    save_current_figure(figures_dir / "missing_values_selected.pdf")


def generate_join_coverage_table(con, tables_dir: Path, skip_large_joins: bool):
    rows = []

    print("[TABLE] Join coverage: title.basics -> title.ratings")

    result = con.execute(
        """
        SELECT
            COUNT(*) AS total_titles,
            COUNT(r.tconst) AS matched_titles
        FROM title_basics b
        LEFT JOIN title_ratings r
        ON b.tconst = r.tconst
        """
    ).fetchone()

    total, matched = result
    rows.append({
        "join": "title.basics -> title.ratings",
        "base_records": total,
        "matched_records": matched,
        "coverage_percentage": round(100 * matched / total, 4) if total > 0 else None,
    })

    if not skip_large_joins:
        print("[TABLE] Join coverage: title.basics -> title.principals")
        print("        This can take time because title.principals is large.")

        result = con.execute(
            """
            WITH principals_titles AS (
                SELECT DISTINCT tconst
                FROM title_principals
                WHERE tconst IS NOT NULL
            )
            SELECT
                COUNT(*) AS total_titles,
                COUNT(p.tconst) AS matched_titles
            FROM title_basics b
            LEFT JOIN principals_titles p
            ON b.tconst = p.tconst
            """
        ).fetchone()

        total, matched = result
        rows.append({
            "join": "title.basics -> title.principals",
            "base_records": total,
            "matched_records": matched,
            "coverage_percentage": round(100 * matched / total, 4) if total > 0 else None,
        })

        print("[TABLE] Join coverage: title.principals -> name.basics")
        print("        This can also take time.")

        result = con.execute(
            """
            WITH principal_people AS (
                SELECT DISTINCT nconst
                FROM title_principals
                WHERE nconst IS NOT NULL
            )
            SELECT
                COUNT(*) AS total_people_in_principals,
                COUNT(n.nconst) AS matched_people
            FROM principal_people p
            LEFT JOIN name_basics n
            ON p.nconst = n.nconst
            """
        ).fetchone()

        total, matched = result
        rows.append({
            "join": "title.principals -> name.basics",
            "base_records": total,
            "matched_records": matched,
            "coverage_percentage": round(100 * matched / total, 4) if total > 0 else None,
        })

    output_path = tables_dir / "join_coverage.csv"
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"[TABLE] Saved {output_path}")


def generate_title_type_rating_table(con, tables_dir: Path):
    """
    Useful table for the report: ratings by title type.
    Filters out very low-vote titles to reduce noise.
    """

    df = con.execute(
        """
        SELECT
            b.titleType,
            COUNT(*) AS rated_titles,
            AVG(TRY_CAST(r.averageRating AS DOUBLE)) AS mean_rating,
            MEDIAN(TRY_CAST(r.averageRating AS DOUBLE)) AS median_rating,
            AVG(TRY_CAST(r.numVotes AS BIGINT)) AS mean_votes,
            MEDIAN(TRY_CAST(r.numVotes AS BIGINT)) AS median_votes
        FROM title_basics b
        INNER JOIN title_ratings r
        ON b.tconst = r.tconst
        WHERE TRY_CAST(r.averageRating AS DOUBLE) IS NOT NULL
          AND TRY_CAST(r.numVotes AS BIGINT) IS NOT NULL
        GROUP BY b.titleType
        ORDER BY rated_titles DESC
        """
    ).fetchdf()

    output_path = tables_dir / "ratings_by_title_type.csv"
    df.to_csv(output_path, index=False)
    print(f"[TABLE] Saved {output_path}")


def generate_rating_by_title_type_plot(con, figures_dir: Path):
    df = con.execute(
        """
        SELECT
            b.titleType,
            AVG(TRY_CAST(r.averageRating AS DOUBLE)) AS mean_rating,
            COUNT(*) AS n
        FROM title_basics b
        INNER JOIN title_ratings r
        ON b.tconst = r.tconst
        WHERE TRY_CAST(r.averageRating AS DOUBLE) IS NOT NULL
        GROUP BY b.titleType
        HAVING COUNT(*) >= 100
        ORDER BY mean_rating DESC
        """
    ).fetchdf()

    plot_bar(
        df=df,
        x_col="titleType",
        y_col="mean_rating",
        title="Mean IMDb rating by title type",
        xlabel="Title type",
        ylabel="Mean average rating",
        output_path=figures_dir / "mean_rating_by_title_type.pdf",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="../data", help="Directory containing IMDb .tsv.gz files.")
    parser.add_argument("--figures-dir", default="figures", help="Output directory for figures.")
    parser.add_argument("--tables-dir", default="tables", help="Output directory for tables.")
    parser.add_argument("--download", action="store_true", help="Download IMDb datasets if missing.")
    parser.add_argument(
        "--skip-large-joins",
        action="store_true",
        help="Skip expensive join coverage computations involving title.principals.",
    )

    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    figures_dir = Path(args.figures_dir)
    tables_dir = Path(args.tables_dir)

    ensure_dirs(figures_dir, tables_dir)

    if args.download:
        download_files(data_dir)

    con = duckdb.connect(database=":memory:")
    con.execute("PRAGMA threads=4")

    print("[SETUP] Creating DuckDB views...")
    create_views(con, data_dir)

    print("[EDA] Generating ER diagram...")
    plot_er_diagram(figures_dir / "imdb_er_diagram.pdf")

    print("[EDA] Generating dataset size table...")
    generate_dataset_size_table(con, tables_dir)

    print("[EDA] Generating title type distribution...")
    generate_title_type_distribution(con, figures_dir)

    print("[EDA] Generating temporal distribution...")
    generate_start_year_distribution(con, figures_dir)

    print("[EDA] Generating genre distribution...")
    generate_genre_distribution(con, figures_dir)

    print("[EDA] Generating runtime distribution...")
    generate_runtime_distribution(con, figures_dir)

    print("[EDA] Loading ratings dataframe...")
    ratings_df = load_ratings_dataframe(con)

    print("[EDA] Generating rating distribution...")
    generate_rating_distribution(ratings_df, figures_dir)

    print("[EDA] Generating vote distribution...")
    generate_num_votes_distribution(ratings_df, figures_dir)

    print("[EDA] Generating rating-votes scatter plot...")
    generate_rating_vs_votes_scatter(ratings_df, figures_dir)

    print("[EDA] Generating principal category distribution...")
    generate_principal_category_distribution(con, figures_dir)

    print("[EDA] Generating missing values table...")
    generate_missing_values_table(con, tables_dir)

    print("[EDA] Generating missing values figure...")
    generate_missing_values_plot(tables_dir, figures_dir)

    print("[EDA] Generating join coverage table...")
    generate_join_coverage_table(con, tables_dir, args.skip_large_joins)

    print("[EDA] Generating rating by title type table...")
    generate_title_type_rating_table(con, tables_dir)

    print("[EDA] Generating rating by title type figure...")
    generate_rating_by_title_type_plot(con, figures_dir)

    print("\nDone.")
    print(f"Figures saved in: {figures_dir.resolve()}")
    print(f"Tables saved in: {tables_dir.resolve()}")


if __name__ == "__main__":
    main()
