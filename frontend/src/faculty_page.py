"""
faculty_page.py
- 사전교육/본교육을 담당하는 교수진을 보여준다. 사진이 없어서 이니셜 배지로 대신한다.
- 프로그램 전체 공통 정보라 기수별로 나누지 않는다.
"""

from nicegui import ui

from theme import ACCENT, INK, MUTED, frame, page_header

FACULTY = [
    ("사전교육", [{"name": "조현일", "role": "교수"}]),
    (
        "본교육",
        [
            {"name": "김소현", "role": "교수"},
            {"name": "김기석", "role": "교수"},
            {"name": "배준현", "role": "교수"},
        ],
    ),
]


def _initials(name: str) -> str:
    return name[-2:] if len(name) >= 2 else name


@ui.page("/faculty")
def faculty_page():
    frame(current_path="/faculty")
    page_header("👩‍🏫", "교수진", "사전교육/본교육을 담당하는 교수진을 소개합니다.")

    for section_title, people in FACULTY:
        ui.label(section_title).classes("font-extrabold text-sm mb-3 mt-2").style(f"color:{ACCENT};")
        with ui.row().classes("gap-4 flex-wrap mb-6"):
            for p in people:
                with ui.card().classes("items-center text-center p-5 w-40"):
                    with ui.element("div").classes(
                        "w-16 h-16 rounded-full flex items-center justify-center text-lg font-extrabold mb-2 mx-auto"
                    ).style(f"background:{ACCENT}; color:#fff;"):
                        ui.label(_initials(p["name"]))
                    ui.label(p["name"]).classes("font-bold text-sm").style(f"color:{INK};")
                    ui.label(p["role"]).classes("text-xs").style(f"color:{MUTED};")
