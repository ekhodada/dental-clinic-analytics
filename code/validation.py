"""I expose the same quality rules to the pipeline and individual tests."""

from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal

KEYS = {
    "locations": "Location ID",
    "patients": "Patient ID",
    "availability": "Session ID",
    "appointments": "Appointment ID",
    "treatments": "Treatment Record ID",
    "payments": "Payment ID",
    "expenses": "Expense ID",
    "recalls": "Recall ID",
}


def cents(value):
    """I convert a validated dollar amount to integer cents."""
    return int(Decimal(str(value)) * 100)


def context(tables, settings, database=None):
    """I prepare shared lookups without changing any source record."""
    result = {"tables": tables, "settings": settings, "database": database}
    result["appointments"] = {r["Appointment ID"]: r for r in tables["appointments"]}
    result["availability"] = {r["Session ID"]: r for r in tables["availability"]}
    result["patients"] = {r["Patient ID"]: r for r in tables["patients"]}
    bills, paid = defaultdict(int), defaultdict(int)
    invoice_visits, visit_bills = defaultdict(set), defaultdict(set)
    for row in tables["treatments"]:
        bills[row["Invoice ID"]] += cents(row["Net Charge"])
        invoice_visits[row["Invoice ID"]].add(row["Appointment ID"])
        visit_bills[row["Appointment ID"]].add(row["Invoice ID"])
    for row in tables["payments"]:
        paid[row["Invoice ID"]] += cents(row["Amount"])
    result.update(bills=bills, paid=paid, invoice_visits=invoice_visits, visit_bills=visit_bills)
    return result


def unique_ids(data, table):
    """I check that every row has a distinct table key."""
    rows = data["tables"][table]
    return len({r[KEYS[table]] for r in rows}) == len(rows)


def check_unique_locations(data):
    """I check distinct location identifiers."""
    return unique_ids(data, "locations")


def check_unique_patients(data):
    """I check distinct patient identifiers."""
    return unique_ids(data, "patients")


def check_unique_availability(data):
    """I check distinct working-session identifiers."""
    return unique_ids(data, "availability")


def check_unique_appointments(data):
    """I check distinct appointment identifiers."""
    return unique_ids(data, "appointments")


def check_unique_treatments(data):
    """I check distinct treatment-record identifiers."""
    return unique_ids(data, "treatments")


def check_unique_payments(data):
    """I check distinct receipt identifiers."""
    return unique_ids(data, "payments")


def check_unique_expenses(data):
    """I check distinct expense identifiers."""
    return unique_ids(data, "expenses")


def check_unique_recalls(data):
    """I check distinct recall identifiers."""
    return unique_ids(data, "recalls")


def check_three_locations(data):
    """I check the expected branch count."""
    return len(data["tables"]["locations"]) == 3


def check_provider_roles(data):
    """I check that six dentists and six hygienists have consistent roles."""
    roles = defaultdict(set)
    for row in data["availability"].values():
        roles[row["Provider ID"]].add(row["Provider Type"])
    return Counter(next(iter(values)) for values in roles.values() if len(values) == 1) == {
        "Dentist": 6,
        "Hygienist": 6,
    }


def check_session_bounds(data):
    """I check that each booking fits its branch and working session."""
    for row in data["appointments"].values():
        session = data["availability"][row["Session ID"]]
        if not (
            session["Work Starts"]
            <= row["Scheduled Start"]
            < row["Scheduled End"]
            < row["Chair Available At"]
            <= session["Work Ends"]
            and row["Location ID"] == session["Location ID"]
        ):
            return False
    return True


def check_booking_period(data):
    """I check that bookings fall within the reporting window."""
    settings = data["settings"]
    return all(
        settings["start_date"] <= row["Scheduled Start"][:10] <= settings["end_date"]
        for row in data["appointments"].values()
    )


def check_booking_times(data):
    """I check that bookings and cancellations precede planned care."""
    return all(
        row["Booked At"] <= row["Scheduled Start"]
        and (
            not row["Cancelled At"]
            or row["Booked At"] <= row["Cancelled At"] <= row["Scheduled Start"]
        )
        for row in data["appointments"].values()
    )


