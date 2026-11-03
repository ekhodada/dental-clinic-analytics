"""I clean snapshots in six small stages before publishing checked reports."""

from pathlib import Path
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
import argparse
import csv
import hashlib
import json
import os
import shutil
import sqlite3
import time
from .validation import KEYS, TABLE_CHECKS, DATABASE_CHECKS, context, cents

BASE = Path(__file__).resolve().parents[1]
MONEY = {"Gross Charge", "Discount", "Adjustment", "Net Charge", "Amount"}
INTS = {"Chairs", "Birth Year", "Available Minutes", "Grace Days"}
DATES = {"First Visit", "Cost From", "Cost To", "Paid On", "Payment Date", "Return Due"}
TIMES = {
    "Work Starts",
    "Work Ends",
    "Booked At",
    "Scheduled Start",
    "Scheduled End",
    "Chair Available At",
    "Cancelled At",
    "Treatment Started",
    "Treatment Finished",
}
FK = {
    "patients": {"Home Location ID": ("locations", "Location ID")},
    "availability": {"Location ID": ("locations", "Location ID")},
    "appointments": {
        "Patient ID": ("patients", "Patient ID"),
        "Location ID": ("locations", "Location ID"),
        "Session ID": ("availability", "Session ID"),
    },
    "treatments": {"Appointment ID": ("appointments", "Appointment ID")},
    "expenses": {"Location ID": ("locations", "Location ID")},
    "recalls": {
        "Patient ID": ("patients", "Patient ID"),
        "Previous Visit ID": ("appointments", "Appointment ID"),
    },
}
REPORTS = [
    "weekly_finances",
    "patient_trends",
    "care_summary",
    "capacity",
    "unpaid_invoices",
    "recall_trends",
    "revenue_bridge",
    "noshow_by_lead_time",
    "receivables_by_age",
    "revenue_per_chair_hour",
    "channel_value",
    "retention_cohorts",
]


def read(path):
    """I read CSV headers and records without modifying the input."""
    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        return reader.fieldnames, list(reader)


def write(path, rows, columns=None):
    """I write CSV records in a stable column order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=columns or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_tables(source, settings):
    """I load full source tables after checking the expected headers."""
    raw = {}
    for name in KEYS:
        columns, rows = read(source / f"{name}.csv")
        if columns != settings["columns"][name]:
            raise ValueError(f"{name}: column names/order differ from settings.json")
        raw[name] = rows
    return raw


def normalize_row(original, table, key, changes):
    """I standardize one row's text, money, dates and booking labels."""
    row = {column: value.strip() for column, value in original.items()}
    if row != original:
        changes["Rows with extra spaces fixed"] += 1
    if not row[key]:
        raise ValueError("Missing record ID")
    for column, value in list(row.items()):
        if column in MONEY:
            number = Decimal(value.replace("$", "").replace(",", "").replace("CAD", "").strip())
            if not number.is_finite() or number < 0 or number != number.quantize(Decimal(".01")):
                raise ValueError(f"Invalid amount: {column}")
            row[column] = format(number, ".2f")
            if row[column] != value:
                changes["Money formats fixed"] += 1
        elif column in INTS:
            row[column] = int(value)
            if row[column] < 0:
                raise ValueError(f"Negative number: {column}")
        elif column in DATES and value:
            try:
                parsed = date.fromisoformat(value)
            except ValueError:
                parsed = datetime.strptime(value, "%m/%d/%Y").date()
            row[column] = parsed.isoformat()
            if row[column] != value:
                changes["Date formats fixed"] += 1
        elif column in TIMES and value:
            row[column] = datetime.fromisoformat(value).isoformat()
    if table == "appointments":
        statuses = {
            "completed": "Completed",
            "cancelled": "Cancelled",
            "canceled": "Cancelled",
            "no show": "No-show",
            "no-show": "No-show",
        }
        row["Status"] = statuses[row["Status"].lower()]
        if row["Status"] != original["Status"]:
            changes["Appointment labels fixed"] += 1
    return row


def reject(table, line, reason, row):
    """I preserve the source record and reason for each rejected row."""
    return {"Table": table, "CSV Row": line, "Problem": reason, "Original Record": json.dumps(row)}


def clean_table(name, rows, tables):
    """I normalize and deduplicate one table while checking its parent keys."""
    key = KEYS[name]
    changes, grouped, rejected = Counter(), defaultdict(list), []
    parents = {
        column: {row[parent_key] for row in tables[parent]}
        for column, (parent, parent_key) in FK.get(name, {}).items()
    }
    invoice_keys = {row["Invoice ID"] for row in tables.get("treatments", [])}
    for line, original in enumerate(rows, 2):
        try:
            row = normalize_row(original, name, key, changes)
            for column, valid_keys in parents.items():
                if row[column] not in valid_keys:
                    raise ValueError(f"Unknown {column}: {row[column]}")
            if name == "payments" and row["Invoice ID"] not in invoice_keys:
                raise ValueError("Unknown Invoice ID")
            grouped[row[key]].append((line, row))
        except (ValueError, KeyError, InvalidOperation) as error:
            rejected.append(reject(name, line, str(error), original))
    cleaned, duplicates = [], 0
    for items in grouped.values():
        if len({json.dumps(row, sort_keys=True) for _, row in items}) > 1:
            rejected.extend(
                reject(name, line, "Conflicting records share an ID", row) for line, row in items
            )
        else:
            cleaned.append(items[0][1])
            duplicates += len(items) - 1
    audit = {
        "Raw Rows": len(rows),
        "Clean Rows": len(cleaned),
        "Duplicate Rows Removed": duplicates,
        "Rejected Rows": len(rejected),
        "Changes": dict(changes),
    }
    return cleaned, audit, rejected


