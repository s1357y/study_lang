"""LLM 출력 정합성 검증 — 일본어 문자 포함 여부 등 기본 품질 체크.

generate_json() 직후 호출해 불량 결과를 걸러낸다.
통과하면 quality_score=1.0, 실패 항목은 저장하지 않는다.
"""

from __future__ import annotations

import re

from app.llm.schemas import VocabularyOutput

# 히라가나(3040-309F) + 가타카나(30A0-30FF) + CJK 한자(4E00-9FFF)
_JP_PATTERN = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")


def contains_japanese(text: str) -> bool:
    # 최소 한 글자라도 일본어 문자가 있는지 확인
    return bool(_JP_PATTERN.search(text))


def validate_vocabulary_output(item: VocabularyOutput) -> bool:
    # 필수 필드 비어있지 않아야 함
    if not all([item.word.strip(), item.reading.strip(), item.meaning_ko.strip(), item.example_ja.strip()]):
        return False
    # 단어와 예문에 실제 일본어 문자가 있어야 함
    if not contains_japanese(item.word):
        return False
    if not contains_japanese(item.example_ja):
        return False
    return True
