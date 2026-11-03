"""I publish the checked reporting data and findings."""

from pathlib import Path
import csv
import json
import sqlite3
from datetime import datetime
from .financial_model import build as build_financials, cents
from .viewer_aggregates import aggregate_viewer
from .business_questions import build as build_business_answers
from .check_analyses import main as check_analysis_reports
from .check_findings import main as check_generated_findings
from .project_docs import build as build_project_docs
from .check_docs import main as check_project_docs
from .export_powerbi import build as build_powerbi_exports
from .check_powerbi import build as check_powerbi_exports


def load_viewer_source(financials):
    """I prepare checked source values for aggregate dashboard calculations."""
    base = Path(__file__).resolve().parents[1]
    processed = base / "processed"
    dashboard = base / "dashboard"

    # I load one cleaned table for reporting.
    def rows(name):
        """I load one cleaned table for reporting."""
        with (processed / "clean" / f"{name}.csv").open(encoding="utf-8-sig", newline="") as f:
            return list(csv.DictReader(f))

    patients = rows("patients")
    appointments = rows("appointments")
    treatments = rows("treatments")
    payments = rows("payments")
    locations = rows("locations")
    availability = rows("availability")
    recalls = rows("recalls")
    expenses = rows("expenses")
    patient_index = {p["Patient ID"]: i for i, p in enumerate(patients)}
    appointment_index = {a["Appointment ID"]: i for i, a in enumerate(appointments)}
    location_index = {l["Location ID"]: i for i, l in enumerate(locations)}
    config = json.loads((base / "settings.json").read_text())
    categories = config["care_categories"]
    category_index = {c: i for i, c in enumerate(categories)}
    images = [
        "01-preventive-care.png",
        "02-restoration.png",
        "03-gum-care.png",
        "04-root-canal.png",
        "05-surgery-tooth-replacement.png",
        "06-alignment-jaw-care.png",
    ]
    (dashboard / "images").mkdir(exist_ok=True)

    minutes = lambda s, e: round(
        (datetime.fromisoformat(e) - datetime.fromisoformat(s)).total_seconds() / 60
    )
    invoices = {t["Invoice ID"]: appointment_index[t["Appointment ID"]] for t in treatments}
    c = sqlite3.connect(processed / "dental_clinic.sqlite")
    c.execute("PRAGMA temp_store=MEMORY")
    costs = c.execute(
        "SELECT d.[Date],d.[Location ID],e.[Cost Type],SUM(d.cents) FROM daily_costs d JOIN"
        " expenses e USING([Expense ID]) GROUP BY d.[Date],d.[Location ID],e.[Cost Type]"
    ).fetchall()
    cost_names = sorted({x[2] for x in costs})
    cost_index = {v: i for i, v in enumerate(cost_names)}
    available = c.execute(
        "SELECT substr([Work Starts],1,10),[Location ID],SUM([Available Minutes]) FROM"
        " availability GROUP BY 1,2"
    ).fetchall()
    data = {
        "locations": [[l["Location Name"], l["City"]] for l in locations],
        "locationIds": [l["Location ID"] for l in locations],
        "categories": categories,
        "images": images,
        "costNames": cost_names,
        "patients": [[int(p["Birth Year"]), p["Gender"], p["First Visit"]] for p in patients],
        "appointments": [
            [
                patient_index[a["Patient ID"]],
                location_index[a["Location ID"]],
                a["Scheduled Start"][:10],
                category_index[a["Care Category"]],
                ["Completed", "Cancelled", "No-show"].index(a["Status"]),
                (
                    minutes(a["Treatment Started"], a["Treatment Finished"])
                    if a["Status"] == "Completed"
                    else 0
                ),
                minutes(a["Scheduled Start"], a["Chair Available At"]),
                (
                    1
                    if a["Cancelled At"]
                    and minutes(a["Cancelled At"], a["Scheduled Start"]) < 1440
                    else 0
                ),
            ]
            for a in appointments
        ],
        "treatments": [
            [
                appointment_index[t["Appointment ID"]],
                category_index[t["Care Category"]],
                round(float(t["Net Charge"]) * 100),
            ]
            for t in treatments
        ],
        "payments": [
            [invoices[r["Invoice ID"]], r["Payment Date"], round(float(r["Amount"]) * 100)]
            for r in payments
        ],
        "costs": [[d, location_index[l], cost_index[cat], amt] for d, l, cat, amt in costs],
        "cashExpenses": [
            [x["Paid On"], location_index[x["Location ID"]], cents(x["Amount"])]
            for x in expenses
            if x["Paid On"] and config["start_date"] <= x["Paid On"] <= config["end_date"]
        ],
        "financialMonths": financials["monthly"],
        "financialAging": financials["aging"],
        "financialPolicy": financials["policy"],
        "riskCosts": [[d, location_index[l], amount] for d, l, amount in financials["provisions"]],
        "available": [[d, location_index[l], m] for d, l, m in available],
        "recalls": [
            [
                patient_index[q["Patient ID"]],
                appointment_index[q["Previous Visit ID"]],
                q["Return Due"],
                int(q["Grace Days"]),
            ]
            for q in recalls
        ],
    }
    c.close()
    return data


def build():
    """I publish aggregate viewer data and checked findings after financial reconciliation."""
    base = Path(__file__).resolve().parents[1]
    financials = build_financials()
    source = load_viewer_source(financials)
    aggregates = aggregate_viewer(source)
    (base / "dashboard/data.js").write_text(
        "window.CLINIC_DATA=" + json.dumps(aggregates, separators=(",", ":")) + ";"
    )
    build_business_answers()
    build_powerbi_exports()
    check_powerbi_exports()
    check_analysis_reports()
    check_generated_findings()
    build_project_docs()
    check_project_docs()
    print("Exported aggregate viewer data, checked findings and reconciled finances.")


if __name__ == "__main__":
    build()
