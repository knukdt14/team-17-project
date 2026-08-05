"""
landing.py
- 기수를 먼저 선택해야 다른 탭(챗봇/일정/오시는길/강의실사진/관리자)이 나타난다.
- 이미 기수를 선택한 상태로 "/"에 들어오면 바로 챗봇으로 보낸다. "기수 변경" 버튼만
  선택을 지우고 여기로 돌아오게 한다 (theme.py의 좌측 드로어에서 호출).
"""

from nicegui import app, ui

from cohorts import COHORT_LIST, get_cohort
from theme import apply_global_style


def _select(name: str):
    app.storage.user["selected_cohort"] = name
    ui.navigate.to("/chat")


@ui.page("/")
def landing():
    apply_global_style()

    if app.storage.user.get("selected_cohort"):
        ui.navigate.to("/chat")
        return

    with ui.column().classes("w-full max-w-2xl mx-auto px-4 py-10 items-center gap-0"):
        with ui.element("div").classes(
            "w-full text-center rounded-[28px] px-6 py-11 mb-7 shadow-lg"
        ).style("background: linear-gradient(135deg, #6366F1 0%, #8B5CF6 100%);"):
            ui.label("🎓").classes("text-5xl")
            ui.label("KDT 챗봇").classes("text-white text-3xl font-extrabold mt-2")
            ui.label("소속된 기수를 선택해주세요").classes("text-white/90 mt-1")

        with ui.grid(columns=2).classes("w-full gap-4"):
            for name in COHORT_LIST:
                data = get_cohort(name)
                with ui.card().classes(
                    "items-center text-center p-5 cursor-pointer hover:shadow-lg "
                    "hover:border-indigo-400 border border-transparent transition-all"
                ).on("click", lambda name=name: _select(name)):
                    with ui.element("div").classes(
                        "w-13 h-13 rounded-2xl bg-indigo-50 flex items-center justify-center text-2xl mb-2"
                    ):
                        ui.label(data.get("icon", "🎓"))
                    ui.label(name).classes("font-extrabold text-base")
                    ui.label(data.get("subtitle", "")).classes("text-gray-500 text-xs")
                    ui.button("선택", on_click=lambda name=name: _select(name)).props(
                        "unelevated color=primary"
                    ).classes("w-full mt-3 rounded-xl")
