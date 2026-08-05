"""
chat_page.py
- 사용자용 챗봇 화면. model과의 통신은 api_client를 통해서만 한다.
"""

import streamlit as st

from api_client import ModelServiceError, ask_stream, send_feedback
from sources import render_sources
from theme import page_header

# 챗봇 화면에 바로 보여줄 자주 묻는 질문(규정 관련 위주).
# 일정처럼 기수마다 값이 달라지는 정보는 여기 넣지 않는다 — 벡터DB가 기수 구분 없이
# 통합돼 있어서, 기수별 정보를 챗봇으로 물으면 다른 기수 내용이 섞여 나올 수 있다.
FAQ_QUESTIONS = [
    "출석 인정 기준이 어떻게 되나요?",
    "수료 조건이 무엇인가요?",
    "훈련장려금은 어떻게 지급되나요?",
]


def _render_feedback(idx: int, message: dict):
    """답변 아래 👍/👎 버튼. 누르면 model로 피드백을 보낸다 (model에 엔드포인트가
    아직 없어도 조용히 무시되므로 안전). 같은 평가를 매 rerun마다 중복 전송하지 않도록
    message에 마지막으로 보낸 값을 기록해둔다.
    """
    rating_idx = st.feedback("thumbs", key=f"feedback_{idx}")
    if rating_idx is None:
        return
    rating = "up" if rating_idx == 1 else "down"
    if message.get("feedback_sent") != rating:
        send_feedback(question=message.get("question", ""), answer=message["content"], rating=rating)
        message["feedback_sent"] = rating


def _ask(question: str):
    """질문 하나를 처리해서 화면에 그린다. st.chat_input으로 직접 입력한 경우와
    FAQ 버튼을 클릭한 경우가 완전히 동일하게 동작하도록 이 함수 하나로 모은다.
    """
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        spinner_text = (
            "🧠 모델을 처음 준비하는 중이에요. 첫 응답은 조금 더 걸릴 수 있어요..."
            if not st.session_state.asked_once
            else "💬 답변 생성 중..."
        )

        answer = ""
        sources: list = []
        is_error = False

        with st.spinner(spinner_text):
            try:
                answer = st.write_stream(ask_stream(question, sources_out=sources))
            except ModelServiceError as e:
                answer = str(e)
                is_error = True

        st.session_state.asked_once = True

        if is_error:
            st.error(answer)
        else:
            render_sources(sources)

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "is_error": is_error,
            "question": question,
        }
    )


def render():
    page_header("💬", "KDT 규정집 챗봇", "국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "asked_once" not in st.session_state:
        # 모델 최초 로딩 안내용: 첫 질문 전/후를 구분해 스피너 문구를 다르게 보여준다.
        st.session_state.asked_once = False

    for idx, message in enumerate(st.session_state.messages):
        with st.chat_message(message["role"]):
            if message.get("is_error"):
                st.error(message["content"])
            else:
                st.markdown(message["content"])
                render_sources(message.get("sources"))
                if message["role"] == "assistant":
                    _render_feedback(idx, message)

    pending_question = None

    if not st.session_state.messages:
        st.markdown("💡 **자주 묻는 질문**")
        cols = st.columns(len(FAQ_QUESTIONS))
        for col, q in zip(cols, FAQ_QUESTIONS):
            if col.button(q, use_container_width=True, key=f"faq_{q}"):
                pending_question = q

    typed_question = st.chat_input("질문을 입력하세요.")
    question = pending_question or typed_question

    if question:
        _ask(question)
