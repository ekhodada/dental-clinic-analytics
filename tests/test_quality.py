"""I run each of the 34 publication rules as a separate test."""

from dental_analytics import validation


def test_unique_locations(checked_data):
    """I verify unique locations."""
    assert validation.check_unique_locations(checked_data)


def test_unique_patients(checked_data):
    """I verify unique patients."""
    assert validation.check_unique_patients(checked_data)


def test_unique_availability(checked_data):
    """I verify unique availability."""
    assert validation.check_unique_availability(checked_data)


def test_unique_appointments(checked_data):
    """I verify unique appointments."""
    assert validation.check_unique_appointments(checked_data)


def test_unique_treatments(checked_data):
    """I verify unique treatments."""
    assert validation.check_unique_treatments(checked_data)


def test_unique_payments(checked_data):
    """I verify unique payments."""
    assert validation.check_unique_payments(checked_data)


def test_unique_expenses(checked_data):
    """I verify unique expenses."""
    assert validation.check_unique_expenses(checked_data)


def test_unique_recalls(checked_data):
    """I verify unique recalls."""
    assert validation.check_unique_recalls(checked_data)


def test_three_locations(checked_data):
    """I verify three locations."""
    assert validation.check_three_locations(checked_data)


def test_provider_roles(checked_data):
    """I verify provider roles."""
    assert validation.check_provider_roles(checked_data)


def test_session_bounds(checked_data):
    """I verify session bounds."""
    assert validation.check_session_bounds(checked_data)


def test_booking_period(checked_data):
    """I verify booking period."""
    assert validation.check_booking_period(checked_data)


def test_booking_times(checked_data):
    """I verify booking times."""
    assert validation.check_booking_times(checked_data)


def test_treatment_times(checked_data):
    """I verify treatment times."""
    assert validation.check_treatment_times(checked_data)


def test_no_overlapping_provider_bookings(checked_data):
    """I verify provider overlap."""
    assert validation.check_provider_overlap(checked_data)


def test_no_overlapping_chair_bookings(checked_data):
    """I verify chair overlap."""
    assert validation.check_chair_overlap(checked_data)


def test_no_overlapping_patient_bookings(checked_data):
    """I verify patient overlap."""
    assert validation.check_patient_overlap(checked_data)


def test_availability_minutes(checked_data):
    """I verify availability minutes."""
    assert validation.check_availability_minutes(checked_data)


def test_first_visit(checked_data):
    """I verify first visit."""
    assert validation.check_first_visit(checked_data)


def test_charge_math(checked_data):
    """I verify charge math."""
    assert validation.check_charge_math(checked_data)


def test_completed_treatments(checked_data):
    """I verify completed treatments."""
    assert validation.check_completed_treatments(checked_data)


def test_invoice_links(checked_data):
    """I verify invoice links."""
    assert validation.check_invoice_links(checked_data)


def test_overpayments(checked_data):
    """I verify overpayments."""
    assert validation.check_overpayments(checked_data)


def test_payment_dates(checked_data):
    """I verify payment dates."""
    assert validation.check_payment_dates(checked_data)


def test_expense_periods(checked_data):
    """I verify expense periods."""
    assert validation.check_expense_periods(checked_data)


def test_recall_links(checked_data):
    """I verify recall links."""
    assert validation.check_recall_links(checked_data)


def test_care_categories(checked_data):
    """I verify care categories."""
    assert validation.check_care_categories(checked_data)


def test_weekly_revenue(checked_data):
    """I verify weekly revenue."""
    assert validation.check_weekly_revenue(checked_data)


def test_weekly_costs(checked_data):
    """I verify weekly costs."""
    assert validation.check_weekly_costs(checked_data)


def test_weekly_receipts(checked_data):
    """I verify weekly receipts."""
    assert validation.check_weekly_receipts(checked_data)


def test_unpaid_totals(checked_data):
    """I verify unpaid totals."""
    assert validation.check_unpaid_totals(checked_data)


def test_capacity_limits(checked_data):
    """I verify capacity limits."""
    assert validation.check_capacity_limits(checked_data)


def test_patient_segments(checked_data):
    """I verify patient segments."""
    assert validation.check_patient_segments(checked_data)


def test_sqlite_integrity(checked_data):
    """I verify sqlite integrity."""
    assert validation.check_sqlite_integrity(checked_data)
