# Start here

1. Open the [live dashboard](https://ekhodada.github.io/dental-clinic-analytics/) or double-click `index.html`.
2. Read [the three business answers](BUSINESS_QUESTIONS.md).
3. Use [the metric guide](DASHBOARD_GUIDE.md) for definitions and [the financial guide](FINANCIAL_MODEL.md) for profit versus cash.

## Update the data

Replace `raw/` with a complete snapshot using the same columns and stable IDs. Run both commands:

```bash
python3 code/clean_and_refresh.py
python3 code/build_dashboard_data.py
```

The Mac and Windows refresh runners execute both steps. Inspect the saved checks before committing and pushing updated reports and dashboard data. GitHub Pages publishes from the main branch.

## Change something

- Labels and charts: `dashboard/`.
- Source definitions: `column_guide.csv` and `settings.json`.
- Financial scenario assumptions: `financial_policy.json`.
- Reporting calculations: `code/reports.sql` and `code/financial_model.py`.

These records are synthetic. Main operating profit is before estimated collection losses; the optional scenario must remain separate.
