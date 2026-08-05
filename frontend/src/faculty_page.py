"""
faculty_page.py
- 사전교육/본교육을 담당하는 교수진을 보여준다. 사진이 없어서 이니셜 배지로 대신한다.
- 프로그램 전체 공통 정보라 기수별로 나누지 않는다.
- 소속/전공 등 상세 정보는 아직 안 받아서 자리표시자로 비워두고, 정보가 오면
  FACULTY 딕셔너리에 채워 넣기만 하면 카드에 그대로 반영되도록 틀을 잡아뒀다.
"""

from nicegui import ui

from theme import ACCENT, BORDER, INK, MUTED, frame, page_header

FACULTY = [
    (
        "사전교육",
        [
            {"name": "조현일", "role": "교수", "affiliation": "", "field": ""},
        ],
    ),
    (
        "본교육",
        [
            {"name": "김소현", "role": "교수", "affiliation": "", "field": ""},
            {"name": "김기석", "role": "교수", "affiliation": "", "field": ""},
            {"name": "배준현", "role": "교수", "affiliation": "", "field": ""},
        ],
    ),
]


def _initials(name: str) -> str:
    return name[-2:] if len(name) >= 2 else name


def _faculty_card(p: dict):
    with ui.card().classes("items-center text-center p-8 w-64"):
        with ui.element("div").classes(
            "w-24 h-24 rounded-full flex items-center justify-center text-3xl font-extrabold mb-4 mx-auto"
        ).style(f"background:{ACCENT}; color:#fff;"):
            ui.label(_initials(p["name"]))
        ui.label(p["name"]).classes("font-extrabold text-lg").style(f"color:{INK};")
        ui.label(p["role"]).classes("text-sm mt-0.5").style(f"color:{ACCENT};")
        ui.element("div").classes("w-8 h-px my-3").style(f"background:{BORDER};")
        ui.label(p.get("affiliation") or "소속 정보 준비 중").classes("text-xs").style(f"color:{MUTED};")
        ui.label(p.get("field") or "담당 분야 준비 중").classes("text-xs mt-1").style(f"color:{MUTED};")


@ui.page("/faculty")
def faculty_page():
    frame(current_path="/faculty")
    page_header("👩‍🏫", "교수진", "사전교육/본교육을 담당하는 교수진을 소개합니다.")

    for section_title, people in FACULTY:
        ui.label(section_title).classes("font-extrabold text-base mb-4 mt-2").style(f"color:{ACCENT};")
        with ui.row().classes("gap-6 flex-wrap mb-8"):
            for p in people:
                _faculty_card(p)
