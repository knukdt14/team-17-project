"""
landing.py
- 기수를 먼저 선택해야 다른 탭(챗봇/일정/오시는길/교수진)이 나타난다.
- 4개 기수 카드를 가로 한 줄에 폭 꽉 채워 나란히 배치하고 은은하게 부유시키다가,
  카드를 클릭하면 그 기수로 화면이 전환된다.
- 이미 기수를 선택한 상태로 "/"에 들어오면 바로 챗봇으로 보낸다. "기수 변경" 버튼만
  선택(+대화기록)을 지우고 여기로 돌아오게 한다 (theme.py의 좌측 드로어에서 호출).
"""

import os

from nicegui import app, ui

from auth import is_admin
from cohorts import COHORT_LIST, get_cohort
from theme import ACCENT, INK, MUTED, frame

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")

_FLOAT_CSS = f"""
<style>
  .kdt-blob {{
    position: fixed;
    border-radius: 9999px;
    filter: blur(90px);
    z-index: 0;
    pointer-events: none;
  }}
  @keyframes kdt-float {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-12px); }}
  }}
  .kdt-float-card {{
    animation: kdt-float 6.5s ease-in-out infinite;
    transition: transform 0.25s ease, box-shadow 0.25s ease;
    position: relative;
    z-index: 1;
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
    # 관리자는 기수 개념과 무관하게 항상 챗봇+업로드 화면으로 바로 들어간다.
    if is_admin() or app.storage.user.get("selected_cohort"):
        ui.navigate.to("/chat")
        return

    frame(current_path="/")
    ui.add_head_html(_FLOAT_CSS)

    ui.element("div").classes("kdt-blob").style(
        f"width:480px; height:480px; top:-160px; left:-160px; background:{ACCENT}; opacity:0.10;"
    )
    ui.element("div").classes("kdt-blob").style(
        f"width:420px; height:420px; bottom:-140px; right:-140px; background:{ACCENT}; opacity:0.08;"
    )

    with ui.column().classes(
        "w-full items-center justify-center gap-16 px-4 py-24 relative min-h-[85vh]"
    ).style("z-index:1;"):
        with ui.column().classes("items-center gap-2 text-center"):
            ui.label("KDT AI·빅데이터 전문가 양성과정").classes("text-3xl font-extrabold").style(f"color:{INK};")
            ui.label("소속된 기수를 선택해주세요").classes("text-base").style(f"color:{MUTED};")
            ui.element("div").classes("w-12 h-1 rounded-full mt-2").style(f"background:{ACCENT};")

        with ui.row().classes("w-full max-w-5xl gap-10 flex-nowrap overflow-x-auto px-1 justify-center"):
            for name in COHORT_LIST:
                data = get_cohort(name)
                with ui.card().classes(
                    "kdt-float-card items-center text-center p-9 flex-1 min-w-0 cursor-pointer"
                ).on("click", lambda name=name: _select(name)):
                    logo_path = os.path.join(ASSETS_DIR, data["logo"]) if data.get("logo") else None
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-2xl flex items-center justify-center text-3xl mb-3 mx-auto overflow-hidden"
                    ).style(f"background:{ACCENT}14;"):
                        if logo_path and os.path.exists(logo_path):
                            ui.image(logo_path).classes("w-full h-full").props("fit=cover")
                        else:
                            ui.label(data.get("icon", "🎓"))
                    ui.label(name).classes("font-extrabold text-xl").style(f"color:{INK};")
                    ui.label(data.get("subtitle", "")).classes("text-sm mt-1").style(f"color:{MUTED};")