def check_treatment_times(data):
    """I check actual care timestamps against attendance and reserved time."""
    for row in data["appointments"].values():
        if row["Status"] == "Completed":
            if (
                not row["Scheduled Start"]
                <= row["Treatment Started"]
                < row["Treatment Finished"]
                <= row["Chair Available At"]
            ):
                return False
        elif row["Treatment Started"] or row["Treatment Finished"]:
            return False
    return True


def no_overlaps(data, group_by):
    """I compare adjacent reservations within each resource group."""
    groups = defaultdict(list)
    for row in data["appointments"].values():
        groups[group_by(row)].append(row)
    for rows in groups.values():
        rows.sort(key=lambda row: row["Scheduled Start"])
        if any(
            left["Chair Available At"] > right["Scheduled Start"]
            for left, right in zip(rows, rows[1:])
        ):
            return False
    return True


def check_provider_overlap(data):
    """I reject overlapping bookings for a clinician."""
    return no_overlaps(data, lambda row: data["availability"][row["Session ID"]]["Provider ID"])


def check_chair_overlap(data):
    """I reject overlapping bookings for a branch chair."""
    return no_overlaps(
        data, lambda row: (row["Location ID"], data["availability"][row["Session ID"]]["Chair ID"])
    )


def check_patient_overlap(data):
    """I reject overlapping bookings for a patient."""
    return no_overlaps(data, lambda row: row["Patient ID"])


def check_availability_minutes(data):
    """I reconcile recorded working minutes with session timestamps."""
    return all(
        row["Available Minutes"]
        == int(
            (
                datetime.fromisoformat(row["Work Ends"])
                - datetime.fromisoformat(row["Work Starts"])
            ).total_seconds()
            / 60
        )
        for row in data["availability"].values()
    )


def check_first_visit(data):
    """I check that completed care does not precede the patient's first visit."""
    return all(
        data["patients"][row["Patient ID"]]["First Visit"] <= row["Scheduled Start"][:10]
        for row in data["appointments"].values()
        if row["Status"] == "Completed"
    )


def check_charge_math(data):
    """I reconcile gross charges, discounts and adjustments with net charges."""
    return all(
        cents(row["Gross Charge"]) - cents(row["Discount"]) - cents(row["Adjustment"])
        == cents(row["Net Charge"])
        for row in data["tables"]["treatments"]
    )


def check_completed_treatments(data):
    """I require every billed service to belong to completed care."""
    return all(
        data["appointments"][row["Appointment ID"]]["Status"] == "Completed"
        for row in data["tables"]["treatments"]
    )


def check_invoice_links(data):
    """I require exactly one invoice for each completed visit."""
    completed = {
        row["Appointment ID"]
        for row in data["appointments"].values()
        if row["Status"] == "Completed"
    }
    return (
        set(data["visit_bills"]) == completed
        and all(len(values) == 1 for values in data["visit_bills"].values())
        and all(len(values) == 1 for values in data["invoice_visits"].values())
    )


def check_overpayments(data):
    """I check that invoice receipts do not exceed charges."""
    return all(data["paid"][key] <= amount for key, amount in data["bills"].items())


def check_payment_dates(data):
    """I check that receipts follow care and stay inside the observation cutoff."""
    for row in data["tables"]["payments"]:
        visit = next(iter(data["invoice_visits"][row["Invoice ID"]]))
        if (
            not data["appointments"][visit]["Scheduled Start"][:10]
            <= row["Payment Date"]
            <= data["settings"]["end_date"]
        ):
            return False
    return True


def check_expense_periods(data):
    """I require the calendar to cover each full expense period."""
    settings = data["settings"]
    return all(
        settings["start_date"] <= row["Cost From"] <= row["Cost To"] <= settings["end_date"]
        for row in data["tables"]["expenses"]
    )


def check_recall_links(data):
    """I match recall plans to their patient and completed source visit."""
    for row in data["tables"]["recalls"]:
        visit = data["appointments"][row["Previous Visit ID"]]
        if not (
            visit["Patient ID"] == row["Patient ID"]
            and visit["Status"] == "Completed"
            and row["Return Due"] > visit["Scheduled Start"][:10]
        ):
            return False
    return True


