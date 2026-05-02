import json
from datetime import datetime
from pathlib import Path


def save_report(results):
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = reports_dir / f"test_report_{timestamp}.json"

    report = {
        "project": "Hardware Validation Automation Lab",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "total_tests": len(results),
        "passed": sum(1 for test in results if test["result"] == "PASS"),
        "failed": sum(1 for test in results if test["result"] == "FAIL"),
        "results": results
    }

    with open(file_path, "w", encoding="utf-8") as file:
        json.dump(report, file, indent=4)

    return file_path