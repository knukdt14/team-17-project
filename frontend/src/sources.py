"""
sources.py
- RAG 답변의 근거가 된 출처(조항)를, 답변과 분리된 별도 말풍선이 아니라 같은 말풍선 안에
  답변 바로 아래 작은 주석 글씨로 붙인다. 누르면 팝오버로 원문을 띄운다.
- model이 아직 sources 필드를 안 내려줘도(또는 빈 리스트여도) 에러 없이 조용히 아무것도 표시하지 않는다.
- model은 검색 결과 중 실제 답변과 가장 겹치는(=답변에 가장 큰 영향을 준) 문서 1개만 sources로 보낸다.
"""

import re

from nicegui import ui

from theme import MUTED

# 청크 본문 맨 앞의 "제15조(제목)" / "제15조의2(제목)" 표기를 뽑아내는 패턴.
# model이 별도 article 필드를 안 내려줘도, 본문(text)만 있으면 여기서 조 번호를 뽑아 라벨로 쓴다.
ARTICLE_PATTERN = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*\([^)]{0,40}\)")


def extract_article_label(text: str):
    if not text:
        return None
    match = ARTICLE_PATTERN.search(text)
    return match.group(0) if match else None


def render_sources(sources):
    """답변에 가장 큰 영향을 준 근거 조항 1건을, 답변 밑에 작은 주석 텍스트로 붙인다.
    라벨은 "제O조(제목)"을 우선 쓰고(본문에서 자동 추출), 없으면 파일명으로 대체한다.
    """
    if not sources:
        return

    src = sources[0]
    filename = src.get("filename") or src.get("source") or "알 수 없는 문서"
    page = src.get("page") or src.get("page_num")
    text = src.get("text") or src.get("snippet") or ""
    article = src.get("article") or extract_article_label(text)

    label = f"📄 관련: {article or filename}"
    meta = filename + (f" · {page}페이지" if page else "")

    with ui.button(label).props("flat dense no-caps unelevated").classes(
        "text-xs normal-case px-0 mt-1 min-h-0"
    ).style(f"color:{MUTED}; border-bottom: 1px dashed {MUTED};"):
        with ui.menu().classes("p-3 max-w-sm"):
            ui.label(meta).classes("text-xs text-gray-500 mb-1")
            ui.markdown(text if text else "_본문 미리보기가 제공되지 않았습니다._").classes("text-sm")
