from pathlib import Path

from personal_kb_mcp.config import Settings
from personal_kb_mcp.runtime import create_runtime


def test_runtime_reuses_one_write_queue_for_same_vault(tmp_path: Path) -> None:
    settings = Settings(vault_path=tmp_path / "vault")

    first = create_runtime(settings)
    second = create_runtime(settings)

    assert first.write_queue is second.write_queue
    assert first.writer.queue is first.write_queue
    assert second.writer.queue is first.write_queue
