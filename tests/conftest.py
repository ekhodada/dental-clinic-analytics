"""I share clean fixtures without changing published files."""

import csv
import json
import sqlite3
import pytest
from dental_analytics.clean_and_refresh import BASE
from dental_analytics.validation import context, KEYS


@pytest.fixture(scope="session")
def checked_data():
    """I load the clean snapshot and its reporting database."""
    tables = {}
    for name in KEYS:
        with (BASE / "processed/clean" / f"{name}.csv").open(
            newline="", encoding="utf-8-sig"
        ) as stream:
            tables[name] = list(csv.DictReader(stream))
        for row in tables[name]:
            for key in ("Chairs", "Birth Year", "Available Minutes", "Grace Days"):
                if key in row:
                    row[key] = int(row[key])
    settings = json.loads((BASE / "settings.json").read_text())
    database = sqlite3.connect(f"file:{BASE}/processed/dental_clinic.sqlite?mode=ro", uri=True)
    yield context(tables, settings, database)
    database.close()
