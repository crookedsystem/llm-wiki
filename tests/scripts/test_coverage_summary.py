import json
import subprocess
import sys
from pathlib import Path


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("project root not found")


PROJECT_ROOT = _project_root()
SUMMARY_SCRIPT = PROJECT_ROOT / "scripts" / "coverage_summary.py"


def test_커버리지_요약_스크립트는_총_커버리지와_하위_파일을_markdown으로_출력한다(
    tmp_path: Path,
) -> None:
    # Given: coverage.py JSON 형식의 최소 커버리지 결과가 있다.
    coverage_json = tmp_path / "coverage.json"
    coverage_json.write_text(
        json.dumps(
            {
                "totals": {
                    "percent_covered": 96.93,
                    "covered_lines": 376,
                    "num_statements": 384,
                    "covered_branches": 35,
                    "num_branches": 40,
                },
                "files": {
                    "src/personal_kb_mcp/main.py": {
                        "summary": {"percent_covered": 80.0, "missing_lines": 1}
                    },
                    "src/personal_kb_mcp/config.py": {
                        "summary": {"percent_covered": 100.0, "missing_lines": 0}
                    },
                },
            }
        ),
        encoding="utf-8",
    )

    # When: PR 댓글용 coverage summary를 생성한다.
    completed = subprocess.run(
        [sys.executable, str(SUMMARY_SCRIPT), str(coverage_json)],
        check=True,
        capture_output=True,
        text=True,
    )

    # Then: 총 coverage, 80% 기준, 가장 낮은 파일이 Markdown으로 드러난다.
    assert "## 테스트 커버리지" in completed.stdout
    assert "96.93%" in completed.stdout
    assert "80%" in completed.stdout
    assert "src/personal_kb_mcp/main.py" in completed.stdout
