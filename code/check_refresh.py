"""Repeatability and rejection-gate tests. Run with --work pointing to a scratch folder."""

import json
import csv
import shutil
import hashlib
import contextlib
import io
import argparse
from pathlib import Path
from clean_and_refresh import BASE, refresh, read, write


def main(work):
    """I check repeatability and preserve outputs when invalid input arrives."""
    output = work / "results"
    source = work / "raw"
    source.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(BASE / "raw", source, dirs_exist_ok=True)
    with contextlib.redirect_stdout(io.StringIO()):
        first_run = refresh(source, output)
        second_run = refresh(source, output)
    assert first_run["Clean File Hashes"] == second_run["Clean File Hashes"]
    expected = json.loads((BASE / "settings.json").read_text())["expected_rows"]
    assert all(
        first_run["Tables"][name]["Clean Rows"] == count for name, count in expected.items()
    )
    assert sum(t["Duplicate Rows Removed"] for t in first_run["Tables"].values()) == 100
    assert first_run["Rejected Demo Records"] == 6
    database_path = output / "dental_clinic.sqlite"
    before = hashlib.sha256(database_path.read_bytes()).hexdigest()
    fields, rows = read(source / "payments.csv")
    bad = dict(rows[0])
    bad["Payment ID"] = "UNEXPECTED"
    bad["Invoice ID"] = "MISSING"
    rows.append(bad)
    write(source / "payments.csv", rows, fields)
    blocked = False
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            refresh(source, output)
    except ValueError:
        blocked = True
    assert blocked and hashlib.sha256(database_path.read_bytes()).hexdigest() == before
    result = {
        "Same inputs produce identical clean files": True,
        "All expected row counts match": True,
        "100 duplicate rows removed": True,
        "Six demo errors isolated": True,
        "New invalid payment blocks publication": True,
        "Prior published database preserved": True,
        "Measured run seconds": [first_run["Run Seconds"], second_run["Run Seconds"]],
    }
    (BASE / "processed" / "repeatability_checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--work", type=Path, required=True)
    main(p.parse_args().work)