def check_care_categories(data):
    """I check the expected set of billed care categories."""
    return {row["Care Category"] for row in data["tables"]["treatments"]} == set(
        data["settings"]["care_categories"]
    )


def database_total(data, query):
    """I convert an aggregated SQL dollar result back to cents."""
    return round(data["database"].execute(query).fetchone()[0] * 100)


def check_weekly_revenue(data):
    """I reconcile weekly revenue with the cleaned service charges."""
    return database_total(data, 'SELECT SUM("Service Revenue") FROM weekly_finances') == sum(
        data["bills"].values()
    )


def check_weekly_costs(data):
    """I reconcile allocated weekly costs with the cleaned expenses."""
    return database_total(data, 'SELECT SUM("Operating Costs") FROM weekly_finances') == sum(
        cents(row["Amount"]) for row in data["tables"]["expenses"]
    )


def check_weekly_receipts(data):
    """I reconcile weekly receipts with the cleaned payments."""
    return database_total(data, 'SELECT SUM("Money Received") FROM weekly_finances') == sum(
        data["paid"].values()
    )


def check_unpaid_totals(data):
    """I reconcile outstanding balances with charges less receipts."""
    return database_total(data, 'SELECT SUM("Still Owed") FROM unpaid_invoices') == sum(
        data["bills"].values()
    ) - sum(data["paid"].values())


def check_capacity_limits(data):
    """I check that booked and direct-care capacity stay within availability."""
    return (
        data["database"]
        .execute('SELECT COUNT(*) FROM capacity WHERE "Booked Capacity">1 OR "Treatment Use">1')
        .fetchone()[0]
        == 0
    )


def check_patient_segments(data):
    """I reconcile monthly new and returning segments with patients seen."""
    return (
        data["database"]
        .execute(
            'SELECT COUNT(*) FROM patient_trends WHERE "New Patients"+"Returning'
            ' Patients"<>"Patients Seen"'
        )
        .fetchone()[0]
        == 0
    )


def check_sqlite_integrity(data):
    """I require SQLite's storage integrity check to pass."""
    return data["database"].execute("PRAGMA integrity_check").fetchone()[0] == "ok"


TABLE_CHECKS = [
    ("locations: unique IDs", check_unique_locations),
    ("patients: unique IDs", check_unique_patients),
    ("availability: unique IDs", check_unique_availability),
    ("appointments: unique IDs", check_unique_appointments),
    ("treatments: unique IDs", check_unique_treatments),
    ("payments: unique IDs", check_unique_payments),
    ("expenses: unique IDs", check_unique_expenses),
    ("recalls: unique IDs", check_unique_recalls),
    ("Three locations", check_three_locations),
    ("Six dentists and six hygienists", check_provider_roles),
    ("Appointments fit available sessions", check_session_bounds),
    ("Bookings fall in analysis period", check_booking_period),
    ("Booking and cancellation times make sense", check_booking_times),
    ("Actual treatment times match attendance", check_treatment_times),
    ("Provider: no overlapping bookings", check_provider_overlap),
    ("Chair: no overlapping bookings", check_chair_overlap),
    ("Patient: no overlapping bookings", check_patient_overlap),
    ("Availability minutes match work blocks", check_availability_minutes),
    ("Patients first visit is consistent", check_first_visit),
    ("Treatment charge calculations reconcile", check_charge_math),
    ("Treatments belong to completed visits", check_completed_treatments),
    ("One invoice per completed visit", check_invoice_links),
    ("Invoices are not overpaid", check_overpayments),
    ("Payment dates are valid", check_payment_dates),
    ("Expense periods covered by calendar", check_expense_periods),
    ("Recall plans match patients and dates", check_recall_links),
    ("Six known care categories", check_care_categories),
]
DATABASE_CHECKS = [
    ("Weekly revenue matches treatments", check_weekly_revenue),
    ("Weekly costs match expenses", check_weekly_costs),
    ("Weekly collections match payments", check_weekly_receipts),
    ("Unpaid invoice amounts reconcile", check_unpaid_totals),
    ("Capacity rates do not exceed 100%", check_capacity_limits),
    ("Monthly new and returning patients reconcile", check_patient_segments),
    ("SQLite file integrity", check_sqlite_integrity),
]
