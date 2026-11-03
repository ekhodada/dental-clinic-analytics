"""I publish aggregate numbers for every supported viewer selection."""

from collections import defaultdict
from datetime import date, timedelta


def matches(day, year, month):
    """I match a calendar date to the selected year and month."""
    return (year == "all" or day[:4] == year) and (month == "all" or day[5:7] == month)


def week_start(day):
    """I find the Monday containing a calendar date."""
    value = date.fromisoformat(day)
    return (value - timedelta(days=value.weekday())).isoformat()


def overdue_count(data, cutoff, location):
    """I count overdue latest recall plans at a month-end cutoff."""
    appointments = data["appointments"]
    latest = {}
    for plan in data["recalls"]:
        visit = appointments[plan[1]]
        if visit[2] > cutoff:
            continue
        previous = latest.get(plan[0])
        if previous is None or (appointments[previous[1]][2], previous[1]) < (visit[2], plan[1]):
            latest[plan[0]] = plan
    return sum(
        1
        for plan in latest.values()
        if (location == "all" or appointments[plan[1]][1] == location)
        and (date.fromisoformat(plan[2]) + timedelta(days=plan[3])).isoformat() < cutoff
    )


def category_totals(data, completed):
    """I count distinct people, services and net charges for each care category."""
    people = [set() for _ in data["categories"]]
    services = [0] * len(people)
    revenue = [0] * len(people)
    for visit, category, charge in data["treatments"]:
        if visit in completed:
            people[category].add(data["appointments"][visit][0])
            services[category] += 1
            revenue[category] += charge
    return [[len(group), count, amount] for group, count, amount in zip(people, services, revenue)]


