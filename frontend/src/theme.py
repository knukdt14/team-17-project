"""
theme.py
- config.toml의 색상만으로는 버튼/카드/말풍선 모양, 여백까지 못 바꿔서 여기서 CSS를
  한 번 더 주입한다. 전체 배경에 은은한 인디고 그라데이션을 깔고, Streamlit 기본 레이아웃의
  과한 상단 여백을 줄이고, 카드/버튼에 그림자와 채도를 더 줘서 밋밋해 보이지 않게 한다.
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
    --accent-2: #8B5CF6;
    --accent-soft: #EEF0FE;
    --border-soft: #E5E3FA;
    --text-muted: #6B7280;
}

html, body, [data-testid="stAppViewContainer"], [class*="css"] {
    font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* 전체 배경 - 순백 대신 은은한 인디고 그라데이션 */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(180deg, #F3F1FF 0%, #FAFAFF 45%, #FFFFFF 100%) !important;
    background-attachment: fixed !important;
}

/* 상단 고정 툴바가 흰색이라 그라데이션과 이질감이 생기는 걸 방지 - 투명하게 */
[data-testid="stHeader"] {
    background: transparent !important;
}

/* Streamlit 기본 상단 여백이 과해서 "휑해 보이는" 원인 중 하나 - 줄이되,
   상단 고정 툴바(Deploy 메뉴 바)에 콘텐츠가 가려지지 않도록 최소 여백은 남긴다. */
.block-container {
    padding-top: 3.5rem !important;
    padding-bottom: 3rem !important;
    max-width: 780px !important;
}
[data-testid="stSidebar"] .block-container {
    padding-top: 1.5rem !important;
}

h1, h2, h3 {
    font-weight: 800 !important;
    letter-spacing: -0.02em !important;
}
h3 {
    color: var(--accent) !important;
    font-size: 1.05rem !important;
    border-bottom: 2px solid var(--accent-soft);
    padding-bottom: 0.35rem;
    margin-top: 1.4rem !important;
}

[data-testid="stCaptionContainer"], .stCaption {
    color: var(--text-muted) !important;
}

/* 버튼: 카드 스타일 + 살짝 뜨는 호버 */
[data-testid="stButton"] button,
[data-testid="stLinkButton"] a {
    border-radius: 14px !important;
    border: 1.5px solid var(--border-soft) !important;
    background: #FFFFFF !important;
    color: #1F2333 !important;
    font-weight: 700 !important;
    padding: 0.6rem 1rem !important;
    box-shadow: 0 2px 6px rgba(99, 102, 241, 0.06) !important;
    transition: all 0.15s ease !important;
}
[data-testid="stButton"] button:hover,
[data-testid="stLinkButton"] a:hover {
    border-color: var(--accent) !important;
    color: var(--accent) !important;
    box-shadow: 0 8px 20px rgba(99, 102, 241, 0.18) !important;
    transform: translateY(-2px);
}
[data-testid="stButton"] button:active {
    transform: translateY(0px);
}

/* primary 버튼(카드 CTA 등) - 그라데이션 채움 */
[data-testid="stButton"] button[kind="primary"] {
    background: linear-gradient(135deg, var(--accent) 0%, var(--accent-2) 100%) !important;
    border: none !important;
    color: #FFFFFF !important;
    box-shadow: 0 6px 16px rgba(99, 102, 241, 0.28) !important;
}
[data-testid="stButton"] button[kind="primary"]:hover {
    color: #FFFFFF !important;
    box-shadow: 0 10px 22px rgba(99, 102, 241, 0.36) !important;
    transform: translateY(-2px);
}

/* 기수 선택 카드 (st.container(border=True)) */
[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 20px !important;
    border: 1.5px solid var(--border-soft) !important;
    background: #FFFFFF !important;
    box-shadow: 0 4px 14px rgba(99, 102, 241, 0.07) !important;
    transition: all 0.18s ease !important;
}
[data-testid="stVerticalBlockBorderWrapper"]:hover {
    border-color: var(--accent) !important;
    box-shadow: 0 12px 26px rgba(99, 102, 241, 0.16) !important;
    transform: translateY(-2px);
}

/* 채팅 말풍선 - 카드처럼 테두리/그림자를 줘서 배경과 분리 */
[data-testid="stChatMessage"] {
    border-radius: 18px !important;
    border: 1px solid var(--border-soft) !important;
    background: #FFFFFF !important;
    box-shadow: 0 2px 10px rgba(99, 102, 241, 0.06) !important;
    padding: 0.9rem 1.1rem !important;
    margin-bottom: 0.7rem !important;
}

/* 출처 카드 / expander */
[data-testid="stExpander"] {
    border-radius: 14px !important;
    border: 1px solid var(--border-soft) !important;
    background: var(--accent-soft) !important;
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
    background: #F6F5FF !important;
    border-right: 1px solid #ECEAFB !important;
}

/* 로딩 스피너 - 기본 회색 대신 브랜드 컬러로, 답변 대기 중이라는 느낌을 통일감 있게 */
[data-testid="stSpinner"] > div {
    border-top-color: var(--accent) !important;
}
[data-testid="stSpinner"] p {
    color: var(--accent) !important;
    font-weight: 600 !important;
}
</style>
"""


def inject_custom_css():
    st.markdown(_CSS, unsafe_allow_html=True)


def render_topbar(right_renderer):
    """좌측 브랜드 마크 + 우측 위젯(관리자 로그인 등)을 한 줄에 배치하는 상단바.
    사이드바에는 "현재 기수/메뉴"만 남기고, 로그인처럼 자주 안 쓰는 기능은 눈에 덜 띄게
    상단 구석으로 뺀다."""
    left, right = st.columns([6, 1])
    with left:
        st.markdown(
            """
            <div style="display:flex;align-items:center;gap:0.5rem;padding-top:0.35rem;">
              <span style="font-size:1.3rem;">🎓</span>
              <span style="font-weight:800;font-size:1.05rem;color:#1F2333;letter-spacing:-0.01em;">
                KDT 규정집 챗봇
              </span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with right:
        right_renderer()


def page_header(icon: str, title: str, subtitle: str = ""):
    """st.title()+st.caption() 대신 쓰는 아이콘 뱃지형 헤더. 모든 탭에서 통일된 톤을 준다."""
    sub_html = (
        f"<p style='color:#6B7280;margin:0.2rem 0 0;font-size:0.92rem;'>{subtitle}</p>"
        if subtitle
        else ""
    )
    st.markdown(
        f"""
        <div style="display:flex;align-items:center;gap:0.9rem;margin-bottom:1.5rem;">
          <div style="width:52px;height:52px;min-width:52px;border-radius:16px;
                      background:linear-gradient(135deg,#EEF0FE,#E0E7FF);
                      display:flex;align-items:center;justify-content:center;
                      font-size:1.6rem;box-shadow:0 2px 8px rgba(99,102,241,0.15);">
            {icon}
          </div>
          <div>
            <div style="font-size:1.55rem;font-weight:800;letter-spacing:-0.02em;color:#1F2333;">{title}</div>
            {sub_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
