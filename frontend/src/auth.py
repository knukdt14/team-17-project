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
    """작은 로그인 버튼(팝오버) 하나를 그 자리에 그린다. 배치(사이드바/상단바 등)는
    호출하는 쪽(theme.render_topbar)이 결정하고, 이 함수는 로그인 로직/내용에만 집중한다."""
    if is_admin():
        with st.popover("🔑", use_container_width=True):
            st.caption("관리자로 로그인됨")
            if st.button("로그아웃", use_container_width=True, key="admin_logout_btn"):
                st.session_state[_SESSION_KEY] = False
                st.rerun()
    else:
        with st.popover("🔒", use_container_width=True):
            st.caption("관리자 로그인")
            pw = st.text_input(
                "비밀번호",
                type="password",
                key="admin_pw_input",
                label_visibility="collapsed",
                placeholder="비밀번호",
            )
            if st.button("로그인", use_container_width=True, key="admin_login_btn"):
                if pw and pw == _admin_password():
                    st.session_state[_SESSION_KEY] = True
                    st.rerun()
                else:
                    st.error("비밀번호가 올바르지 않습니다.")
            if _admin_password() == _DEFAULT_ADMIN_PASSWORD:
                st.caption("⚠️ ADMIN_PASSWORD 환경변수 미설정 — 기본값 사용 중")
