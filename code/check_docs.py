"""I validate the short overview and consolidated method guide after each refresh."""

from pathlib import Path
import json
import re
from .project_docs import render_readme

BASE = Path(__file__).resolve().parents[1]
OLD_GUIDES = [
    "START_HERE.md",
    "PROCESS.md",
    "SAVINGS_ESTIMATE.md",
    "DASHBOARD_GUIDE.md",
    "FINANCIAL_MODEL.md",
    "DATA_NOTES.md",
]
SECTIONS = [
    "Data and tables",
    "Cleaning and checks",
    "Metric definitions",
    "Financial method",
    "Assumptions",
    "How to refresh",
    "File map",
]


# I check the word limit, document links, asset status and current reporting figures.
def main():
    """I check the word limit, document links, asset status and current reporting figures."""
    readme = (BASE / "README.md").read_text()
    details = (BASE / "DETAILS.md").read_text()
    total_words = len((readme + details).split())
    assert total_words < 1000
    assert re.findall(r"^## (.+)$", details, flags=re.MULTILINE) == SECTIONS
    assert not any((BASE / name).exists() for name in OLD_GUIDES)
    assert "**Tools:** Python, SQL, Power BI" in readme
    assert readme.startswith("# Dental Clinic Analytics\n")
    assert (
        "Built on a simulated dataset modelled on a 3-branch dental group (10,000 patients,"
        " 2024-2025)."
        in readme
    )
    section = readme.split("## How I built it")[1].split("**Tools:**")[0]
    assert len(re.findall(r"^- ", section, flags=re.MULTILINE)) == 4
    for path in BASE.glob("*.md"):
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            assert (BASE / target.split("#")[0]).exists(), (path.name, target)
    media = json.loads((BASE / "docs/walkthrough-meta.json").read_text())
    assert 60 <= media["duration_seconds"] <= 120
    assert (BASE / media["path"]).read_bytes()[:6] in (b"GIF89a", b"GIF87a")
    metrics = json.loads((BASE / "processed/business_findings.json").read_text())
    quality = json.loads((BASE / "processed/refresh_log.json").read_text())
    financial = json.loads((BASE / "processed/financial_checks.json").read_text())
    image_path = "docs/images/power-bi-summary.png"
    image = image_path if (BASE / image_path).exists() else None
    assert readme == render_readme(metrics, quality, financial, media, image)
    if image is None:
        assert "I will add its screenshot after I build the report." in readme
    result = {
        "status": "PASS",
        "readme_words": len(readme.split()),
        "details_words": len(details.split()),
        "combined_words": total_words,
        "seven_required_sections": True,
        "six_old_guides_removed": True,
        "local_links_resolve": True,
        "tools_line_exact": True,
        "readme_matches_current_metrics": True,
        "walkthrough_seconds": media["duration_seconds"],
        "power_bi_summary_screenshot": "available" if image else "pending report build",
    }
    (BASE / "processed/documentation_checks.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
