"""
faculty_page.py
- 원장/본부장/연구원 등 운영진과, 사전교육/본교육을 담당하는 교수진을 함께 보여준다.
  "교수진"이라는 이름만으로는 운영진까지 아우르지 못해서 탭 이름/제목을 "운영진"으로 바꿨다.
- 사전교육/본교육 담당 교수는 예전엔 섹션을 나눠서 두 줄로 보여줬는데, 한 줄에 같이
  보이도록 "교수진" 한 섹션으로 합치고 담당 단계는 역할 뱃지 문구(예: "사전교육 교수")로 구분한다.
- 사진이 없어서 이니셜 배지로 대신한다. 남성은 파란 계열, 그 외에는 브랜드 레드 계열로
  배지 색을 구분한다. 프로그램 전체 공통 정보라 기수별로 나누지 않는다.
- 소속/담당 분야는 정확한 정보를 받기 전까지 임의로 채워둔 placeholder다.
- main.py의 ui.sub_pages가 이 함수를 "/faculty" 콘텐츠로 호출하므로 @ui.page 데코레이터와
  frame() 호출은 여기서 하지 않는다(헤더는 root_page에서 한 번만 그린다).
"""

from nicegui import ui

from theme import ACCENT, ACCENT_DARK, BORDER, GOLD, INK, MUTED, page_header

BLUE = "#3B65C4"
BLUE_DARK = "#1E3D82"

# 아바타 배지 색을 파란 계열로 보여줄 이름(남성).
MALE_NAMES = {"정태옥", "조현일", "김기석", "배준현"}

FACULTY = [
    (
        "운영진",
        [
            {
                "name": "정태옥",
                "role": "원장",
                "affiliation": "경북대학교 데이터융복합연구원",
                "field": "교육과정 총괄",
            },
            {
                "name": "류승령",
                "role": "본부장",
                "affiliation": "경북대학교 데이터융복합연구원",
                "field": "교육운영 총괄",
            },
            {
                "name": "김효진",
                "role": "연구원",
                "affiliation": "경북대학교 데이터융복합연구원",
                "field": "교육기획 및 운영지원",
            },
        ],
    ),
    (
        "교수진",
        [
            {
                "name": "조현일",
                "role": "사전교육 교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "프로그래밍 기초 및 데이터 분석",
            },
            {
                "name": "김소현",
                "role": "본교육 교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "머신러닝 · 데이터 시각화",
            },
            {
                "name": "김기석",
                "role": "본교육 교수",
                "affiliation": "AI·빅데이터 교육",
                "field": "딥러닝 · 백엔드 개발",
                "github": "https://github.com/ladofa",
            },
            {
                "name": "배준현",
                "role": "본교육 교수",
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
    is_male = p["name"] in MALE_NAMES
    grad_from, grad_to = (BLUE, BLUE_DARK) if is_male else (ACCENT, ACCENT_DARK)
    badge_color = BLUE if is_male else ACCENT

    with ui.card().classes("items-stretch text-center p-0 w-64 overflow-hidden").style("cursor: default;"):
        ui.element("div").classes("w-full h-1.5").style(
            f"background:linear-gradient(90deg,{grad_from},{GOLD});"
        )
        with ui.column().classes("items-center text-center p-8 pt-7 gap-0"):
            with ui.element("div").classes(
                "w-24 h-24 rounded-full flex items-center justify-center text-3xl font-extrabold mb-4 mx-auto"
            ).style(
                f"background:linear-gradient(135deg,{grad_from},{grad_to}); color:#fff; "
                f"box-shadow: 0 0 0 3px #fff, 0 0 0 4px {GOLD}80;"
            ):
                ui.label(_initials(p["name"]))
            ui.label(p["name"]).classes("kdt-serif font-extrabold text-lg").style(f"color:{INK};")
            ui.label(p["role"]).classes(
                "text-[11px] font-bold mt-1.5 px-2.5 py-0.5 rounded-full"
            ).style(f"color:{badge_color}; background:{badge_color}14;")
            ui.element("div").classes("w-8 h-px my-3").style(f"background:{BORDER};")
            ui.label(p.get("affiliation") or "소속 정보 준비 중").classes("text-xs").style(f"color:{MUTED};")
            ui.label(p.get("field") or "담당 분야 준비 중").classes("text-xs mt-1").style(f"color:{MUTED};")
            github = p.get("github")
            if github:
                ui.link("GitHub ↗", github, new_tab=True).classes(
                    "text-xs font-bold mt-3 no-underline"
                ).style(f"color:{badge_color};")


def faculty_page():
    page_header("groups", "운영진", "교육을 이끌어가는 운영진과 교수진을 소개합니다.", kicker="TEAM")

    for section_title, people in FACULTY:
        with ui.row().classes("items-center gap-3 mb-4 mt-2"):
            ui.label(section_title).classes("font-extrabold text-base").style(f"color:{ACCENT};")
            ui.element("div").classes("h-px flex-grow").style(f"background:{BORDER};")
        with ui.row().classes("gap-6 flex-wrap mb-8 kdt-stagger kdt-reveal"):
            for p in people:
                _faculty_card(p)
