"""
sources.py
- RAG 답변의 근거가 된 출처(조항)를 클릭해서 펼쳐보는 카드 UI.
- model이 아직 sources 필드를 안 내려줘도 에러 없이 조용히 아무것도 표시하지 않는다.
- model이 sources: [{"filename": ..., "page": ..., "text": ...}] 형태로 내려주기 시작하면
  이 모듈은 수정 없이 바로 동작한다.
"""

import re

import streamlit as st

# 청크 본문 맨 앞의 "제15조(제목)" / "제15조의2(제목)" 표기를 뽑아내는 패턴.
# model이 별도 article 필드를 안 내려줘도, 본문(text)만 있으면 여기서 조 번호를 뽑아 카드 제목으로 쓴다.
ARTICLE_PATTERN = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*\([^)]{0,40}\)")


def extract_article_label(text: str):
    if not text:
        return None
    match = ARTICLE_PATTERN.search(text)
    return match.group(0) if match else None


def render_sources(sources):
    """출처 카드 UI. model이 sources 필드를 내려주면 클릭해서 펼치는 카드로 보여준다.
    카드 제목은 "제O조(제목)"을 우선 쓰고(본문에서 자동 추출), 없으면 "파일명 · N페이지"로 대체한다.
    펼치면 해당 조항 원문이 그대로 나와서, 클릭 한 번으로 근거 조항을 바로 확인할 수 있다.
    """
    if not sources:
        return

    st.caption(f"📎 관련 조항 {len(sources)}건 — 클릭하면 원문을 볼 수 있어요")
    for idx, src in enumerate(sources, start=1):
        filename = src.get("filename") or src.get("source") or "알 수 없는 문서"
        page = src.get("page") or src.get("page_num")
        text = src.get("text") or src.get("snippet") or ""
        article = src.get("article") or extract_article_label(text)

        title = article or filename
        meta = filename + (f" · {page}페이지" if page else "")

        with st.expander(f"{idx}. {title}"):
            st.caption(meta)
            st.markdown(text if text else "_본문 미리보기가 제공되지 않았습니다._")
