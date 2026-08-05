"""
admin_page.py
- 관리자 전용 화면: 규정 PDF 업로드/반영.
- app.py의 st.navigation이 is_admin()일 때만 이 페이지를 메뉴에 노출하므로,
  로그인 안 한 사용자에게는 이 페이지 자체가 보이지 않는다.
"""

import streamlit as st

from api_client import ModelServiceError, upload_pdf


def render():
    st.title("🛠️ 관리자 - 규정 PDF 관리")
    st.caption("규정이 바뀌었을 때 새 PDF를 업로드해서 벡터DB에 반영합니다.")

    uploaded = st.file_uploader("PDF 파일 업로드", type=["pdf"])
    if uploaded is not None and st.button("업로드 및 벡터DB에 반영"):
        with st.spinner("업로드 및 반영 중..."):
            try:
                data = upload_pdf(uploaded.name, uploaded.getvalue())
                st.success(f"{data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)")
            except ModelServiceError as e:
                st.error(str(e))

    st.divider()
    st.subheader("업로드된 문서 목록")
    st.info(
        "📋 문서 목록 조회/삭제 기능은 아직 model에 관련 API(`/documents` 등)가 없어서 "
        "준비 중입니다. 추가되면 여기에 목록·삭제 UI를 연결하겠습니다."
    )
