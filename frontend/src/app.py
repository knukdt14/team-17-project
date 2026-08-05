"""
app.py
- frontend 컨테이너의 Streamlit 진입점.
- 기수를 먼저 선택해야 사이드바 탭(챗봇/일정/오시는길/강의실사진/관리자)이 나타난다.
- 로그인 상태(auth.py)에 따라 관리자 메뉴가 추가로 노출된다.
- RAG 로직/모델 관련 코드는 전혀 갖지 않는다. model 서비스(/ask, /ingest)만 직접 호출.
"""

import streamlit as st

import admin_page
import chat_page
import classroom_page
import map_page
import schedule_page
from auth import is_admin, render_login_widget
from cohorts import COHORT_LIST, get_cohort
from theme import inject_custom_css

st.set_page_config(
    page_title="KDT 규정집 챗봇",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

inject_custom_css()
render_login_widget()

if "selected_cohort" not in st.session_state:
    st.session_state.selected_cohort = None


def _render_cohort_picker():
    st.markdown(
        "<div style='text-align:center;padding:1.5rem 0 0.5rem;'>"
        "<div style='font-size:2.75rem;'>🎓</div>"
        "<h1 style='margin-bottom:0.15rem;'>KDT 챗봇</h1>"
        "<p style='color:#6B7280;font-size:1rem;margin-top:0;'>소속된 기수를 선택해주세요</p>"
        "</div>",
        unsafe_allow_html=True,
    )

    rows = [COHORT_LIST[i : i + 2] for i in range(0, len(COHORT_LIST), 2)]
    for row in rows:
        cols = st.columns(len(row))
        for col, name in zip(cols, row):
            data = get_cohort(name)
            with col:
                with st.container(border=True):
                    st.markdown(
                        f"<div style='font-size:1.8rem;'>{data.get('icon', '🎓')}</div>",
                        unsafe_allow_html=True,
                    )
                    st.markdown(f"**{name}**")
                    st.caption(data.get("subtitle", ""))
                    if st.button("선택", key=f"cohort_{name}", use_container_width=True):
                        st.session_state.selected_cohort = name
                        st.rerun()


if not st.session_state.selected_cohort:
    _render_cohort_picker()
else:
    with st.sidebar:
        st.caption(f"📌 현재 기수: **{st.session_state.selected_cohort}**")
        if st.button("기수 변경", use_container_width=True):
            st.session_state.selected_cohort = None
            st.rerun()

    pages = [
        st.Page(chat_page.render, title="챗봇", icon="💬", url_path="chat", default=True),
        st.Page(schedule_page.render, title="일정", icon="📅", url_path="schedule"),
        st.Page(map_page.render, title="오시는길", icon="📍", url_path="map"),
        st.Page(classroom_page.render, title="강의실 사진", icon="🏫", url_path="classroom"),
    ]
    if is_admin():
        pages.append(st.Page(admin_page.render, title="관리자", icon="🛠️", url_path="admin"))

    nav = st.navigation(pages, position="sidebar")
    nav.run()
