"""
faculty_page.py
- 사전교육/본교육을 담당하는 교수진을 보여준다. 사진이 없어서 이니셜 배지로 대신한다.
- 프로그램 전체 공통 정보라 기수별로 나누지 않는다.
- 소속/담당 분야는 정확한 정보를 받기 전까지 임의로 채워둔 placeholder다.
"""

from nicegui import ui

from theme import ACCENT, BORDER, INK, MUTED, frame, page_header

FACULTY = [
    (
        "사전교육",
        [
            {
                "name": "조현일",
                "role": "교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "프로그래밍 기초 및 데이터 분석",
            },
        ],
    ),
    (
        "본교육",
        [
            {
                "name": "김소현",
                "role": "교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "머신러닝 · 데이터 시각화",
            },
            {
                "name": "김기석",
                "role": "교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "딥러닝 · 백엔드 개발",
                "github": "https://github.com/ladofa",
            },
            {
                "name": "배준현",
                "role": "교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "클라우드 · MLOps",
                "github": "https://github.com/joonion",
            },
        ],
    ),
]


def _initials(name: str) -> str:
    return name[-2:] if len(name) >= 2 else name


def _faculty_card(p: dict):
    with ui.card().classes(
        "items-center text-center p-8 w-64 transition-all hover:-translate-y-1.5"
    ).style("cursor: default;"):
        with ui.element("div").classes(
            "w-24 h-24 rounded-full flex items-center justify-center text-3xl font-extrabold mb-4 mx-auto"
        ).style(f"background:{ACCENT}; color:#fff;"):
            ui.label(_initials(p["name"]))
        ui.label(p["name"]).classes("font-extrabold text-lg").style(f"color:{INK};")
        ui.label(p["role"]).classes("text-sm mt-0.5").style(f"color:{ACCENT};")
        ui.element("div").classes("w-8 h-px my-3").style(f"background:{BORDER};")
        ui.label(p.get("affiliation") or "소속 정보 준비 중").classes("text-xs").style(f"color:{MUTED};")
        ui.label(p.get("field") or "담당 분야 준비 중").classes("text-xs mt-1").style(f"color:{MUTED};")
        github = p.get("github")
        if github:
            ui.link("GitHub ↗", github, new_tab=True).classes("text-xs mt-3 font-bold").style(
                f"color:{ACCENT};"
            )


@ui.page("/faculty")
def faculty_page():
    frame(current_path="/faculty")
    page_header("groups", "교수진", "사전교육/본교육을 담당하는 교수진을 소개합니다.")

    for section_title, people in FACULTY:
        ui.label(section_title).classes("font-extrabold text-base mb-4 mt-2").style(f"color:{ACCENT};")
        with ui.row().classes("gap-6 flex-wrap mb-8 kdt-stagger"):
            for p in people:
                _faculty_card(p)
