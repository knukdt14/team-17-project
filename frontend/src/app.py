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

st.set_page_config(
    page_title="KDT 규정집 챗봇",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

st.title("KDT 규정집 챗봇")
st.caption("국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "asked_once" not in st.session_state:
    # 모델 최초 로딩 안내용: 첫 질문 전/후를 구분해 스피너 문구를 다르게 보여준다.
    st.session_state.asked_once = False


def render_sources(sources):
    """출처 카드 UI. backend/model이 sources 필드를 내려주면 접었다 펼치는 카드로 보여준다.
    아직 backend가 sources를 내려주지 않아도 에러 없이 조용히 아무것도 표시하지 않는다.
    """
    if not sources:
        return
    with st.expander(f"📎 출처 {len(sources)}건 보기"):
        for src in sources:
            filename = src.get("filename") or src.get("source") or "알 수 없는 문서"
            page = src.get("page") or src.get("page_num")
            label = f"**📄 {filename}**" + (f" · {page}페이지" if page else "")
            st.markdown(label)
            snippet = src.get("text") or src.get("snippet")
            if snippet:
                st.caption(snippet)


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
            except requests.Timeout:
                st.error("⏱️ 업로드 요청이 시간 초과되었습니다. 파일 크기를 확인하거나 잠시 후 다시 시도해주세요.")
            except requests.ConnectionError:
                st.error("🔌 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.")
            except requests.RequestException as e:
                st.error(f"❌ 업로드 실패: {e}")

    st.divider()
    st.caption("ℹ️ 첫 질문은 모델이 준비되는 데 시간이 다소 걸릴 수 있어요.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message.get("is_error"):
            st.error(message["content"])
        else:
            st.markdown(message["content"])
            render_sources(message.get("sources"))

if question := st.chat_input("질문을 입력하세요."):
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
        sources = None
        is_error = False

        with st.spinner(spinner_text):
            try:
                resp = requests.post(
                    f"{BACKEND_URL}/ask", json={"question": question}, timeout=REQUEST_TIMEOUT
                )
                if resp.status_code == 429:
                    # 동시 요청이 몰려 backend/model이 바쁠 때를 대비한 안내
                    answer = "🚦 지금 다른 사용자의 답변을 생성하고 있어요. 잠시 후 다시 시도해주세요."
                    is_error = True
                else:
                    resp.raise_for_status()
                    data = resp.json()
                    answer = data.get("answer", "")
                    sources = data.get("sources")
            except requests.Timeout:
                answer = "⏱️ 죄송합니다, 응답 시간이 초과되었습니다. 잠시 후 다시 시도해주세요."
                is_error = True
            except requests.ConnectionError:
                answer = "🔌 죄송합니다, 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요."
                is_error = True
            except requests.RequestException as e:
                answer = f"❌ 죄송합니다, 답변을 가져오지 못했습니다. ({e})"
                is_error = True

        st.session_state.asked_once = True

        if is_error:
            st.error(answer)
        else:
            st.markdown(answer)
            render_sources(sources)

    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources, "is_error": is_error}
    )
