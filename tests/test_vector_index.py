import asyncio

from personal_kb_mcp.domain.vector_index import IndexedNote, NullVectorIndex, VectorSearchResult


def test_null_vector_index는_index와_delete를_받아도_검색결과를_반환하지_않는다() -> None:
    async def exercise_index() -> None:
        # Given: 벡터 기능이 비활성화된 NullVectorIndex와 indexed note가 있다.
        index = NullVectorIndex()
        note = IndexedNote(path="daily/today.md", content="Body", content_hash="abc")

        # When: note를 upsert하고 검색한 뒤 delete한다.
        await index.upsert(note)
        results = await index.search("Body", limit=5)
        await index.delete("daily/today.md")

        # Then: null adapter는 외부 index 없이 빈 검색 결과를 반환한다.
        assert results == []

    asyncio.run(exercise_index())


def test_vector_search_result는_경로와_score와_content_hash_shape를_유지한다() -> None:
    # Given: 검색 결과에 필요한 path, score, content_hash가 있다.
    result = VectorSearchResult(path="daily/today.md", score=0.5, content_hash="abc")

    # When: dataclass field 값을 조회한다.
    observed_result = {
        "path": result.path,
        "score": result.score,
        "content_hash": result.content_hash,
    }

    # Then: vector search result shape가 안정적으로 유지된다.
    assert observed_result == {
        "path": "daily/today.md",
        "score": 0.5,
        "content_hash": "abc",
    }
