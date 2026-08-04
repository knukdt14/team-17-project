"""
chunker.py
- 문서(source) 단위로 텍스트를 이어붙인 뒤,
  "제○조" / "①②③..." / "1. 2. 3..." 같은 조항·항목 경계에서 나눠서 청킹
  (글자 수로만 자르면 표/항목이 뒤섞여서 검색이 흐려지는 문제 개선)
"""

import re
from dataclasses import dataclass
from typing import List
from itertools import groupby

from loader import PageDoc  # loader.py의 PageDoc 재사용

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150

# 조/항/호 경계 패턴: "제15조(", "제15조의2(", "①"~"⑬", "1. " 같은 표시 앞에서 자름
SPLIT_PATTERN = re.compile(r"(?=\n(?:제\d+조(?:의\d+)?\(|\[표:|[①-⑬]|\d+\.\s))")


@dataclass
class Chunk:
    chunk_id: str
    source: str
    page_num: int
    text: str


def _build_source_text(group: List[PageDoc]):
    """같은 source(파일)의 페이지들을 이어붙이고, 글자 위치 -> page_num 매핑을 만듦"""
    full_text = ""
    char_to_page = []

    for page in group:
        if not page.text:
            continue
        full_text += page.text + "\n"
        char_to_page.extend([page.page_num] * (len(page.text) + 1))

    return full_text, char_to_page


def _split_into_segments(full_text: str) -> List[str]:
    """조항/항목 경계 기준으로 텍스트를 세그먼트로 나눔.
    경계 표시가 하나도 없으면 원문 전체가 세그먼트 1개로 반환됨."""
    segments = SPLIT_PATTERN.split(full_text)
    return [s for s in segments if s.strip()]


def _pack_segments(
    segments: List[str], full_text: str, char_to_page: List[int],
    source: str, chunk_size: int, overlap: int,
) -> List[Chunk]:
    chunks = []
    chunk_counter = 0
    current_text = ""
    current_start_offset = 0
    cursor = 0
    in_table_block = False  # 추가

    def flush(text: str, start_offset: int):
        nonlocal chunk_counter
        if not text.strip():
            return
        page_num = char_to_page[start_offset] if start_offset < len(char_to_page) else char_to_page[-1]
        chunks.append(Chunk(
            chunk_id=f"{source}_c{chunk_counter}",
            source=source, page_num=page_num, text=text.strip(),
        ))
        chunk_counter += 1

    for seg in segments:
        seg_offset = full_text.find(seg, cursor)
        if seg_offset == -1:
            seg_offset = cursor
        cursor = seg_offset + len(seg)

        if seg.lstrip().startswith("[표:"):
            flush(current_text, current_start_offset)
            current_text = seg
            current_start_offset = seg_offset
            in_table_block = True
            continue

        if in_table_block:
            if re.match(r"제\d+조(?:의\d+)?\(", seg.lstrip()):
                flush(current_text, current_start_offset)
                current_text = seg
                current_start_offset = seg_offset
                in_table_block = False
            else:
                current_text += seg
            continue

        if not current_text:
            current_start_offset = seg_offset

        if current_text and len(current_text) + len(seg) > chunk_size:
            flush(current_text, current_start_offset)
            tail = current_text[-overlap:] if overlap > 0 else ""
            current_text = tail + seg
            current_start_offset = seg_offset
        else:
            current_text += seg

    flush(current_text, current_start_offset)
    return chunks


def chunk_pages(pages: List[PageDoc], chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[Chunk]:
    chunks = []

    for source, group in groupby(pages, key=lambda p: p.source):
        group = list(group)
        full_text, char_to_page = _build_source_text(group)
        if not full_text:
            continue

        segments = _split_into_segments(full_text)
        chunks.extend(_pack_segments(segments, full_text, char_to_page, source, chunk_size, overlap))

    return chunks


if __name__ == "__main__":
    from loader import load_pdf

    pages = load_pdf("data/raw/국민내일배움카드 운영규정.pdf")
    chunks = chunk_pages(pages)

    print(f"총 청크 수: {len(chunks)}")
    lengths = [len(c.text) for c in chunks]
    print(f"평균 길이: {sum(lengths)/len(lengths):.0f}자, 최소 {min(lengths)}자, 최대 {max(lengths)}자")

    print("---- 샘플 청크 3개 ----")
    for c in chunks[:3]:
        print(f"[{c.chunk_id}] {c.text[:100]}...")