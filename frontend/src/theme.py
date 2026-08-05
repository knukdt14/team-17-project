"""
theme.py
- 앱 전체 브랜드 컬러 / 헤더 / 좌측 네비게이션(드로어)을 한 곳에서 관리한다.
- frame()이 모든 페이지 공통 뼈대(헤더+드로어)를 그리고, 각 페이지는 그 아래 본문만 채우면 된다.
"""

from nicegui import app, ui

from auth import is_admin, render_login_widget

ACCENT = "#6366F1"
ACCENT_2 = "#8B5CF6"

NAV_ITEMS = [
    ("💬", "챗봇", "/chat"),
    ("📅", "일정", "/schedule"),
    ("📍", "오시는길", "/map"),
    ("🏫", "강의실 사진", "/classroom"),
]


def apply_global_style():
    ui.colors(primary=ACCENT, secondary=ACCENT_2)
    ui.add_head_html(
        """
        <style>
          body {
            background: linear-gradient(180deg, #F3F1FF 0%, #FAFAFF 45%, #FFFFFF 100%) !important;
          }
          .q-card, .q-menu { border-radius: 16px !important; }
          .q-chat-message__text--sent { background: linear-gradient(135deg, #6366F1, #8B5CF6) !important; }
        </style>
        """
    )


def _clear_cohort():
    app.storage.user["selected_cohort"] = None


def frame(current_path: str = ""):
    """헤더(브랜드+로그인) + 기수 선택 후에만 보이는 좌측 네비게이션 드로어를 그린다."""
    apply_global_style()
    cohort = app.storage.user.get("selected_cohort")

    with ui.header().classes("items-center justify-between bg-white text-gray-800 shadow-sm px-4 py-2"):
        with ui.row().classes("items-center gap-2"):
            ui.label("🎓").classes("text-2xl")
            ui.label("KDT 규정집 챗봇").classes("font-extrabold text-lg")
        render_login_widget()

    if cohort:
        with ui.left_drawer().classes("bg-indigo-50"):
            ui.label(f"📌 현재 기수 · {cohort}").classes(
                "font-bold text-white bg-gradient-to-r from-indigo-500 to-purple-500 "
                "rounded-xl px-3 py-2 mb-3 w-full"
            )
            for icon, label, path in NAV_ITEMS:
                active = path == current_path
                ui.link(f"{icon}  {label}", path).classes(
                    "block py-2 px-3 rounded-lg no-underline mb-1 "
                    + ("bg-indigo-100 text-indigo-700 font-bold" if active else "text-gray-700 hover:bg-indigo-100")
                )
            if is_admin():
                active = current_path == "/admin"
                ui.link("🛠️  관리자", "/admin").classes(
                    "block py-2 px-3 rounded-lg no-underline mb-1 "
                    + ("bg-indigo-100 text-indigo-700 font-bold" if active else "text-gray-700 hover:bg-indigo-100")
                )
            ui.separator().classes("my-2")
            ui.button(
                "기수 변경",
                on_click=lambda: (_clear_cohort(), ui.navigate.to("/")),
            ).props("flat").classes("w-full text-gray-600")


def page_header(icon: str, title: str, subtitle: str = ""):
    with ui.row().classes("items-center gap-3 mb-5"):
        with ui.element("div").classes(
            "w-14 h-14 min-w-[3.5rem] rounded-2xl bg-indigo-50 flex items-center justify-center text-2xl shadow-sm"
        ):
            ui.label(icon)
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-2xl font-extrabold text-gray-800")
            if subtitle:
                ui.label(subtitle).classes("text-gray-500 text-sm")
