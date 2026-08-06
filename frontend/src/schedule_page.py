"""
schedule_page.py
- 선택한 기수의 교육기간/장소/모집기간/혜택/문의를 타임라인 + 카드 형태로 보여준다.
- model을 거치지 않고 cohorts.py의 데이터를 그대로 표시한다.
- main.py의 ui.sub_pages가 이 함수를 "/schedule" 콘텐츠로 호출하므로 @ui.page 데코레이터와
  frame() 호출은 여기서 하지 않는다(헤더는 root_page에서 한 번만 그린다).
"""

from nicegui import app, ui

from cohorts import get_cohort, get_posters
from theme import ACCENT, ACCENT_DARK, ACCENT_SOFT, BORDER, GOLD, INK, MUTED, page_header


def schedule_page():
    cohort = app.storage.user.get("selected_cohort")
    data = get_cohort(cohort)
    if not data:
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        return

    def _intro_button():
        ui.button(
            f"{cohort} 소개 보기",
            icon="auto_stories",
            on_click=lambda: ui.navigate.to("/intro"),
        ).props("unelevated no-caps color=primary")

    page_header(
        "event",
        f"{cohort} 교육 일정",
        data.get("title", ""),
        kicker="PROGRAM SCHEDULE",
        right=_intro_button if get_posters(cohort) else None,
    )

    period = data.get("period", {})
    location = data.get("location", {})
    steps = []
    if "사전교육" in period:
        steps.append(("사전교육", period.get("사전교육"), location.get("사전교육")))
    if "정규교육" in period:
        steps.append(("본교육", period.get("정규교육"), location.get("본교육") or location.get("정규교육")))
    steps.append(("수료", "전 과정 이수 후 수료증 발급", None))

    with ui.column().classes("w-full gap-0 mb-6 p-6 kdt-fade-up").style(
        f"background:linear-gradient(160deg,{ACCENT_SOFT},transparent 60%); "
        f"border:1px solid {BORDER}; border-radius:18px;"
    ):
        for i, (label, period_text, loc_text) in enumerate(steps):
            is_last = i == len(steps) - 1
            with ui.row().classes("w-full gap-4 items-stretch"):
                with ui.column().classes("items-center gap-0 w-8"):
                    with ui.element("div").classes(
                        "w-8 h-8 rounded-full flex items-center justify-center text-xs font-extrabold"
                    ).style(
                        f"background:linear-gradient(135deg,{ACCENT},{ACCENT_DARK}); color:#fff; "
                        f"box-shadow: 0 0 0 4px #fff, 0 4px 10px rgba(200,16,46,0.25);"
                    ):
                        ui.label(str(i + 1))
                    if not is_last:
                        ui.element("div").classes("w-0.5 flex-grow mt-1").style(
                            f"background:linear-gradient(180deg,{ACCENT}55,{BORDER});"
                        )
                with ui.column().classes("pb-8 gap-1"):
                    ui.label(label).classes("kdt-serif font-extrabold text-lg").style(f"color:{INK};")
                    if period_text:
                        ui.label(period_text).classes("text-sm").style(f"color:{MUTED};")
                    if loc_text:
                        with ui.row().classes("items-center gap-1 flex-nowrap"):
                            ui.icon("place", size="15px").style(f"color:{GOLD};")
                            ui.label(loc_text).classes("text-sm").style(f"color:{INK};")

    with ui.grid(columns=2).classes("w-full gap-4 kdt-stagger kdt-reveal"):
        with ui.card().classes("p-5"):
            with ui.row().classes("items-center gap-2 mb-2"):
                with ui.element("div").classes("w-8 h-8 rounded-lg flex items-center justify-center").style(
                    f"background:{ACCENT_SOFT};"
                ):
                    ui.icon("event_available", size="16px").style(f"color:{ACCENT};")
                ui.label("모집 기간").classes("font-bold text-sm").style(f"color:{INK};")
            ui.label(data.get("apply_period", "정보 없음")).classes("text-sm").style(f"color:{MUTED};")
        contact = data.get("contact", {})
        homepage = data.get("homepage")
        if contact or homepage:
            with ui.card().classes("p-5"):
                with ui.row().classes("items-center gap-2 mb-2"):
                    with ui.element("div").classes(
                        "w-8 h-8 rounded-lg flex items-center justify-center"
                    ).style(f"background:{ACCENT_SOFT};"):
                        ui.icon("support_agent", size="16px").style(f"color:{ACCENT};")
                    ui.label("교육 문의").classes("font-bold text-sm").style(f"color:{INK};")
                for k, v in contact.items():
                    ui.label(f"{k} · {v}").classes("text-sm").style(f"color:{MUTED};")
                if homepage:
                    with ui.row().classes("items-center gap-1 mt-1"):
                        ui.icon("open_in_new", size="13px").style(f"color:{ACCENT};")
                        ui.link("홈페이지 바로가기", homepage, new_tab=True).classes(
                            "text-sm font-bold no-underline"
                        ).style(f"color:{ACCENT};")

    benefits = data.get("benefits", [])
    if benefits:
        with ui.row().classes("items-center gap-3 mt-8 mb-3"):
            ui.label("참여 혜택").classes("kdt-serif font-extrabold text-lg").style(f"color:{INK};")
            ui.element("div").classes("h-px flex-grow").style(f"background:{BORDER};")
        with ui.column().classes("gap-2.5 kdt-reveal"):
            for b in benefits:
                with ui.row().classes("items-center gap-3 flex-nowrap p-3").style(
                    f"background:#fff; border:1px solid {BORDER}; border-radius:12px;"
                ):
                    with ui.element("div").classes(
                        "w-6 h-6 min-w-[1.5rem] rounded-full flex items-center justify-center"
                    ).style(f"background:{ACCENT};"):
                        ui.icon("check", size="14px").style("color:#fff;")
                    ui.label(b).classes("text-sm flex-grow").style(f"color:{INK};")

    ui.separator().classes("my-5")
    ui.label("※ 위 일정은 모집공고 기준이며, 운영 상황에 따라 변경될 수 있습니다.").classes("text-xs").style(
        f"color:{MUTED};"
    )
