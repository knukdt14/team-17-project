"""
app.py
- frontend 컨테이너의 Streamlit 챗봇 UI: backend 게이트웨이(/ask, /upload)만 호출한다.
- RAG 로직/모델 관련 코드는 전혀 갖지 않는다.
"""

import os

import requests
import streamlit as st

BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8000")
REQUEST_TIMEOUT = float(os.environ.get("BACKEND_REQUEST_TIMEOUT", "120"))

st.set_page_config(page_title="KDT 규정집 챗봇", page_icon="🎓")
st.title("KDT 규정집 챗봇")
st.caption("국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.")

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.subheader("규정 PDF 추가")
    uploaded = st.file_uploader("PDF 파일 업로드", type=["pdf"])
    if uploaded is not None and st.button("업로드 및 벡터DB에 반영"):
        with st.spinner("업로드 및 반영 중..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/upload",
                    files={"file": (uploaded.name, uploaded.getvalue(), "application/pdf")},
                    timeout=REQUEST_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
                st.success(f"{data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)")
            except requests.RequestException as e:
                st.error(f"업로드 실패: {e}")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if question := st.chat_input("질문을 입력하세요."):
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("답변 생성 중..."):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/ask", json={"question": question}, timeout=REQUEST_TIMEOUT
                )
                resp.raise_for_status()
                answer = resp.json()["answer"]
            except requests.RequestException as e:
                answer = f"죄송합니다, 답변을 가져오지 못했습니다. ({e})"
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
