"""
theme.py
- config.toml의 색상만으로는 버튼/카드/말풍선 모양까지 못 바꿔서, 여기서 CSS를 한 번 더
  주입해 전체적으로 화이트 미니멀 + 인디고 포인트 컬러의 트렌디한 톤을 입힌다.
- data-testid 셀렉터를 우선 쓴다 (Streamlit 내부 class명보다 버전 변화에 덜 취약함).
  다만 100% 안정 보장은 안 되므로, 셀렉터가 안 맞아도 앱 동작 자체는 깨지지 않는다
  (그냥 스타일이 일부 안 먹는 정도).
"""

import streamlit as st

_CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

:root {
    --accent: #6366F1;
    --accent-soft: #EEF0FE;
    --border-soft: #E7E8F0;
    --text-muted: #6B7280;
}

html, body, [data-testid="stAppViewContainer"], [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

h1, h2, h3 {
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
}

[data-testid="stCaptionContainer"], .stCaption {
    color: var(--text-muted) !important;
}

/* 버튼: 필/카드 스타일 + 살짝 뜨는 호버 */
[data-testid="stButton"] button,
[data-testid="stLinkButton"] a {
    border-radius: 14px !important;
    border: 1px solid var(--border-soft) !important;
    background: #FFFFFF !important;
    color: #1F2333 !important;
    font-weight: 600 !important;
    padding: 0.55rem 1rem !important;
    box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButton"] button:hover,
[data-testid="stLinkButton"] a:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.16) !important;
    transform: translateY(-1px);
}
[data-testid="stButton"] button:active {
    transform: translateY(0px);
}
[data-testid="stButton"] button[kind="primary"] {
    background: var(--accent) !important;
    border-color: var(--accent) !important;
    color: #FFFFFF !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    color: #FFFFFF !important;
    filter: brightness(1.08);
}

/* 기수 선택 카드 (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 18px !important;
    border: 1px solid var(--border-soft) !important;
    box-shadow: 0 2px 8px rgba(16, 24, 40, 0.04) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.12) !important;
}

/* 채팅 말풍선 */
[data-testid="stChatMessage"] {
    border-radius: 16px !important;
    margin-bottom: 0.5rem !important;
}

/* 출처 카드 / expander */
[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid var(--border-soft) !important;
    overflow: hidden;
}

/* 알림 박스 */
[data-testid="stAlert"] {
    border-radius: 14px !important;
}

/* 입력 필드 */
input, textarea, [data-testid="stChatInput"] textarea {
    border-radius: 12px !important;
}

/* 사이드바 */
[data-testid="stSidebar"] {
    background: #F6F7FB !important;
    border-right: 1px solid #ECEDF3 !important;
}
</style>
"""


def inject_custom_css():
    st.markdown(_CSS, unsafe_allow_html=True)
