FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN mkdir -p /app/dashboard /app/data

COPY dashboard/requirements.txt /app/dashboard/requirements.txt

RUN pip install -r /app/dashboard/requirements.txt

COPY dashboard/ /app/dashboard/
COPY data/netflix.csv /app/data/netflix.csv
COPY data/primevideo.csv /app/data/primevideo.csv

RUN set -eux; \
    for file in \
        name.basics.tsv.gz \
        title.basics.tsv.gz \
        title.principals.tsv.gz \
        title.ratings.tsv.gz; do \
        curl -fsSL --retry 5 --retry-delay 2 "https://datasets.imdbws.com/${file}" -o "/app/data/${file}"; \
    done

EXPOSE 8095

CMD ["streamlit", "run", "dashboard/Titles.py", "--server.address=0.0.0.0", "--server.port=8095", "--server.headless=true"]