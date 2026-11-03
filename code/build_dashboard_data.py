"""I prepare the dashboard data from the checked clinic records."""

from pathlib import Path
from datetime import datetime
import csv
import json
import sqlite3
from financial_model import build as build_financials, cents
from business_questions import build as build_business_answers


def minutes_between(start, end):
    """I measure elapsed minutes using the existing rounding rule."""
    return round(
        (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds() / 60
    )


def prepare_dashboard_data(financials):
    """I prepare checked source values for the dashboard."""
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
    recalls = rows("recalls")
    expenses = rows("expenses")
    patient_index = {p["Patient ID"]: i for i, p in enumerate(patients)}
    appointment_index = {a["Appointment ID"]: i for i, a in enumerate(appointments)}
    location_index = {l["Location ID"]: i for i, l in enumerate(locations)}
    config = json.loads((base / "settings.json").read_text())
    categories = config["care_categories"]
    category_index = {category: index for index, category in enumerate(categories)}
    images = [
        "01-preventive-care.png",
        "02-restoration.png",
        "03-gum-care.png",
        "04-root-canal.png",
        "05-surgery-tooth-replacement.png",
        "06-alignment-jaw-care.png",
    ]
    (dashboard / "images").mkdir(exist_ok=True)

    invoices = {t["Invoice ID"]: appointment_index[t["Appointment ID"]] for t in treatments}
    database = sqlite3.connect(processed / "dental_clinic.sqlite")
    database.execute("PRAGMA temp_store=MEMORY")
    costs = database.execute(
        "SELECT d.[Date],d.[Location ID],e.[Cost Type],SUM(d.cents) FROM daily_costs d JOIN"
        " expenses e USING([Expense ID]) GROUP BY d.[Date],d.[Location ID],e.[Cost Type]"
    ).fetchall()
    cost_names = sorted({x[2] for x in costs})
    cost_index = {v: i for i, v in enumerate(cost_names)}
    available = database.execute(
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
                    minutes_between(a["Treatment Started"], a["Treatment Finished"])
                    if a["Status"] == "Completed"
                    else 0
                ),
                minutes_between(a["Scheduled Start"], a["Chair Available At"]),
                (
                    1
                    if a["Cancelled At"]
                    and minutes_between(a["Cancelled At"], a["Scheduled Start"]) < 1440
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
    database.close()
    return data


def build():
    """I refresh finances, dashboard data and the three business answers."""
    base = Path(__file__).resolve().parents[1]
    financials = build_financials()
    data = prepare_dashboard_data(financials)
    (base / "dashboard/data.js").write_text(
        "window.CLINIC_DATA=" + json.dumps(data, separators=(",", ":")) + ";"
    )
    build_business_answers()
    print("Exported dashboard data and checked business findings.")


if __name__ == "__main__":
    build()
