// I draw financial headline cards with the same-period comparison.
function financeMetrics(s) {
  const comparison = comparisonText(s);
  const charges = s.revenue,
    received = s.received,
    cost = s.cost,
    profit = charges - cost,
    paidForVisits = s.paidVisits;
  $("metrics").innerHTML =
    metric(
      "Net service revenue",
      money(charges),
      comparison.revenue || "After discounts; before operating costs",
    ) +
    metric(
      "Money received",
      money(received),
      "Receipts dated in selected period",
    ) +
    metric(
      "Operating costs",
      money(cost),
      "Recorded costs allocated to this period",
    ) +
    metric(
      "Operating profit",
      money(profit),
      (comparison.profit || "Revenue minus operating costs") +
        " · before loss estimates",
    ) +
    metric(
      "Operating margin",
      pct(profit / charges),
      "Before estimated collection losses",
    ) +
    metric(
      "Unpaid at period end",
      money(charges - paidForVisits),
      "Selected visits · gross balance at " + s.cutoff,
    );
}

// I draw receipts, cash payments and their difference.
function cashPanel(s) {
  const received = s.received,
    cashPaid = s.cashPaid;
  return panel(
    "Cash collected and paid",
    "Payment dates in the selected period · modeled operations only",
    table(
      ["Money received", "Operating payments", "Operating cash surplus"],
      [[money(received), money(cashPaid), money(received - cashPaid)]],
    ) +
      '<p class="notice">Cash surplus is separate from profit. It excludes equipment purchases, loans, income tax and owner withdrawals; it is not the bank balance or owner take-home pay. Depreciation and loss provisions are not cash payments.</p>',
    "full",
  );
}

// I draw the separate collection-loss scenario and aged balances.
function collectionRiskPanel(s) {
  const charges = s.revenue,
    profit = s.revenue - s.cost;
  const financialSum = (key) => s.financial[key];
  const aging = D.financialPolicy.age_bands.map((b, i) => [
    b.label,
    money(s.aging[i]),
    pct(b.loss_rate),
  ]);
  const riskExpense = s.risk;
  const balancePanel =
    '<details class="panel full"><summary><strong>Collection-risk scenario · optional</strong></summary><p class="sub">What if part of the unpaid bills cannot be collected? These are assumptions, not recorded losses.</p>' +
    table(
      ["Assumed loss expense", "Scenario profit", "Scenario margin"],
      [
        [
          money(riskExpense),
          money(profit - riskExpense),
          pct((profit - riskExpense) / charges),
        ],
      ],
    ) +
    '<p class="sub">All tracked visits up to ' +
    s.cutoff +
    " · selected locations, including earlier visits</p>" +
    table(
      [
        "Total unpaid",
        "Assumed loss allowance",
        "Scenario collectible balance",
      ],
      [
        [
          money(financialSum("Gross Receivables")),
          money(financialSum("Scenario Loss Allowance")),
          money(financialSum("Scenario Net Receivables")),
        ],
      ],
    ) +
    table(
      ["Age since treatment", "Unpaid balance", "Assumed loss rate"],
      aging,
    ) +
    '<p class="notice">The main profit uses recorded operating costs, before estimated collection losses. This separate scenario deducts the change in an assumed loss allowance. It does not change receipts or cancel bills. Age alone does not prove a bill is overdue. Records end on 2025-12-31.</p></details>';
  return balancePanel;
}