def selection_summary(data, year, month, location, calendar, net, recall_counts):
    """I calculate one filter selection without exporting individual records."""
    appointments, patients = data["appointments"], data["patients"]
    dates = [day for day in calendar if matches(day, year, month)]
    months = sorted({day[:7] for day in dates})
    first, cutoff = dates[0], dates[-1]
    selected = [
        i
        for i, row in enumerate(appointments)
        if matches(row[2], year, month) and (location == "all" or row[1] == location)
    ]
    completed = [i for i in selected if appointments[i][4] == 0]
    completed_set = set(completed)
    people = {appointments[i][0] for i in completed}
    new = sum(first <= patients[p][2] <= cutoff for p in people)
    first_selected = {}
    for i in completed:
        person, _, day, *_ = appointments[i]
        first_selected[person] = min(day, first_selected.get(person, day))
    ages = [int(day[:4]) - patients[person][0] for person, day in first_selected.items()]
    age_rows = [[0, 0, 0] for _ in range(5)]
    for person, day in first_selected.items():
        age = int(day[:4]) - patients[person][0]
        gender = (
            0 if patients[person][1] == "Female" else 1 if patients[person][1] == "Male" else 2
        )
        for j, (low, high) in enumerate([(0, 17), (18, 34), (35, 49), (50, 64), (65, 150)]):
            if low <= age <= high:
                age_rows[j][gender] += 1
                break
    availability = [
        row
        for row in data["available"]
        if matches(row[0], year, month) and (location == "all" or row[1] == location)
    ]
    costs = [
        row
        for row in data["costs"]
        if matches(row[0], year, month) and (location == "all" or row[1] == location)
    ]
    receipts = [
        row
        for row in data["payments"]
        if matches(row[1], year, month)
        and (location == "all" or appointments[row[0]][1] == location)
    ]
    revenue = sum(net[i] for i in completed)
    cost = sum(row[3] for row in costs)
    received = sum(row[2] for row in receipts)
    paid_visits = sum(
        row[2] for row in data["payments"] if row[0] in completed_set and row[1] <= cutoff
    )
    cash_paid = sum(
        row[2]
        for row in data["cashExpenses"]
        if matches(row[0], year, month) and (location == "all" or row[1] == location)
    )
    risk = sum(
        row[2]
        for row in data["riskCosts"]
        if matches(row[0], year, month) and (location == "all" or row[1] == location)
    )
    snapshot = [
        row
        for row in data["financialMonths"]
        if row["Month"] == cutoff[:7]
        and (location == "all" or data["locationIds"].index(row["Location ID"]) == location)
    ]
    financial = {
        key: round(sum(float(row[key]) for row in snapshot) * 100)
        for key in ["Gross Receivables", "Scenario Loss Allowance", "Scenario Net Receivables"]
    }
    aging = [
        round(
            sum(
                float(row["Gross Balance"])
                for row in data["financialAging"]
                if row["As Of"] == cutoff
                and row["Invoice Age"] == band["label"]
                and (
                    location == "all" or data["locationIds"].index(row["Location ID"]) == location
                )
            )
            * 100
        )
        for band in data["financialPolicy"]["age_bands"]
    ]
    branch_people, branch_finance = [], []
    for j in range(len(data["locations"])):
        if location != "all" and j != location:
            continue
        ids = [i for i in completed if appointments[i][1] == j]
        branch_people.append(
            [
                j,
                len({appointments[i][0] for i in ids}),
                len(ids),
                len({appointments[i][0] for i in ids if patients[appointments[i][0]][2] >= first}),
            ]
        )
        branch_finance.append(
            [
                j,
                sum(net[i] for i in ids),
                sum(row[2] for row in receipts if appointments[row[0]][1] == j),
                sum(row[3] for row in costs if row[1] == j),
            ]
        )
    activity, returning, heat, monthly_finance = [], [], [], []
    for key in months:
        booked = [appointments[i] for i in selected if appointments[i][2].startswith(key)]
        ids = [i for i in completed if appointments[i][2].startswith(key)]
        seen = {appointments[i][0] for i in ids}
        activity.append([sum(row[4] == status for row in booked) for status in [0, 2, 1]])
        returning.append(
            [
                sum(patients[p][2].startswith(key) for p in seen),
                sum(patients[p][2][:7] < key for p in seen),
            ]
        )
        capacity = []
        for weekday in range(5):
            available = sum(
                row[2]
                for row in availability
                if row[0].startswith(key) and date.fromisoformat(row[0]).weekday() == weekday
            )
            reserved = sum(
                row[6] for row in booked if date.fromisoformat(row[2]).weekday() == weekday
            )
            capacity.append(reserved / available if available else None)
        heat.append(capacity)
        rev = sum(net[i] for i in ids)
        expense = sum(row[3] for row in costs if row[0].startswith(key))
        monthly_finance.append([rev, expense, rev - expense])
    weeks = {}
    for day in dates:
        key = week_start(day)
        if key not in weeks:
            weeks[key] = {"week": key, "revenue": 0, "cost": 0, "receipts": 0, "days": 0}
        weeks[key]["days"] += 1
    for i in completed:
        weeks[week_start(appointments[i][2])]["revenue"] += net[i]
    for row in costs:
        weeks[week_start(row[0])]["cost"] += row[3]
    for row in receipts:
        weeks[week_start(row[1])]["receipts"] += row[2]
    return {
        "dates": dates,
        "first": first,
        "cutoff": cutoff,
        "monthly": months,
        "people": len(people),
        "completed": len(completed),
        "new": new,
        "ageSum": sum(ages),
        "ageRows": age_rows,
        "categories": category_totals(data, completed_set),
        "branchPeople": branch_people,
        "selected": len(selected),
        "missed": sum(appointments[i][4] == 2 for i in selected),
        "cancelled": sum(appointments[i][4] == 1 for i in selected),
        "late": sum(bool(appointments[i][7]) for i in selected),
        "capacity": sum(row[2] for row in availability),
        "careMinutes": sum(appointments[i][5] for i in completed),
        "overdue": recall_counts[(cutoff[:7], location)],
        "activity": activity,
        "returning": returning,
        "heat": heat,
        "recall": [recall_counts[(key, location)] for key in months],
        "revenue": revenue,
        "received": received,
        "cost": cost,
        "paidVisits": paid_visits,
        "cashPaid": cash_paid,
        "risk": risk,
        "financial": financial,
        "aging": aging,
        "monthlyFinance": monthly_finance,
        "branchFinance": branch_finance,
        "weeks": list(weeks.values()),
        "byCost": [
            sum(row[3] for row in costs if row[2] == j) for j in range(len(data["costNames"]))
        ],
    }


def aggregate_viewer(data):
    """I replace row-level exports with summaries for all 156 filter combinations."""
    calendar = sorted({row[0] for row in data["costs"]})
    net = [0] * len(data["appointments"])
    for visit, _, amount in data["treatments"]:
        net[visit] += amount
    month_ends = {day[:7]: day for day in calendar}
    locations = ["all", 0, 1, 2]
    recall_counts = {
        (month, location): overdue_count(data, cutoff, location)
        for month, cutoff in month_ends.items()
        for location in locations
    }
    snapshots = {}
    for year in ["all", "2024", "2025"]:
        for month in ["all"] + [f"{number:02}" for number in range(1, 13)]:
            for location in locations:
                key = f"{year}|{month}|{location}"
                snapshots[key] = selection_summary(
                    data, year, month, location, calendar, net, recall_counts
                )
    result = {
        key: data[key]
        for key in [
            "locations",
            "locationIds",
            "categories",
            "images",
            "costNames",
            "financialPolicy",
        ]
    }
    result["snapshots"] = snapshots
    return result
