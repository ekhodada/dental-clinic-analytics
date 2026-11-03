"""I export a small Power BI star schema from the checked reporting database."""

import csv
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def query_rows(connection, sql):
    """I read a SQL result as named records in a stable order."""
    cursor = connection.execute(sql)
    fields = [column[0] for column in cursor.description]
    return [dict(zip(fields, row)) for row in cursor]


def date_rows(connection):
    """I prepare a complete calendar with readable labels and sorting columns."""
    rows = []
    for (value,) in connection.execute("SELECT Date FROM dates ORDER BY Date"):
        day = date.fromisoformat(value)
        rows.append(
            {
                "Date": value,
                "Year": day.year,
                "Quarter": f"Q{(day.month - 1) // 3 + 1}",
                "MonthNumber": day.month,
                "MonthName": day.strftime("%b"),
                "YearMonth": value[:7],
                "YearMonthSort": day.year * 100 + day.month,
                "WeekStarting": (day - timedelta(days=day.weekday())).isoformat(),
                "WeekdayNumber": day.weekday() + 1,
                "WeekdayName": day.strftime("%a"),
            }
        )
    return rows


def category_rows(settings):
    """I assign stable keys and short chart labels to the six care categories."""
    names = ["Routine care", "Restoration", "Gum care", "Root canal", "Surgery", "Other care"]
    return [
        {
            "CareCategoryID": f"C{i:02}",
            "CareCategory": category,
            "ShortName": names[i - 1],
            "CategorySort": i,
        }
        for i, category in enumerate(settings["care_categories"], 1)
    ]


def appointment_rows(connection, category_keys):
    """I export one booking with its lead time, outcome and actual care minutes."""
    rows = query_rows(
        connection,
        '''SELECT a."Appointment ID" AppointmentID,
        substr(a."Scheduled Start",1,10) AppointmentDate,
        a."Location ID" LocationID,a."Patient ID" PatientID,
        a."Care Category" CareCategoryID,a."Main Service" MainService,a.Status,
        a."Booked At" BookedAt,a."Scheduled Start" ScheduledStart,
        a."Treatment Started" TreatmentStarted,a."Treatment Finished" TreatmentFinished,
        a."Chair Available At" ChairAvailableAt,p."Birth Year" BirthYear
        FROM appointments a JOIN patients p USING("Patient ID")
        ORDER BY a."Appointment ID"''',
    )
    for row in rows:
        start = datetime.fromisoformat(row["ScheduledStart"])
        lead = (start - datetime.fromisoformat(row["BookedAt"])).days
        row["LeadDays"] = lead
        row["LeadTimeBand"] = "0-6 days" if lead < 7 else "7-29 days" if lead < 30 else "30+ days"
        row["LeadTimeSort"] = 1 if lead < 7 else 2 if lead < 30 else 3
        row["TreatmentMinutes"] = 0
        if row["Status"] == "Completed":
            row["TreatmentMinutes"] = round(
                (
                    datetime.fromisoformat(row["TreatmentFinished"])
                    - datetime.fromisoformat(row["TreatmentStarted"])
                ).total_seconds()
                / 60
            )
        row["ReservedMinutes"] = round(
            (datetime.fromisoformat(row.pop("ChairAvailableAt")) - start).total_seconds() / 60
        )
        row["AgeAtVisit"] = start.year - row.pop("BirthYear")
        boundaries = [(17, "0-17"), (34, "18-34"), (49, "35-49"), (64, "50-64"), (150, "65+")]
        row["AgeGroupSort"], row["AgeGroup"] = next(
            (i, label)
            for i, (maximum, label) in enumerate(boundaries, 1)
            if row["AgeAtVisit"] <= maximum
        )
        row["CareCategoryID"] = category_keys[row["CareCategoryID"]]
        del row["TreatmentStarted"], row["TreatmentFinished"]
    return rows


