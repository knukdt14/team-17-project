"""
theme.py
- 앱 전체 브랜드 컬러 / 모션(애니메이션) 시스템 / 헤더 / 좌측 네비게이션(드로어)을
  한 곳에서 관리한다.
- "AI 웹디자이너" 컨셉으로 다시 다듬은 톤: 크림슨 레드 + 딥 잉크 + 골드 포인트를 쓰는
  고급 기관형 팔레트, Pretendard 폰트, 카드/버튼/말풍선에 진입 애니메이션과 호버
  인터랙션을 광범위하게 깔아서 Streamlit 시절의 밋밋한 느낌을 완전히 벗어난다.
  헤더 좌측에는 경북대 로고(frontend/assets/logo_13.png)를 고정으로 붙인다.
- frame()이 모든 페이지 공통 뼈대(헤더+드로어)를 그리고, 각 페이지는 그 아래 본문만 채우면 된다.
"""

import os

from nicegui import app, ui

from api_client import ModelServiceError, upload_pdf
from auth import is_admin, render_login_widget

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
KNU_LOGO_PATH = os.path.join(ASSETS_DIR, "logo_13.png")

ACCENT = "#C8102E"
ACCENT_DARK = "#8F0B21"
ACCENT_SOFT = "#C8102E14"
GOLD = "#AD8A3B"
INK = "#1B1F2A"
MUTED = "#6B7280"
BORDER = "#E9E5DD"
BG = "#FAF9F6"
# 관리자로 로그인하면 화면 전체가 살짝 어두워져서 "지금은 일반 화면이 아니다"가 한눈에
# 구분되게 한다.
ADMIN_BG = "#D7DBE2"
ADMIN_DRAWER_BG = "#EEF0F3"

NAV_ITEMS = [
    ("챗봇", "/chat"),
    ("일정", "/schedule"),
    ("오시는길", "/map"),
    ("교수진", "/faculty"),
]