// I download every selected week as a CSV file.
function downloadWeekly() {
  const h = Object.keys(latestExport[0] || {}),
    csv = [
      h.join(","),
      ...latestExport.map((r) => h.map((k) => r[k]).join(",")),
    ].join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "dental-clinic-weekly-report.csv";
  a.click();
  URL.revokeObjectURL(url);
}
// I draw distinct patients by age and recorded gender.
function ageChart(ageRows) {
  const max = Math.max(1, ...ageRows.flatMap((r) => r.values)),
    w = 620,
    h = 235;
  let svg = `<svg class="chart" viewBox="0 0 ${w} ${h}" role="img" aria-label="Distinct patients by age group and recorded gender">`;
  ageRows.forEach((r, i) => {
    r.values.forEach((v, j) => {
      const height = (v / max) * 165;
      svg += `<rect x="${50 + i * 115 + j * 22}" y="${185 - height}" width="19" height="${height}" rx="3" fill="${colors[j]}"><title>${r.label} · ${["Female", "Male", "Other / not recorded"][j]}: ${fmt(v)}</title></rect>`;
    });
    svg += `<text x="${82 + i * 115}" y="210" text-anchor="middle" fill="#80768b" font-size="12">${r.label}</text>`;
  });
  return svg + "</svg>" + legend(["Female", "Male", "Other / not recorded"]);
}

/* I draw the reporting pages from precomputed summaries. */
const D = window.CLINIC_DATA;
// I find one page element by its identifier.
function $(id) {
  return document.getElementById(id);
}
// I add a list of numeric values.
function sum(values) {
  return values.reduce((total, value) => total + value, 0);
}
// I format a whole-number count for display.
function fmt(value) {
  return Math.round(value).toLocaleString("en-CA");
}
// I display integer cents as rounded Canadian dollars.
function money(value) {
  return (value / 100).toLocaleString("en-CA", {
    style: "currency",
    currency: "CAD",
    maximumFractionDigits: 0,
  });
}
// I display a ratio as a percentage or a blank marker.
function pct(value) {
  return Number.isFinite(value) ? (value * 100).toFixed(1) + "%" : "—";
}
// I escape text before inserting it into the page.
function esc(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
}
const months = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];
const colors = ["#7141bc", "#b5a3ed", "#d6cbe8", "#da8ca4"];
const shortCats = [
  "Routine & preventive",
  "Repair & restoration",
  "Gum care",
  "Root canal care",
  "Surgery & replacement",
  "Alignment & other care",
];
const categoryDescriptions = [
  "Check-ups, preventive cleaning and diagnostic services.",
  "Fillings, crowns and other services that restore teeth.",
  "Periodontal maintenance and gum assessments.",
  "Services treating the tooth pulp and root canals.",
  "Extractions, replacement-related care and denture adjustments.",
  "Aligner reviews, night guards and other related care.",
];
let page = "overview",
  category = 0,
  latestExport = [];
