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
from theme import inject_custom_css, render_topbar

st.set_page_config(
    page_title="KDT 규정집 챗봇",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

inject_custom_css()
render_topbar(render_login_widget)

if "selected_cohort" not in st.session_state:
    st.session_state.selected_cohort = None


def _render_cohort_picker():
    st.markdown(
        """
        <div style="
            background:linear-gradient(135deg,#6366F1 0%,#8B5CF6 100%);
            border-radius:28px;
            padding:2.75rem 1.5rem;
            text-align:center;
            box-shadow:0 16px 36px rgba(99,102,241,0.28);
            margin-bottom:1.75rem;
        ">
          <div style="font-size:3rem;">🎓</div>
          <div style="color:#fff;font-size:1.8rem;font-weight:800;letter-spacing:-0.02em;
                      margin:0.4rem 0 0.3rem;">KDT 챗봇</div>
          <p style="color:rgba(255,255,255,0.88);margin:0;font-size:1rem;">
            소속된 기수를 선택해주세요
          </p>
        </div>
        """,
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
                        f"""
                        <div style="width:52px;height:52px;border-radius:16px;
                                    background:linear-gradient(135deg,#EEF0FE,#E0E7FF);
                                    display:flex;align-items:center;justify-content:center;
                                    font-size:1.6rem;margin:0.2rem auto 0.6rem;">
                          {data.get('icon', '🎓')}
                        </div>
                        <div style="text-align:center;font-weight:800;font-size:1.05rem;">{name}</div>
                        <p style="text-align:center;color:#6B7280;font-size:0.85rem;margin:0.15rem 0 0.8rem;">
                          {data.get('subtitle', '')}
                        </p>
                        """,
                        unsafe_allow_html=True,
                    )
                    if st.button(
                        "선택",
                        key=f"cohort_{name}",
                        use_container_width=True,
                        type="primary",
                    ):
                        st.session_state.selected_cohort = name
                        st.rerun()


if not st.session_state.selected_cohort:
    _render_cohort_picker()
else:
    with st.sidebar:
        st.markdown(
            f"""
            <div style="background:linear-gradient(135deg,#6366F1,#8B5CF6);
                        color:#fff;border-radius:14px;padding:0.7rem 0.9rem;
                        font-weight:700;margin-bottom:0.6rem;box-shadow:0 4px 12px rgba(99,102,241,0.25);">
              📌 현재 기수 · {st.session_state.selected_cohort}
            </div>
            """,
            unsafe_allow_html=True,
        )
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
