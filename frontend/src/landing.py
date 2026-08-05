"""
landing.py
- 기수를 먼저 선택해야 다른 탭(챗봇/일정/오시는길/교수진)이 나타난다.
- 4개 기수 카드가 은은하게 부유하다가, 카드를 클릭하면 그 기수로 화면이 전환된다.
- 이미 기수를 선택한 상태로 "/"에 들어오면 바로 챗봇으로 보낸다. "기수 변경" 버튼만
  선택을 지우고 여기로 돌아오게 한다 (theme.py의 좌측 드로어에서 호출).
"""

from nicegui import app, ui

from cohorts import COHORT_LIST, get_cohort
from theme import ACCENT, INK, MUTED

_FLOAT_CSS = f"""
<style>
  @keyframes kdt-float {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-12px); }}
  }}
  .kdt-float-card {{
    animation: kdt-float 6.5s ease-in-out infinite;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
  }}
  .kdt-float-card:nth-child(2) {{ animation-delay: -1.6s; animation-duration: 7.2s; }}
  .kdt-float-card:nth-child(3) {{ animation-delay: -3.2s; animation-duration: 6.8s; }}
  .kdt-float-card:nth-child(4) {{ animation-delay: -4.8s; animation-duration: 7.6s; }}
  .kdt-float-card:hover {{
    animation-play-state: paused;
    transform: translateY(-8px) scale(1.04);
    box-shadow: 0 20px 40px rgba(200,16,46,0.18) !important;
    border-color: {ACCENT} !important;
  }}
</style>
"""


def _select(name: str):
    app.storage.user["selected_cohort"] = name
    ui.navigate.to("/chat")


@ui.page("/")
def landing():
    ui.colors(primary=ACCENT)
    ui.add_head_html(_FLOAT_CSS)

    if app.storage.user.get("selected_cohort"):
        ui.navigate.to("/chat")
        return

    with ui.column().classes("w-full min-h-screen items-center justify-center gap-12 px-4 py-10").style(
        "background: radial-gradient(circle at 50% 0%, #FFF1F2 0%, #FAFAFA 55%);"
    ):
        with ui.column().classes("items-center gap-2 text-center"):
            ui.label("KDT AI·빅데이터 전문가 양성과정").classes("text-3xl font-extrabold").style(f"color:{INK};")
            ui.label("소속된 기수를 선택해주세요").classes("text-base").style(f"color:{MUTED};")
            ui.element("div").classes("w-12 h-1 rounded-full mt-2").style(f"background:{ACCENT};")

        with ui.row().classes("gap-7 flex-wrap justify-center max-w-4xl"):
            for name in COHORT_LIST:
                data = get_cohort(name)
                with ui.card().classes(
                    "kdt-float-card items-center text-center p-7 w-52 cursor-pointer"
                ).on("click", lambda name=name: _select(name)):
                    with ui.element("div").classes(
                        "w-14 h-14 rounded-2xl flex items-center justify-center text-2xl mb-3 mx-auto"
                    ).style(f"background:{ACCENT}14;"):
                        ui.label(data.get("icon", "🎓"))
                    ui.label(name).classes("font-extrabold text-lg").style(f"color:{INK};")
                    ui.label(data.get("subtitle", "")).classes("text-xs mt-1").style(f"color:{MUTED};")
