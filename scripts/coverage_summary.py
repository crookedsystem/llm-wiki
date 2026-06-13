from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

COVERAGE_GATE_PERCENT = 80.0
LOWEST_FILE_LIMIT = 5


def main() -> int:
    coverage_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("coverage.json")
    if not coverage_path.exists():
        print("## 테스트 커버리지")
        print()
        print(
            "coverage.json 파일을 찾지 못했습니다. "
            "타입 검사나 테스트가 coverage report 생성 전에 실패했을 수 있습니다."
        )
        print()
        print("먼저 실패한 CI step 로그를 확인해 주세요.")
        return 0

    data = json.loads(coverage_path.read_text(encoding="utf-8"))
    print(build_summary(data))
    return 0


def build_summary(data: dict[str, Any]) -> str:
    totals = data.get("totals", {})
    total_percent = _float_value(totals.get("percent_covered"))
    covered_lines = _int_value(totals.get("covered_lines"))
    num_statements = _int_value(totals.get("num_statements"))
    covered_branches = _int_value(totals.get("covered_branches"))
    num_branches = _int_value(totals.get("num_branches"))
    status = "✅ 통과" if total_percent >= COVERAGE_GATE_PERCENT else "❌ 실패"

    lines = [
        "## 테스트 커버리지",
        "",
        f"- 기준: **{COVERAGE_GATE_PERCENT:.0f}% 이상**",
        f"- 현재: **{total_percent:.2f}%** — {status}",
        f"- 라인: `{covered_lines}/{num_statements}`",
    ]
    if num_branches:
        lines.append(f"- 브랜치: `{covered_branches}/{num_branches}`")

    lines.extend(
        [
            "",
            "| 낮은 커버리지 파일 | Coverage | Missing lines |",
            "| --- | ---: | ---: |",
        ]
    )
    for file_path, percent, missing_lines in _lowest_files(data):
        lines.append(f"| `{file_path}` | {percent:.2f}% | {missing_lines} |")

    return "\n".join(lines)


def _lowest_files(data: dict[str, Any]) -> list[tuple[str, float, int]]:
    files = data.get("files", {})
    rows: list[tuple[str, float, int]] = []
    for file_path, file_data in files.items():
        if not isinstance(file_data, dict):
            continue
        summary = file_data.get("summary", {})
        percent = _float_value(summary.get("percent_covered"))
        missing_lines = _int_value(summary.get("missing_lines"))
        rows.append((file_path, percent, missing_lines))
    return sorted(rows, key=lambda row: (row[1], row[0]))[:LOWEST_FILE_LIMIT]


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(float(value))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