def apply_global_style():
    ui.colors(primary=ACCENT, secondary=INK)
    body_bg = ADMIN_BG if is_admin() else BG
    ui.add_head_html(
        f"""
        <link rel="preconnect" href="https://cdn.jsdelivr.net">
        <style>
          @import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

          :root {{
            --kdt-accent: {ACCENT};
            --kdt-accent-dark: {ACCENT_DARK};
            --kdt-gold: {GOLD};
            --kdt-ink: {INK};
            --kdt-muted: {MUTED};
            --kdt-border: {BORDER};
            --kdt-shadow-sm: 0 2px 8px rgba(27,31,42,0.06);
            --kdt-shadow-md: 0 12px 28px rgba(27,31,42,0.10), 0 2px 6px rgba(27,31,42,0.06);
            --kdt-shadow-glow: 0 18px 40px rgba(200,16,46,0.18);
          }}

          html, body, .q-field, .q-btn, .q-card {{
            font-family: 'Pretendard', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
          }}

          body {{
            background: {body_bg} !important;
            background-image:
              radial-gradient(circle at 12% 8%, rgba(200,16,46,0.045) 0%, transparent 45%),
              radial-gradient(circle at 88% 92%, rgba(173,138,59,0.05) 0%, transparent 45%);
            background-attachment: fixed;
          }}

          ::selection {{ background: {ACCENT}; color: #fff; }}

          ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
          ::-webkit-scrollbar-track {{ background: transparent; }}
          ::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, {ACCENT}, {ACCENT_DARK});
            border-radius: 999px;
            border: 2px solid {BG};
          }}

          /* ---------- 모션 시스템 ---------- */
          @keyframes kdt-fade-up {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
          }}
          @keyframes kdt-fade-in {{
            from {{ opacity: 0; }}
            to   {{ opacity: 1; }}
          }}
          @keyframes kdt-pop-in {{
            0%   {{ opacity: 0; transform: scale(0.94) translateY(8px); }}
            100% {{ opacity: 1; transform: scale(1) translateY(0); }}
          }}
          @keyframes kdt-underline-grow {{
            from {{ width: 0; }}
            to   {{ width: 100%; }}
          }}
          @keyframes kdt-pulse-glow {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(200,16,46,0.28); }}
            50%      {{ box-shadow: 0 0 0 8px rgba(200,16,46,0); }}
          }}

          .kdt-fade-up {{ animation: kdt-fade-up 0.6s cubic-bezier(.2,.7,.2,1) both; }}
          .kdt-stagger > * {{ opacity: 0; animation: kdt-pop-in 0.55s cubic-bezier(.2,.7,.2,1) both; }}
          .kdt-stagger > *:nth-child(1) {{ animation-delay: 0.02s; }}
          .kdt-stagger > *:nth-child(2) {{ animation-delay: 0.10s; }}
          .kdt-stagger > *:nth-child(3) {{ animation-delay: 0.18s; }}
          .kdt-stagger > *:nth-child(4) {{ animation-delay: 0.26s; }}
          .kdt-stagger > *:nth-child(5) {{ animation-delay: 0.34s; }}
          .kdt-stagger > *:nth-child(6) {{ animation-delay: 0.42s; }}

          /* ---------- 카드 ---------- */
          .q-card {{
            border-radius: 18px !important;
            border: 1px solid {BORDER} !important;
            box-shadow: var(--kdt-shadow-sm) !important;
            transition: transform 0.28s cubic-bezier(.2,.7,.2,1), box-shadow 0.28s ease, border-color 0.28s ease;
          }}
          a.no-underline .q-card, .kdt-hover .q-card {{ will-change: transform; }}

          /* ---------- 버튼 ---------- */
          .q-btn {{
            transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease !important;
            border-radius: 12px;
          }}
          .q-btn:active {{ transform: scale(0.97); }}
          .q-btn.bg-primary, .q-btn[color=primary] {{
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%) !important;
          }}

          .q-menu {{
            border-radius: 16px !important;
            box-shadow: var(--kdt-shadow-md) !important;
            animation: kdt-pop-in 0.18s ease both;
          }}

          /* ---------- 채팅 말풍선: 새로 생기면 자동으로 슬라이드-인 ---------- */
          .q-message {{ animation: kdt-fade-up 0.4s cubic-bezier(.2,.7,.2,1) both; }}
          .q-message-text--sent, .q-message-text--sent > div {{
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%) !important;
            color: #fff !important;
            box-shadow: 0 6px 16px rgba(200,16,46,0.22);
          }}
          .q-message-text--received, .q-message-text--received > div {{
            background: #FFFFFF !important;
            color: {INK} !important;
            border: 1px solid {BORDER};
            box-shadow: var(--kdt-shadow-sm);
          }}
          .q-message-name {{
            color: {MUTED} !important; font-weight: 700 !important; font-size: 0.72rem !important;
            letter-spacing: 0.02em;
          }}

          /* ---------- 토글(무료/유료) ---------- */
          .q-btn-toggle {{ transition: box-shadow 0.25s ease; }}
          .q-btn-toggle .q-btn {{ transition: background 0.25s ease, color 0.25s ease !important; }}

          /* ---------- 링크 ---------- */
          a {{ transition: color 0.2s ease; }}
        </style>
        """
    )


def _clear_cohort():
    # 기수를 바꾸면 이전 기수에서 나눴던 대화가 새 기수 화면에 그대로 남아있으면 안 되니
    # 같이 비운다.
    app.storage.user["selected_cohort"] = None
    app.storage.user["chat_messages"] = []


def _brand_mark():
    with ui.row().classes("items-center gap-3"):
        ui.element("div").classes("w-1 h-9 rounded-full").style(
            f"background:linear-gradient(180deg,{ACCENT},{GOLD});"
        )
        if os.path.exists(KNU_LOGO_PATH):
            ui.image(KNU_LOGO_PATH).classes("w-8 h-8 transition-transform hover:scale-110").props(
                "fit=contain"
            )
        with ui.column().classes("gap-0"):
            ui.label("KDT AI·빅데이터").classes("font-extrabold text-base leading-tight").style(f"color:{INK};")
            ui.label("경북대학교 데이터융복합연구원").classes("text-[11px] leading-tight").style(f"color:{MUTED};")


