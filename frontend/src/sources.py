"""
sources.py
- RAG 답변의 근거가 된 출처(조항)를 작은 버튼 하나로 보여주고, 누르면 팝오버로 원문을 띄운다.
- model이 아직 sources 필드를 안 내려줘도(또는 빈 리스트여도) 에러 없이 조용히 아무것도 표시하지 않는다.
- model은 검색 결과 중 가장 순위가 높은(=답변에 가장 큰 영향을 준) 문서 1개만 sources로 보낸다.
"""

import re

import streamlit as st

# 청크 본문 맨 앞의 "제15조(제목)" / "제15조의2(제목)" 표기를 뽑아내는 패턴.
# model이 별도 article 필드를 안 내려줘도, 본문(text)만 있으면 여기서 조 번호를 뽑아 버튼 라벨로 쓴다.
ARTICLE_PATTERN = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*\([^)]{0,40}\)")


def extract_article_label(text: str):
    if not text:
        return None
    match = ARTICLE_PATTERN.search(text)
    return match.group(0) if match else None


def render_sources(sources):
    """답변에 가장 큰 영향을 준 근거 조항 1건을 작은 팝오버 버튼으로 보여준다.
    버튼 라벨은 "제O조(제목)"을 우선 쓰고(본문에서 자동 추출), 없으면 파일명으로 대체한다.
    누르면 팝오버가 떠서 해당 조항 원문을 바로 확인할 수 있다.
    """
    if not sources:
        return

    src = sources[0]
    filename = src.get("filename") or src.get("source") or "알 수 없는 문서"
    page = src.get("page") or src.get("page_num")
    text = src.get("text") or src.get("snippet") or ""
    article = src.get("article") or extract_article_label(text)

    label = f"📎 {article or filename}"
    meta = filename + (f" · {page}페이지" if page else "")

    with st.popover(label, use_container_width=False):
        st.caption(meta)
        st.markdown(text if text else "_본문 미리보기가 제공되지 않았습니다._")