def clean_rows(raw):
    """I clean tables in parent-first order and collect an audit trail."""
    tables, audit, rejected = {}, {}, []
    for name in KEYS:
        tables[name], audit[name], errors = clean_table(name, raw[name], tables)
        rejected.extend(errors)
    return tables, audit, rejected


def validate_rejections(rejected, settings, output):
    """I block any rejected row outside the six named demonstration fixtures."""
    expected = settings.get("demo_rejected_records", {})
    columns = ["Table", "CSV Row", "Problem", "Original Record"]
    write(output / "rejected_rows.csv", rejected, columns)
    unexpected = [
        row
        for row in rejected
        if str(json.loads(row["Original Record"]).get(KEYS[row["Table"]], ""))
        not in expected.get(row["Table"], [])
    ]
    if unexpected:
        raise ValueError("New invalid records found; prior published data preserved.")


def validate(tables, settings, output, database=None, previous=None):
    """I run the tested quality rules and stop on any failing result."""
    data = context(tables, settings, database)
    rules = DATABASE_CHECKS if database is not None else TABLE_CHECKS
    checks = list(previous or [])
    checks.extend(
        {"Check": label, "Result": "PASS" if rule(data) else "FAIL"} for label, rule in rules
    )
    write(output / "quality_checks.csv", checks)
    if any(row["Result"] == "FAIL" for row in checks):
        raise ValueError("Quality checks failed; previous published data preserved.")
    return checks


def calendar_rows(settings):
    """I build daily calendar rows with Monday-based reporting weeks."""
    rows = []
    current = date.fromisoformat(settings["start_date"])
    end = date.fromisoformat(settings["end_date"])
    while current <= end:
        rows.append(
            {
                "Date": current.isoformat(),
                "Week Starting": (current - timedelta(days=current.weekday())).isoformat(),
                "Month": current.strftime("%Y-%m"),
            }
        )
        current += timedelta(days=1)
    return rows


def column_type(column):
    """I choose the database type for a cleaned source column."""
    if column in MONEY:
        return "REAL"
    if column in INTS:
        return "INTEGER"
    return "TEXT"


def build_database(tables, settings, stage):
    """I build a staged database and its SQL reporting views."""
    tables = {**tables, "dates": calendar_rows(settings)}
    database = sqlite3.connect(stage / "dental_clinic.sqlite")
    database.execute("PRAGMA temp_store=MEMORY")
    database.execute("PRAGMA journal_mode=MEMORY")
    for name, rows in tables.items():
        columns = list(rows[0])
        key = KEYS.get(name, "Date")
        definitions = ",".join(
            f'"{column}" {column_type(column)}' + (" PRIMARY KEY" if column == key else "")
            for column in columns
        )
        database.execute(f"CREATE TABLE {name} ({definitions})")
        marks = ",".join("?" for _ in columns)
        database.executemany(
            f"INSERT INTO {name} VALUES ({marks})",
            [[row[column] for column in columns] for row in rows],
        )
        write(stage / "clean" / f"{name}.csv", rows)
    database.executescript((BASE / "code/reports.sql").read_text())
    database.commit()
    return database


def export_reports(database, stage):
    """I export every reporting view to its matching CSV file."""
    for name in REPORTS:
        cursor = database.execute(f"SELECT * FROM {name}")
        columns = [column[0] for column in cursor.description]
        write(
            stage / "reports" / f"{name}.csv",
            [dict(zip(columns, row)) for row in cursor.fetchall()],
            columns,
        )


def publish(stage, output):
    """I replace published outputs only after all validation has passed."""
    for folder in ["clean", "reports"]:
        old = output / folder
        if old.exists():
            shutil.rmtree(old)
        shutil.move(str(stage / folder), str(old))
    os.replace(stage / "dental_clinic.sqlite", output / "dental_clinic.sqlite")
    stage.rmdir()


def save_log(output, audit, rejected, checks, started):
    """I record the refresh results and hashes for later comparisons."""
    result = {
        "Synthetic Data": True,
        "Input Mode": "Complete snapshot replacement",
        "Tables": audit,
        "Checks Passed": len(checks),
        "Rejected Demo Records": len(rejected),
        "Run Seconds": round(time.perf_counter() - started, 3),
        "Clean File Hashes": {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted((output / "clean").glob("*.csv"))
        },
        "Timing Scope": (
            "Cleaning, checks, SQL database and base report extracts; "
            "excludes review, extra financial tests and publication."
        ),
    }
    (output / "refresh_log.json").write_text(json.dumps(result, indent=2))
    print(
        json.dumps(
            {
                key: value
                for key, value in result.items()
                if key not in ["Tables", "Clean File Hashes"]
            },
            indent=2,
        )
    )
    return result


def refresh(source, output):
    """I coordinate loading, cleaning, validation, building, exporting and publication."""
    started = time.perf_counter()
    settings = json.loads((BASE / "settings.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    stage = output / "_building"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir()
    raw = load_tables(source, settings)
    tables, audit, rejected = clean_rows(raw)
    validate_rejections(rejected, settings, output)
    checks = validate(tables, settings, output)
    database = build_database(tables, settings, stage)
    try:
        checks = validate(tables, settings, output, database, checks)
        export_reports(database, stage)
    finally:
        database.close()
    publish(stage, output)
    return save_log(output, audit, rejected, checks, started)


def main():
    """I accept snapshot paths from the command line."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=BASE / "raw")
    parser.add_argument("--output", type=Path, default=BASE / "processed")
    arguments = parser.parse_args()
    refresh(arguments.input, arguments.output)


if __name__ == "__main__":
    main()
