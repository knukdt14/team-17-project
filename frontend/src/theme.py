"""
theme.py
- 앱 전체 브랜드 컬러 / 헤더 / 좌측 네비게이션(드로어)을 한 곳에서 관리한다.
- 경북대 데이터융복합연구원 사이트 톤(화이트 배경 + 레드 포인트 + 카드형 그리드)을 참고해서,
  Streamlit 시절의 인디고 그라데이션 톤 대신 절제된 기관형 톤으로 바꿨다.
  실제 KNU 로고 이미지는 쓸 수 없어서, 로고 대신 레드 마크 + 텍스트 워드마크로 그 느낌만 가져온다.
- frame()이 모든 페이지 공통 뼈대(헤더+드로어)를 그리고, 각 페이지는 그 아래 본문만 채우면 된다.
"""

from nicegui import app, ui

from auth import is_admin, render_login_widget

ACCENT = "#C8102E"
ACCENT_SOFT = "#C8102E14"
INK = "#1F2937"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
BG = "#FAFAFA"

NAV_ITEMS = [
    ("💬", "챗봇", "/chat"),
    ("📅", "일정", "/schedule"),
    ("📍", "오시는길", "/map"),
    ("👩‍🏫", "교수진", "/faculty"),
]


def apply_global_style():
    ui.colors(primary=ACCENT, secondary=INK)
    ui.add_head_html(
        f"""
        <style>
          body {{ background: {BG} !important; }}
          .q-card {{
            border-radius: 14px !important;
            border: 1px solid {BORDER} !important;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
          }}
          .q-menu {{ border-radius: 12px !important; }}
          .q-message-text--sent, .q-message-text--sent > div {{
            background: {ACCENT} !important; color: #fff !important;
          }}
          .q-message-text--received, .q-message-text--received > div {{
            background: #F3F4F6 !important; color: {INK} !important;
          }}
          .q-message-name {{ color: {MUTED} !important; font-weight: 600 !important; font-size: 0.75rem !important; }}
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
        ui.element("div").classes("w-2.5 h-8 rounded-sm").style(f"background:{ACCENT};")
        with ui.column().classes("gap-0"):
            ui.label("KDT AI·빅데이터").classes("font-extrabold text-base leading-tight").style(f"color:{INK};")
            ui.label("경북대학교 데이터융복합연구원").classes("text-[11px] leading-tight").style(f"color:{MUTED};")


def frame(current_path: str = ""):
    """헤더(브랜드+로그인) + 기수 선택 후에만 보이는 좌측 네비게이션 드로어를 그린다."""
    apply_global_style()
    cohort = app.storage.user.get("selected_cohort")

    with ui.header().classes("items-center justify-between bg-white px-6 py-3").style(
        f"border-bottom: 3px solid {ACCENT};"
    ):
        _brand_mark()
        render_login_widget()

    if cohort:
        with ui.left_drawer().classes("bg-white").style(f"border-right: 1px solid {BORDER};"):
            ui.label(cohort).classes("font-extrabold text-lg mt-1").style(f"color:{INK};")
            ui.label("선택된 기수").classes("text-xs mb-4").style(f"color:{MUTED};")

            def _nav_link(icon: str, label: str, path: str):
                active = path == current_path
                link = ui.link(f"{icon}  {label}", path).classes(
                    "flex items-center gap-2 py-2 px-3 rounded-lg no-underline mb-1"
                    + (" font-bold" if active else "")
                )
                link.style(f"background:{ACCENT_SOFT}; color:{ACCENT};" if active else f"color:{INK};")

            for icon, label, path in NAV_ITEMS:
                _nav_link(icon, label, path)
            if is_admin():
                _nav_link("🛠️", "관리자", "/admin")

            ui.separator().classes("my-3")
            ui.button(
                "기수 변경",
                on_click=lambda: (_clear_cohort(), ui.navigate.to("/")),
            ).props("flat").classes("w-full").style(f"color:{MUTED};")


def page_header(icon: str, title: str, subtitle: str = "", action=None):
    """action을 넘기면 제목은 왼쪽, 그 콜백이 그리는 내용(보통 버튼 하나)은 같은 줄 오른쪽 끝에
    분리돼서 나온다 (제목=주인공, action=보조 기능이라는 위계를 시각적으로 구분하기 위함)."""
    with ui.row().classes("items-center justify-between gap-3 mb-6 w-full flex-wrap"):
        with ui.row().classes("items-center gap-3"):
            with ui.element("div").classes(
                "w-12 h-12 min-w-[3rem] rounded-xl flex items-center justify-center text-xl"
            ).style(f"background:{ACCENT_SOFT};"):
                ui.label(icon)
            with ui.column().classes("gap-0"):
                ui.label(title).classes("text-2xl font-extrabold").style(f"color:{INK};")
                if subtitle:
                    ui.label(subtitle).classes("text-sm").style(f"color:{MUTED};")
        if action:
            action()
