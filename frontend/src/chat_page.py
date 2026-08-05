"""
chat_page.py
- 사용자용 챗봇 화면. backend와의 통신은 api_client를 통해서만 한다.
"""

import streamlit as st

from api_client import BackendError, ask_stream, send_feedback
from sources import render_sources


def _render_feedback(idx: int, message: dict):
    """답변 아래 👍/👎 버튼. 누르면 backend로 피드백을 보낸다 (backend에 엔드포인트가
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


def render():
    st.title("KDT 규정집 챗봇")
    st.caption("국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.")

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

    if question := st.chat_input("질문을 입력하세요."):
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            if not st.session_state.asked_once:
                # 모델 최초 로딩 안내: 스트리밍 첫 토큰이 오기 전까지 잠깐 보여줌
                st.caption("🧠 모델을 처음 준비하는 중이에요. 첫 응답은 조금 더 걸릴 수 있어요...")

            answer = ""
            sources = None
            is_error = False

            # backend가 SSE로 토큰을 흘려주면 st.write_stream()이 도착하는 대로 화면에 찍어주고,
            # 스트림이 끝나면 합쳐진 전체 텍스트를 반환한다.
            try:
                answer = st.write_stream(ask_stream(question)) or ""
            except BackendError as e:
                answer = str(e)
                is_error = True
                st.error(answer)
            else:
                render_sources(sources)

            st.session_state.asked_once = True

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "sources": sources,
                "is_error": is_error,
                "question": question,
            }
        )
