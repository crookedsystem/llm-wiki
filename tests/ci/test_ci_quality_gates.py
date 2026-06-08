from pathlib import Path


def _project_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise RuntimeError("project root not found")


PROJECT_ROOT = _project_root()
CI_WORKFLOW = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


def test_ci는_커버리지_요약을_pr에_댓글로_게시한다() -> None:
    # Given: PR에서 실행되는 CI workflow가 있다.
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")

    # When: coverage 결과를 PR에 노출하는 설정을 확인한다.
    required_fragments = [
        "pull-requests: write",
        "issues: write",
        "coverage-summary.md",
        "actions/github-script@v7",
        "personal-kb-mcp-coverage",
    ]

    # Then: PR comment를 작성하거나 갱신할 수 있는 설정과 sticky comment marker가 있어야 한다.
    for fragment in required_fragments:
        assert fragment in workflow


def test_ci는_mypy와_커버리지_80퍼센트_게이트를_강제한다() -> None:
    # Given: CI workflow와 coverage 설정이 있다.
    workflow = CI_WORKFLOW.read_text(encoding="utf-8")
    pyproject = PYPROJECT.read_text(encoding="utf-8")

    # When: merge gate로 사용할 타입 검사와 테스트 커버리지 기준을 확인한다.
    required_fragments = [
        "uv run mypy src tests",
        "--cov=personal_kb_mcp",
        "--cov-fail-under=80",
        "--cov-report=term-missing",
        "--cov-report=json:coverage.json",
    ]

    # Then: mypy 실패나 80% 미만 coverage는 CI 실패로 이어져야 한다.
    for fragment in required_fragments:
        assert fragment in workflow
    assert "fail_under = 80" in pyproject