def _render_upload_panel():
    """관리자 전용 드로어 내용: 규정 PDF를 업로드하면 model이 청킹 후 벡터DB에 바로
    반영하고 디스크에 저장(save_local)해서, 컨테이너를 재시작해도 남아있다."""
    ui.label("🛠️ 관리자 모드").classes("font-extrabold text-sm").style(f"color:{ACCENT};")
    ui.label("PDF를 올리면 벡터DB에 바로 반영되어 챗봇 답변에 곧장 쓰입니다.").classes(
        "text-xs mb-4"
    ).style(f"color:{MUTED};")

    status_label = ui.label("").classes("text-xs mt-2").style(f"color:{MUTED};")

    async def _handle_upload(e):
        content = await e.file.read()
        status_label.text = "업로드 및 반영 중..."
        status_label.style(f"color:{MUTED};")
        try:
            data = await upload_pdf(e.file.name, content)
            status_label.text = f"✅ {data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)"
            status_label.style("color:#16a34a;")
        except ModelServiceError as err:
            status_label.text = str(err)
            status_label.style("color:#dc2626;")

    ui.upload(on_upload=_handle_upload, auto_upload=True, label="PDF 업로드").props(
        "accept=.pdf flat bordered"
    ).classes("w-full")


def frame(current_path: str = ""):
    """헤더(브랜드+로그인) + 좌측 드로어를 그린다. 드로어 내용은 관리자 로그인 여부로 갈린다:
    관리자면 기수/메뉴 대신 PDF 업로드 패널만 보여주고(메인 화면은 챗봇에 고정), 아니면
    기존처럼 기수 선택 후 메뉴 네비게이션을 보여준다."""
    apply_global_style()
    cohort = app.storage.user.get("selected_cohort")
    admin = is_admin()

    with ui.header().classes("items-center justify-between px-6 py-3").style(
        f"background: rgba(255,255,255,0.85); backdrop-filter: blur(10px); "
        f"border-bottom: 1px solid {BORDER}; box-shadow: 0 1px 0 {GOLD}55;"
    ):
        _brand_mark()
        render_login_widget()

    if admin:
        with ui.left_drawer().classes("").style(
            f"background:{ADMIN_DRAWER_BG}; border-right: 1px solid {BORDER};"
        ):
            _render_upload_panel()
    elif cohort:
        with ui.left_drawer().classes("bg-white").style(f"border-right: 1px solid {BORDER};"):
            ui.label(cohort).classes("font-extrabold text-lg mt-1").style(f"color:{INK};")
            ui.label("선택된 기수").classes("text-xs mb-4").style(f"color:{MUTED};")

            def _nav_link(label: str, path: str):
                active = path == current_path
                link = ui.link(label, path).classes(
                    "flex items-center gap-2 py-2 px-3 rounded-lg no-underline mb-1 transition-all"
                    + (" font-bold" if active else "")
                )
                link.style(
                    (
                        f"background:linear-gradient(90deg,{ACCENT_SOFT},transparent); "
                        f"color:{ACCENT}; border-left: 3px solid {ACCENT};"
                    )
                    if active
                    else f"color:{INK}; border-left: 3px solid transparent;"
                )

            for label, path in NAV_ITEMS:
                _nav_link(label, path)

            ui.separator().classes("my-3")
            ui.button(
                "기수 변경",
                on_click=lambda: (_clear_cohort(), ui.navigate.to("/")),
            ).props("flat").classes("w-full").style(f"color:{MUTED};")


def page_header(icon: str, title: str, subtitle: str = "", *, right=None):
    """오른쪽에 부가 컨트롤(예: 챗봇의 무료/유료 토글)을 같이 놓고 싶을 때는
    right에 그 내용을 그리는 콜백을 넘기면 된다."""
    with ui.row().classes("items-center justify-between w-full mb-6 flex-wrap gap-3 kdt-fade-up"):
        with ui.row().classes("items-center gap-3"):
            with ui.element("div").classes(
                "w-12 h-12 min-w-[3rem] rounded-xl flex items-center justify-center text-xl"
            ).style(
                f"background:linear-gradient(135deg,{ACCENT_SOFT},transparent); "
                f"box-shadow: inset 0 0 0 1px {ACCENT}22;"
            ):
                ui.label(icon)
            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-2xl font-extrabold").style(f"color:{INK};")
                if subtitle:
                    ui.label(subtitle).classes("text-sm").style(f"color:{MUTED};")
        if right:
            right()
