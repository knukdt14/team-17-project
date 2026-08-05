"""
schedule_page.py
- 선택한 기수의 교육기간/장소/모집기간/혜택/문의를 타임라인 + 카드 형태로 보여준다.
- model을 거치지 않고 cohorts.py의 데이터를 그대로 표시한다.
"""

from nicegui import app, ui

from cohorts import get_cohort
from theme import ACCENT, BORDER, INK, MUTED, frame, page_header


@ui.page("/schedule")
def schedule_page():
    frame(current_path="/schedule")

    cohort = app.storage.user.get("selected_cohort")
    data = get_cohort(cohort)
    if not data:
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        return

    page_header("📅", f"{cohort} 교육 일정", data.get("title", ""))

    period = data.get("period", {})
    location = data.get("location", {})
    steps = []
    if "사전교육" in period:
        steps.append(("사전교육", period.get("사전교육"), location.get("사전교육")))
    if "정규교육" in period:
        steps.append(("본교육", period.get("정규교육"), location.get("본교육") or location.get("정규교육")))
    steps.append(("수료", "전 과정 이수 후 수료증 발급", None))

    with ui.column().classes("w-full gap-0 mb-2"):
        for i, (label, period_text, loc_text) in enumerate(steps):
            is_last = i == len(steps) - 1
            with ui.row().classes("w-full gap-4 items-stretch"):
                with ui.column().classes("items-center gap-0 w-4"):
                    ui.element("div").classes("w-3.5 h-3.5 rounded-full mt-1").style(
                        f"background:{ACCENT};"
                    )
                    if not is_last:
                        ui.element("div").classes("w-0.5 flex-grow mt-1").style(f"background:{BORDER};")
                with ui.column().classes("pb-7 gap-1"):
                    ui.label(label).classes("font-extrabold text-base").style(f"color:{INK};")
                    if period_text:
                        ui.label(period_text).classes("text-sm").style(f"color:{MUTED};")
                    if loc_text:
                        ui.label(f"📍 {loc_text}").classes("text-sm").style(f"color:{INK};")

    with ui.grid(columns=2).classes("w-full gap-4"):
        with ui.card().classes("p-4"):
            ui.label("모집 기간").classes("font-bold text-sm mb-1").style(f"color:{ACCENT};")
            ui.label(data.get("apply_period", "정보 없음")).classes("text-sm").style(f"color:{INK};")
        contact = data.get("contact", {})
        if contact:
            with ui.card().classes("p-4"):
                ui.label("교육 문의").classes("font-bold text-sm mb-1").style(f"color:{ACCENT};")
                for k, v in contact.items():
                    ui.label(f"{k} · {v}").classes("text-sm").style(f"color:{INK};")

    benefits = data.get("benefits", [])
    if benefits:
        ui.label("참여 혜택").classes("font-extrabold text-base mt-6 mb-2").style(f"color:{INK};")
        with ui.column().classes("gap-1.5"):
            for b in benefits:
                with ui.row().classes("items-start gap-2 flex-nowrap"):
                    ui.label("●").classes("text-xs mt-1").style(f"color:{ACCENT};")
                    ui.label(b).classes("text-sm flex-grow").style(f"color:{INK};")

    ui.separator().classes("my-5")
    ui.label("※ 위 일정은 모집공고 기준이며, 운영 상황에 따라 변경될 수 있습니다.").classes("text-xs").style(
        f"color:{MUTED};"
    )
