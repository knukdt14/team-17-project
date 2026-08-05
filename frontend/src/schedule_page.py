"""
schedule_page.py
- 선택한 기수의 교육기간/장소/모집기간/혜택/문의를 보여주는 정적 페이지.
- model을 거치지 않고 cohorts.py의 데이터를 그대로 표시한다.
"""

from nicegui import app, ui

from cohorts import get_cohort
from theme import frame, page_header


@ui.page("/schedule")
def schedule_page():
    frame(current_path="/schedule")

    cohort = app.storage.user.get("selected_cohort")
    data = get_cohort(cohort)
    if not data:
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        return

    page_header("📅", f"{cohort} 교육 일정", data.get("title", ""))

    def _section(title: str, rows: dict | None = None, text: str | None = None, items: list | None = None):
        ui.label(title).classes(
            "text-indigo-600 font-extrabold text-base mt-5 mb-2 border-b-2 border-indigo-100 pb-1"
        )
        if rows:
            for label, value in rows.items():
                ui.markdown(f"**{label}** · {value}")
        if text:
            ui.markdown(text)
        if items:
            for it in items:
                ui.markdown(f"- {it}")

    _section("교육 기간", rows=data.get("period", {}))
    _section("교육 장소", rows=data.get("location", {}))
    _section("모집 기간", text=data.get("apply_period", "정보 없음"))

    benefits = data.get("benefits", [])
    if benefits:
        _section("참여 혜택", items=benefits)

    contact = data.get("contact", {})
    if contact:
        _section("교육 문의", rows=contact)

    ui.separator().classes("my-4")
    ui.label("※ 위 일정은 모집공고 기준이며, 운영 상황에 따라 변경될 수 있습니다.").classes(
        "text-gray-400 text-xs"
    )