months.forEach((m, i) =>
  $("month").add(new Option(m, String(i + 1).padStart(2, "0"))),
);
D.locations.forEach((l, i) =>
  $("location").add(new Option(l[0] + " · " + l[1], String(i))),
);
// I draw one headline measure and its definition.
function metric(label, value, note) {
  return `<div class="metric"><div class="label">${label}</div><strong>${value}</strong><small>${note}</small></div>`;
}
// I wrap a chart or table in a titled panel.
function panel(title, sub, body, extra = "") {
  return `<section class="panel ${extra}"><h2>${title}</h2><p class="sub">${sub}</p>${body}</section>`;
}
// I label the colours used in a chart.
function legend(names) {
  return (
    '<div class="legend">' +
    names
      .map(
        (n, i) =>
          `<span><i class="dot" style="background:${colors[i % colors.length]}"></i>${esc(n)}</span>`,
      )
      .join("") +
    "</div>"
  );
}
// I draw monthly lines with selectable month points.
function chart(rows, names, { currency = false, click = false } = {}) {
  if (!rows.length)
    return '<div class="empty">No records in this period.</div>';
  const w = 650,
    h = 270,
    left = 65,
    right = 20,
    top = 20,
    bottom = 45,
    iw = w - left - right,
    ih = h - top - bottom;
  const all = rows.flatMap((r) => r.values),
    lo = Math.min(0, ...all),
    hi = Math.max(1, ...all),
    range = hi - lo;
  const x = (i) =>
      left + (rows.length === 1 ? iw / 2 : (i * iw) / (rows.length - 1)),
    y = (v) => top + ((hi - v) / range) * ih;
  let s = `<svg viewBox="0 0 ${w} ${h}" class="chart" role="img" aria-label="${esc(names.join(", "))} over the selected months">`;
  for (let j = 0; j <= 4; j++) {
    const v = lo + (range * j) / 4,
      yy = y(v);
    s += `<line x1="${left}" x2="${w - right}" y1="${yy}" y2="${yy}" stroke="#eee9f4"/><text x="${left - 9}" y="${yy + 4}" text-anchor="end" fill="#80768b" font-size="10">${currency ? money(v) : fmt(v)}</text>`;
  }
  names.forEach((name, j) => {
    s += `<polyline points="${rows.map((r, i) => x(i) + "," + y(r.values[j])).join(" ")}" fill="none" stroke="${colors[j]}" stroke-width="2.5"/>`;
    rows.forEach(
      (r, i) =>
        (s += `<circle cx="${x(i)}" cy="${y(r.values[j])}" r="4" fill="${colors[j]}" ${click ? 'class="clickable" tabindex="0" role="button" data-month="' + r.key + '" aria-label="Filter ' + r.key + '"' : ""}><title>${esc(r.label)} · ${esc(name)}: ${currency ? money(r.values[j]) : fmt(r.values[j])}</title></circle>`),
    );
  });
  const every = Math.max(1, Math.ceil(rows.length / 9));
  rows.forEach((r, i) => {
    if (i % every === 0 || i === rows.length - 1)
      s += `<text x="${x(i)}" y="${h - 15}" text-anchor="middle" fill="#80768b" font-size="10">${esc(r.label)}</text>`;
  });
  return s + "</svg>" + legend(names);
}
// I draw proportional horizontal bars.
function bars(rows, { currency = false } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return rows
    .map(
      (r) =>
        `<div class="bar-row"><span>${esc(r.label)}</span><div class="bar-track"><div class="bar-fill" style="width:${(100 * r.value) / max}%"></div></div><span class="value">${currency ? money(r.value) : fmt(r.value)}</span></div>`,
    )
    .join("");
}
// I draw a scrollable table from headers and rows.
function table(headers, rows) {
  return (
    '<div class="table-scroll"><table><thead><tr>' +
    headers
      .map((x, i) => `<th class="${i ? "num" : ""}">${esc(x)}</th>`)
      .join("") +
    "</tr></thead><tbody>" +
    rows
      .map(
        (row) =>
          "<tr>" +
          row
            .map((x, i) => `<td class="${i ? "num" : ""}">${x}</td>`)
            .join("") +
          "</tr>",
      )
      .join("") +
    "</tbody></table></div>"
  );
}
// I format a month key for display.
function periodLabel(m) {
  return months[Number(m.slice(5, 7)) - 1] + " " + m.slice(2, 4);
}
// I read the aggregate summary for the selected filters.
function getState() {
  return D.snapshots[
    [$("year").value, $("month").value, $("location").value].join("|")
  ];
}
// I draw the patient overview page.
function overview(s) {
  const noShows = s.missed,
    newPatients = s.new;
  const ages = { length: s.people };
  $("metrics").innerHTML =
    metric(
      "Unique patients seen",
      fmt(s.people),
      "Distinct people with completed visits",
    ) +
    metric(
      "Completed visits",
      fmt(s.completed),
      "One person may have several visits",
    ) +
    metric(
      "New patients seen",
      fmt(newPatients),
      "First-ever visit in selected period",
    ) +
    metric(
      "Returning patients seen",
      fmt(s.people - newPatients),
      "First attended before this period",
    ) +
    metric(
      "Attendance rate",
      pct(s.completed / (s.completed + noShows)),
      "Completed ÷ completed + no-show",
    ) +
    metric(
      "Average patient age",
      ages.length ? (s.ageSum / s.people).toFixed(1) : "—",
      "Approximate years · each person once",
    );
  const ageRows = [
    ["0–17", 0, 17],
    ["18–34", 18, 34],
    ["35–49", 35, 49],
    ["50–64", 50, 64],
    ["65+", 65, 150],
  ].map(([label, min, max]) => ({ label, values: [0, 0, 0], min, max }));
  ageRows.forEach((row, i) => {
    row.values = s.ageRows[i];
  });
  const cats = s.categories.map((row, i) => ({
    label: shortCats[i],
    value: row[0],
  }));
  const byLoc = s.branchPeople.map(([j, people, visits, newPeople]) => [
    esc(D.locations[j][0]),
    fmt(people),
    fmt(visits),
    fmt(newPeople),
  ]);
  $("content").innerHTML =
    '<div class="grid">' +
    panel(
      "Patient age & recorded gender",
      "Distinct patients · age at first selected completed visit",
      ageChart(ageRows),
    ) +
    panel(
      "Explore dental care",
      "Category measures apply to completed services in this period",
      '<div id="care-panel"></div>',
    ) +
    panel(
      "Patients treated by care category",
      "Patients may appear in more than one category.",
      bars(cats),
    ) +
    panel(
      "Compare locations",
      "Group patient totals are deduplicated; branch counts are not additive.",
      table(
        ["Location", "Patients seen", "Completed visits", "New patients"],
        byLoc,
      ),
    ) +
    "</div>";
  renderCategory(s);
}
// I draw the selected care category and its totals.
function renderCategory(s) {
  const [people, services, charges] = s.categories[category];
  $("care-panel").innerHTML =
    `<div class="care"><img src="images/${D.images[category]}" alt="Illustrative dental model for ${esc(D.categories[category])}"><div class="care-info"><label>Care category<select id="category">${D.categories.map((c, i) => `<option value="${i}" ${i === category ? "selected" : ""}>${esc(c)}</option>`).join("")}</select></label><p>${categoryDescriptions[category]}</p><div class="care-numbers"><div><strong>${fmt(people)}</strong><span>Patients treated</span></div><div><strong>${fmt(services)}</strong><span>Services completed</span></div><div><strong>${money(charges)}</strong><span>Net service charges</span></div></div></div></div>`;
  $("category").addEventListener("change", (e) => {
    category = Number(e.target.value);
    renderCategory(s);
  });
}
// I draw appointment, capacity and recall trends.
function trends(s) {
  const comparison = comparisonText(s);
  const cancelled = s.cancelled,
    missed = s.missed,
    late = s.late,
    capacity = s.capacity,
    overdue = s.overdue;
  $("metrics").innerHTML =
    metric("Scheduled appointments", fmt(s.selected), "All booking outcomes") +
    metric(
      "Completed visits",
      fmt(s.completed),
      comparison.visits || "Care delivered",
    ) +
    metric(
      "Missed appointments",
      fmt(missed),
      pct(missed / (s.completed + missed)) + " of completed + missed",
    ) +
    metric(
      "Cancelled appointments",
      fmt(cancelled),
      fmt(late) + " with less than 24h notice",
    ) +
    metric(
      "Actual care utilization",
      pct(s.careMinutes / capacity),
      "Treatment minutes ÷ available minutes",
    ) +
    metric(
      "Overdue recall patients",
      fmt(overdue),
      "Latest plan · as of " + s.cutoff,
    );
  const activity = s.monthly.map((m, i) => ({
    key: m,
    label: periodLabel(m),
    values: s.activity[i],
  }));
  const ret = s.monthly.map((m, i) => ({
    key: m,
    label: periodLabel(m),
    values: s.returning[i],
  }));
  const heat = s.monthly
    .map((m, i) => {
      const cells = s.heat[i].map(
        (ratio) =>
          `<td style="background:rgba(113,65,188,${ratio === null ? 0 : Math.min(0.65, ratio * 0.65)})" title="Reserved time includes cancelled bookings and turnover">${ratio === null ? "—" : pct(ratio)}</td>`,
      );
      return "<tr><td>" + periodLabel(m) + "</td>" + cells.join("") + "</tr>";
    })
    .join("");
  const heatTable =
    '<div class="table-scroll"><table class="heat"><thead><tr>' +
    ["Month", "Mon", "Tue", "Wed", "Thu", "Fri"]
      .map((x) => "<th>" + x + "</th>")
      .join("") +
    "</tr></thead><tbody>" +
    heat +
    "</tbody></table></div>";
  const recallRows = s.monthly.map((m, i) => ({
    label: periodLabel(m),
    key: m,
    values: [s.recall[i]],
  }));
  $("content").innerHTML =
    '<div class="grid">' +
    panel(
      "Appointment activity over time",
      "Counts · select a point to focus on its month",
      chart(activity, ["Completed", "No-show", "Cancelled"], { click: true }),
    ) +
    panel(
      "New and returning patients",
      "Monthly distinct patients · not additive across months",
      chart(ret, ["New", "Returning"], { click: true }),
    ) +
    panel(
      "Booked capacity by weekday",
      "Reserved minutes ÷ available minutes · includes turnover and cancellations",
      heatTable,
    ) +
    panel(
      "Overdue follow-ups",
      "Monthly snapshot · overdue does not mean the patient has left",
      chart(recallRows, ["Overdue patients"], { click: true }),
    ) +
    "</div>";
}
// I draw revenue, costs, profit and cash measures.
function finance(s) {
  financeMetrics(s);
  const cat = s.categories.map((row, i) => ({
    label: shortCats[i],
    value: row[2],
  }));
  const byCost = D.costNames
    .map((label, i) => ({ label, value: s.byCost[i] }))
    .filter((x) => x.value)
    .sort((a, b) => b.value - a.value);
  const monthly = s.monthly.map((m, i) => ({
    key: m,
    label: periodLabel(m),
    values: s.monthlyFinance[i],
  }));
  const rows = s.branchFinance.map(([j, rev, cash, co]) => [
    esc(D.locations[j][0]),
    money(rev),
    money(cash),
    money(co),
    money(rev - co),
    pct((rev - co) / rev),
  ]);
  const weekly = s.weeks;
  latestExport = weekly.map((x) => ({
    "Week Starting": x.week,
    "Days Included": x.days,
    "Service Revenue": (x.revenue / 100).toFixed(2),
    "Money Received": (x.receipts / 100).toFixed(2),
    "Operating Costs": (x.cost / 100).toFixed(2),
    "Operating Profit": ((x.revenue - x.cost) / 100).toFixed(2),
  }));
  const weekRows = weekly
    .slice(-12)
    .map((x) => [
      x.week + (x.days < 7 ? " *" : ""),
      money(x.revenue),
      money(x.receipts),
      money(x.cost),
      money(x.revenue - x.cost),
    ]);
  $("content").innerHTML =
    '<div class="grid">' +
    panel(
      "Revenue by care category",
      "Service mix explains revenue differences; it does not establish profitability.",
      bars(cat, { currency: true }),
    ) +
    panel(
      "Revenue, costs & operating profit",
      "Monthly values · before estimated collection losses",
      chart(monthly, ["Revenue", "Costs", "Profit"], {
        currency: true,
        click: true,
      }),
    ) +
    panel(
      "Compare branch finances",
      "Before estimated collection losses · shared administration split equally",
      table(
        ["Location", "Revenue", "Receipts", "Costs", "Profit", "Margin"],
        rows,
      ),
      "full",
    ) +
    cashPanel(s) +
    panel(
      "Operating cost breakdown",
      "Recorded costs recognized in the selected period",
      bars(byCost, { currency: true }),
    ) +
    panel(
      "Weekly management report",
      "Latest 12 selected weeks · * means partial week",
      `<div class="panel-head"><p class="notice">CAD · all selected locations combined</p><button id="download">Download all weeks</button></div>` +
        table(
          ["Week starting", "Revenue", "Receipts", "Costs", "Profit"],
          weekRows,
        ) +
        '<p class="notice">Profit is before estimated collection losses, income tax and financing costs. Unpaid charges are already included in revenue; do not add them to profit again. Profit is not cash flow or owner take-home pay.</p>',
    ) +
    collectionRiskPanel(s) +
    "</div>";
  $("download").addEventListener("click", downloadWeekly);
}
// I refresh the selected page and attach month filters.
function render() {
  const s = getState();
  $("period").textContent = s.dates.length
    ? s.first + " → " + s.cutoff
    : "No dates in this selection";
  const titles = {
    overview: [
      "Patient Overview",
      "Who visits our clinics, and which services do they use?",
    ],
    trends: [
      "Key Trends",
      "What is changing, and where should we investigate?",
    ],
    finance: [
      "Treatment & Costs",
      "What did we earn, receive and spend in the selected period?",
    ],
  };
  [$("title").textContent, $("subtitle").textContent] = titles[page];
  if (!s.dates.length) {
    $("metrics").innerHTML = "";
    $("content").innerHTML =
      '<div class="panel empty">No data for this period. Choose another year or month.</div>';
    return;
  }
  ({ overview, trends, finance })[page](s);
  document.querySelectorAll("[data-month]").forEach((el) => {
    // I filter the report to the month selected on the chart.
    function go() {
      const m = el.dataset.month;
      $("year").value = m.slice(0, 4);
      $("month").value = m.slice(5, 7);
      render();
    }
    el.addEventListener("click", go);
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        go();
      }
    });
  });
}
// I compare the same selected period with the previous year.
function comparisonText(s) {
  const year = $("year").value,
    month = $("month").value;
  if (year === "all") return {};
  const previous =
    D.snapshots[
      [String(Number(year) - 1), month, $("location").value].join("|")
    ];
  if (!previous)
    return {
      visits: "No earlier-year data",
      revenue: "No earlier-year data",
      profit: "No earlier-year data",
    };
  const prev = String(Number(year) - 1),
    label = month === "all" ? prev : months[Number(month) - 1] + " " + prev;
  const revenue = s.revenue,
    oldRevenue = previous.revenue;
  const profit = revenue - s.cost,
    oldProfit = oldRevenue - previous.cost;
  const change = (now, before, down, up) =>
    before > 0
      ? now === before
        ? "No change from " + label
        : ((Math.abs(now - before) / before) * 100).toFixed(1) +
          "% " +
          (now < before ? down : up) +
          " than " +
          label
      : "No comparison available";
  const delta = profit - oldProfit;
  return {
    visits: change(s.completed, previous.completed, "fewer", "more"),
    revenue: change(revenue, oldRevenue, "lower", "higher"),
    profit:
      delta === 0
        ? "No change from " + label
        : money(Math.abs(delta)) +
          " " +
          (delta < 0 ? "less" : "more") +
          " than " +
          label,
  };
}
document.querySelectorAll(".tab").forEach((b) =>
  b.addEventListener("click", () => {
    page = b.dataset.page;
    document.querySelectorAll(".tab").forEach((x) => {
      x.classList.toggle("active", x === b);
      if (x === b) x.setAttribute("aria-current", "page");
      else x.removeAttribute("aria-current");
    });
    render();
  }),
);
["year", "month", "location"].forEach((id) =>
  $(id).addEventListener("change", render),
);
$("reset").addEventListener("click", () => {
  ["year", "month", "location"].forEach((id) => ($(id).value = "all"));
  category = 0;
  render();
});
render();
