# Usage

> Note that the first time loading the page will take a while, because it needs to load the duckdb indexes.

```bash
python3 -m venv .movie_env
. .movie_env/bin/activate
pip install -r requirements.txt

streamlit run Titles.py
```

## Docker

```bash
# From root of the repo

# Build
docker build -f dashboard/Dockerfile -t dashboard-cabassi-arrondo .

# Run
docker run --rm -p 8095:8095 dashboard-cabassi-arrondo
```
