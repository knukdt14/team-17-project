"""
app.py
- frontend 컨테이너의 Streamlit 진입점.
- 로그인 상태(auth.py)에 따라 챗봇/관리자 메뉴를 구성하고, 각 화면은
  chat_page.py / admin_page.py에 위임한다.
- RAG 로직/모델 관련 코드는 전혀 갖지 않는다. model 서비스(/ask, /ingest)만 직접 호출.
"""

import streamlit as st

import admin_page
import chat_page
from auth import is_admin, render_login_widget

st.set_page_config(
    page_title="KDT 규정집 챗봇",
    page_icon="🎓",
    layout="centered",
    initial_sidebar_state="expanded",
)

render_login_widget()

pages = [st.Page(chat_page.render, title="챗봇", icon="💬", url_path="chat", default=True)]
if is_admin():
    pages.append(st.Page(admin_page.render, title="관리자", icon="🛠️", url_path="admin"))

nav = st.navigation(pages, position="sidebar")
nav.run()
