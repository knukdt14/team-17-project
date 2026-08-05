"""
auth.py
- 관리자 로그인/권한 체크. 회원가입 없이 관리자 비밀번호 하나만 관리하는 단순 구조
  (실사용 전환 시 사용자별 계정이 필요해지면 이 모듈만 교체하면 됨).
- ADMIN_PASSWORD 환경변수로 비밀번호를 바꿀 수 있다. 미설정 시 기본값을 쓰고 경고를 보여준다.
"""

import os

import streamlit as st

_DEFAULT_ADMIN_PASSWORD = "changeme"
_SESSION_KEY = "is_admin"


def _admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)


def is_admin() -> bool:
    return bool(st.session_state.get(_SESSION_KEY, False))


def render_login_widget():
    """사이드바에 로그인/로그아웃 UI를 그린다. app.py 진입 시 한 번 호출하면 된다."""
    with st.sidebar:
        st.divider()
        if is_admin():
            st.success("🔑 관리자로 로그인됨")
            if st.button("로그아웃", use_container_width=True):
                st.session_state[_SESSION_KEY] = False
                st.rerun()
        else:
            with st.expander("🔒 관리자 로그인"):
                pw = st.text_input("비밀번호", type="password", key="admin_pw_input")
                if st.button("로그인", use_container_width=True):
                    if pw and pw == _admin_password():
                        st.session_state[_SESSION_KEY] = True
                        st.rerun()
                    else:
                        st.error("비밀번호가 올바르지 않습니다.")

        if _admin_password() == _DEFAULT_ADMIN_PASSWORD:
            st.caption("⚠️ ADMIN_PASSWORD 환경변수 미설정 — 기본 비밀번호(changeme) 사용 중")
