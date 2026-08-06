"""
theme.py
- 앱 전체 브랜드 컬러 / 헤더 / 좌측 네비게이션(드로어)을 한 곳에서 관리한다.
- 경북대 데이터융복합연구원 사이트 톤(화이트 배경 + 레드 포인트 + 카드형 그리드)을 참고해서,
  Streamlit 시절의 인디고 그라데이션 톤 대신 절제된 기관형 톤으로 바꿨다.
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
ACCENT_SOFT = "#C8102E14"
INK = "#1F2937"
MUTED = "#6B7280"
BORDER = "#E5E7EB"
BG = "#FAFAFA"
# 관리자로 로그인하면 화면 전체가 살짝 어두워져서 "지금은 일반 화면이 아니다"가 한눈에
# 구분되게 한다.
ADMIN_BG = "#D7DBE2"
ADMIN_DRAWER_BG = "#EEF0F3"

NAV_ITEMS = [
    ("💬", "챗봇", "/chat"),
    ("📅", "일정", "/schedule"),
    ("📍", "오시는길", "/map"),
    ("👩‍🏫", "교수진", "/faculty"),
]


def apply_global_style():
    ui.colors(primary=ACCENT, secondary=INK)
    body_bg = ADMIN_BG if is_admin() else BG
    ui.add_head_html(
        f"""
        <style>
          body {{ background: {body_bg} !important; }}
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
        if os.path.exists(KNU_LOGO_PATH):
            ui.image(KNU_LOGO_PATH).classes("w-8 h-8").props("fit=contain")
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

    with ui.header().classes("items-center justify-between bg-white px-6 py-3").style(
        f"border-bottom: 3px solid {ACCENT};"
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

            def _nav_link(icon: str, label: str, path: str):
                active = path == current_path
                link = ui.link(f"{icon}  {label}", path).classes(
                    "flex items-center gap-2 py-2 px-3 rounded-lg no-underline mb-1"
                    + (" font-bold" if active else "")
                )
                link.style(f"background:{ACCENT_SOFT}; color:{ACCENT};" if active else f"color:{INK};")

            for icon, label, path in NAV_ITEMS:
                _nav_link(icon, label, path)

            ui.separator().classes("my-3")
            ui.button(
                "기수 변경",
                on_click=lambda: (_clear_cohort(), ui.navigate.to("/")),
            ).props("flat").classes("w-full").style(f"color:{MUTED};")


def page_header(icon: str, title: str, subtitle: str = ""):
    with ui.row().classes("items-center gap-3 mb-6"):
        with ui.element("div").classes(
            "w-12 h-12 min-w-[3rem] rounded-xl flex items-center justify-center text-xl"
        ).style(f"background:{ACCENT_SOFT};"):
            ui.label(icon)
        with ui.column().classes("gap-0"):
            ui.label(title).classes("text-2xl font-extrabold").style(f"color:{INK};")
            if subtitle:
                ui.label(subtitle).classes("text-sm").style(f"color:{MUTED};")
