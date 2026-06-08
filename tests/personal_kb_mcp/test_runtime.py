from pathlib import Path

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime


def test_runtime은_같은_vault에_대해_하나의_write_queue를_재사용한다(tmp_path: Path) -> None:
    # Given: 같은 vault path를 가리키는 settings가 있다.
    settings = Settings(vault_path=tmp_path / "vault")

    # When: runtime을 두 번 생성한다.
    first = create_runtime(settings)
    second = create_runtime(settings)

    # Then: 두 writer는 같은 process-local write queue를 공유한다.
    assert first.write_queue is second.write_queue
    assert first.write_service.queue is first.write_queue
    assert second.write_service.queue is first.write_queue