def load_tables(connection, settings):
    """I build four dimensions and four facts without joining receipt and service lines."""
    categories = category_rows(settings)
    category_keys = {row["CareCategory"]: row["CareCategoryID"] for row in categories}
    tables = {
        "dim_date": date_rows(connection),
        "dim_location": query_rows(
            connection,
            '''SELECT "Location ID" LocationID,
            "Location Name" LocationName,City,Chairs FROM locations ORDER BY "Location ID"''',
        ),
        "dim_patient": query_rows(
            connection,
            '''SELECT "Patient ID" PatientID,
            "Birth Year" BirthYear,Gender,"First Visit" FirstVisit,
            "How They Found Us" AcquisitionChannel FROM patients ORDER BY "Patient ID"''',
        ),
        "dim_care_category": categories,
        "fact_appointments": appointment_rows(connection, category_keys),
        "fact_treatments": query_rows(
            connection,
            '''SELECT t."Treatment Record ID" TreatmentID,
            t."Appointment ID" AppointmentID,t."Invoice ID" InvoiceID,
            substr(a."Scheduled Start",1,10) ServiceDate,a."Location ID" LocationID,
            a."Patient ID" PatientID,t."Care Category" CareCategoryID,t.Treatment,
            CAST(ROUND(t."Gross Charge"*100) AS INTEGER) GrossChargeCents,
            CAST(ROUND(t.Discount*100) AS INTEGER) DiscountCents,
            CAST(ROUND(t.Adjustment*100) AS INTEGER) AdjustmentCents,
            CAST(ROUND(t."Net Charge"*100) AS INTEGER) NetChargeCents
            FROM treatments t JOIN appointments a USING("Appointment ID")
            ORDER BY t."Treatment Record ID"''',
        ),
        "fact_payments": query_rows(
            connection,
            '''SELECT p."Payment ID" PaymentID,
            p."Invoice ID" InvoiceID,p."Payment Date" PaymentDate,
            a."Location ID" LocationID,a."Patient ID" PatientID,p."Paid By" PaidBy,
            CAST(ROUND(p.Amount*100) AS INTEGER) AmountCents
            FROM payments p JOIN invoice_totals i USING("Invoice ID")
            JOIN appointments a USING("Appointment ID") ORDER BY p."Payment ID"''',
        ),
        "fact_expenses": query_rows(
            connection,
            """SELECT c."Expense ID" ExpenseID,
            c.Date CostDate,c."Location ID" LocationID,e."Cost Type" CostType,c.cents CostCents
            FROM daily_costs c JOIN expenses e USING("Expense ID")
            ORDER BY c."Expense ID",c.Date""",
        ),
    }
    for row in tables["fact_treatments"]:
        row["CareCategoryID"] = category_keys[row["CareCategoryID"]]
    return tables


def model_metadata(tables):
    """I describe row counts, grains and the thirteen single-direction relationships."""
    grains = {
        "dim_date": "One calendar day",
        "dim_location": "One branch",
        "dim_patient": "One registered patient",
        "dim_care_category": "One care category",
        "fact_appointments": "One booking, including cancelled and missed bookings",
        "fact_treatments": "One completed billed service; invoices may have several services",
        "fact_payments": "One receipt; an invoice may have several receipts",
        "fact_expenses": "One expense allocated to one calendar day; ExpenseID repeats by day",
    }
    relationships = []
    for fact, date_column in [
        ("fact_appointments", "AppointmentDate"),
        ("fact_treatments", "ServiceDate"),
        ("fact_payments", "PaymentDate"),
        ("fact_expenses", "CostDate"),
    ]:
        relationships.append(["dim_date", "Date", fact, date_column])
        relationships.append(["dim_location", "LocationID", fact, "LocationID"])
        if fact != "fact_expenses":
            relationships.append(["dim_patient", "PatientID", fact, "PatientID"])
        if fact in ["fact_appointments", "fact_treatments"]:
            relationships.append(["dim_care_category", "CareCategoryID", fact, "CareCategoryID"])
    return {
        "tables": {
            name: {"rows": len(rows), "grain": grains[name], "columns": list(rows[0])}
            for name, rows in tables.items()
        },
        "relationships": relationships,
        "relationship_settings": "Active; one dimension to many fact rows; Single direction",
        "amount_unit": "Integer CAD cents; DAX divides totals by 100",
    }


def build():
    """I refresh the Power BI exports and model manifest from the checked database."""
    settings = json.loads((BASE / "settings.json").read_text())
    output = BASE / "powerbi"
    output.mkdir(exist_ok=True)
    with sqlite3.connect(BASE / "processed/dental_clinic.sqlite") as connection:
        tables = load_tables(connection, settings)
    for name, rows in tables.items():
        with (output / f"{name}.csv").open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    metadata = model_metadata(tables)
    (output / "model.json").write_text(json.dumps(metadata, indent=2))
    from .powerbi_guide import build as build_guide

    build_guide(tables)
    print("Exported eight Power BI tables with thirteen dimension-to-fact relationships.")
    return tables


if __name__ == "__main__":
    build()
