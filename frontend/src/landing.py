"""
landing.py
- 기수를 먼저 선택해야 다른 탭(챗봇/일정/오시는길/운영진)이 나타난다.
- 4개 기수 카드를 가로 한 줄에 폭 꽉 채워 나란히 배치한다. 페이지 진입 시 순서대로
  팝인하고, 자리 잡은 뒤에는 각자 다른 리듬으로 은은히 부유한다. 카드를 클릭하면
  그 기수로 화면이 전환된다.
- 이미 기수를 선택한 상태로 "/"에 들어오면 바로 챗봇으로 보낸다. "기수 변경" 버튼만
  선택(+대화기록)을 지우고 여기로 돌아오게 한다 (theme.py의 헤더 네비게이션에서 호출).
- main.py의 ui.sub_pages가 이 함수를 "/" 경로 콘텐츠로 그대로 호출하므로 @ui.page
  데코레이터도, 헤더를 그리는 frame() 호출도 여기서는 하지 않는다(헤더는 root_page에서
  한 번만 그려서 탭을 옮겨 다녀도 깜빡이지 않게 한다).
"""

import os

from nicegui import app, ui

from auth import is_admin
from cohorts import COHORT_LIST, get_cohort
from theme import ACCENT, ACCENT_DARK, GOLD, INK, MUTED

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
  @keyframes kdt-drift {{
    0%   {{ transform: translate(0px, 0px) rotate(0deg); }}
    50%  {{ transform: translate(36px, -26px) rotate(10deg); }}
    100% {{ transform: translate(0px, 0px) rotate(0deg); }}
  }}
  @keyframes kdt-card-in {{
    from {{ opacity: 0; transform: translateY(28px) scale(0.94); }}
    to   {{ opacity: 1; transform: translateY(0) scale(1); }}
  }}
  @keyframes kdt-float {{
    0%, 100% {{ transform: translateY(0px); }}
    50% {{ transform: translateY(-12px); }}
  }}
  .kdt-float-card {{
    opacity: 0;
    position: relative;
    z-index: 1;
    animation: kdt-card-in 0.7s cubic-bezier(.2,.7,.2,1) forwards, kdt-float 6.5s ease-in-out infinite;
    animation-delay: 0.05s, 0.75s;
    transition: transform 0.3s cubic-bezier(.2,.7,.2,1), box-shadow 0.3s ease, border-color 0.3s ease;
  }}
  .kdt-float-card:nth-child(2) {{ animation-delay: 0.15s, 1.35s; animation-duration: 0.7s, 7.2s; }}
  .kdt-float-card:nth-child(3) {{ animation-delay: 0.25s, 1.85s; animation-duration: 0.7s, 6.8s; }}
  .kdt-float-card:nth-child(4) {{ animation-delay: 0.35s, 2.35s; animation-duration: 0.7s, 7.6s; }}
  .kdt-float-card:hover {{
    animation-play-state: paused, paused;
    transform: translateY(-10px) scale(1.045) rotate(-0.6deg);
    box-shadow: 0 24px 48px rgba(200,16,46,0.22), 0 4px 14px rgba(173,138,59,0.15) !important;
    border-color: {ACCENT} !important;
  }}
  .kdt-hero > * {{
    opacity: 0;
    animation: kdt-fade-up 0.7s cubic-bezier(.2,.7,.2,1) forwards;
  }}
  .kdt-hero > *:nth-child(1) {{ animation-delay: 0.05s; }}
  .kdt-hero > *:nth-child(2) {{ animation-delay: 0.16s; }}
  .kdt-hero > *:nth-child(3) {{ animation-delay: 0.28s; }}
  .kdt-hero > *:nth-child(4) {{ animation-delay: 0.40s; }}

  .kdt-highlight-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px;
    border-radius: 999px;
    background: rgba(255,255,255,0.6);
    border: 1px solid {GOLD}40;
    box-shadow: 0 4px 14px rgba(27,31,42,0.05);
    backdrop-filter: blur(6px);
  }}

  .kdt-card-cta {{
    opacity: 0;
    transform: translateY(4px);
    transition: opacity 0.25s ease, transform 0.25s ease;
  }}
  .kdt-float-card:hover .kdt-card-cta {{ opacity: 1; transform: translateY(0); }}

  .kdt-card-index {{
    font-weight: 800;
    letter-spacing: 0.12em;
  }}

  .kdt-logo-badge {{ position: relative; }}
  .kdt-logo-badge::before {{
    content: "";
    position: absolute;
    inset: -10px;
    border-radius: 9999px;
    background: radial-gradient(circle, {ACCENT}26 0%, transparent 70%);
    z-index: -1;
  }}
</style>
"""


def _select(name: str):
    app.storage.user["selected_cohort"] = name
    app.storage.user["chat_messages"] = []
    # 기수 선택은 헤더(상단바 로고·네비게이션)가 바뀌어야 하는 상태 변경이라, ui.sub_pages의
    # 소프트 전환 대신 진짜 새로고침으로 넘어간다 - 그래야 프레임이 새 상태로 다시 그려진다.
    ui.run_javascript("window.location.href = '/chat'")


def landing():
    # 관리자는 기수 개념과 무관하게 항상 챗봇+업로드 화면으로 바로 들어간다.
    if is_admin() or app.storage.user.get("selected_cohort"):
        ui.run_javascript("window.location.href = '/chat'")
        return

    ui.add_head_html(_FLOAT_CSS)

    ui.element("div").classes("kdt-blob").style(
        f"width:520px; height:520px; top:-180px; left:-180px; background:{ACCENT}; "
        f"opacity:0.10; animation: kdt-drift 20s ease-in-out infinite;"
    )
    ui.element("div").classes("kdt-blob").style(
        f"width:460px; height:460px; bottom:-160px; right:-160px; background:{ACCENT}; "
        f"opacity:0.08; animation: kdt-drift 24s ease-in-out infinite reverse;"
    )
    ui.element("div").classes("kdt-blob").style(
        f"width:320px; height:320px; top:38%; left:50%; background:{GOLD}; "
        f"opacity:0.07; animation: kdt-drift 16s ease-in-out infinite; animation-delay: -4s;"
    )

    with ui.column().classes(
        "w-full items-center justify-center gap-8 px-4 py-6 relative"
    ).style(
        # 헤더(~61px) + .nicegui-content 상하 패딩(40px+72px, theme.py 전역 스타일)만큼을
        # 빼야 화면 안에 딱 맞아서 기수 선택 페이지에서 세로 스크롤이 안 생긴다.
        "z-index:1; min-height: calc(100vh - 173px);"
    ):
        with ui.column().classes("items-center gap-2 text-center kdt-hero"):
            ui.label("KYUNGPOOK NATIONAL UNIVERSITY").classes("kdt-kicker")
            ui.label("AI·빅데이터 전문가 양성과정").classes("kdt-serif text-4xl md:text-5xl font-extrabold").style(
                f"color:{INK};"
            )
            ui.label("소속된 기수를 선택해주세요").classes("text-base mt-1").style(f"color:{MUTED};")
            ui.element("div").classes("w-14 h-[3px] rounded-full mt-3").style(
                f"background:linear-gradient(90deg,{ACCENT},{GOLD});"
            )

        with ui.row().classes("gap-3 flex-wrap justify-center kdt-fade-up").style("animation-delay: 0.5s;"):
            for icon, text in [
                ("school", "6개월 심화 실무 과정"),
                ("payments", "교육비 전액 국비 지원"),
                ("verified", "경북대학교 수료증 발급"),
            ]:
                with ui.row().classes("kdt-highlight-pill items-center"):
                    ui.icon(icon, size="16px").style(f"color:{ACCENT};")
                    ui.label(text).classes("text-xs font-bold").style(f"color:{INK};")

        # overflow-x-auto만 줘도 CSS 스펙상 overflow-y가 auto로 강제 승격돼서, 카드가
        # 위로 떠오르는 애니메이션의 윗부분이 잘려 보였다. 가로 스크롤 안전장치보다
        # 이 클리핑 버그가 더 커서, overflow 자체를 없애고 카드 폭 축소(min-w-0)로만 방어한다.
        with ui.row().classes("w-full max-w-5xl gap-10 flex-nowrap px-1 justify-center py-4"):
            for i, name in enumerate(COHORT_LIST):
                data = get_cohort(name)
                with ui.card().classes(
                    "kdt-float-card items-stretch text-center p-0 flex-1 min-w-0 cursor-pointer overflow-hidden"
                ).on("click", lambda name=name: _select(name)):
                    with ui.row().classes("w-full items-center justify-between px-4 py-2").style(
                        f"background:linear-gradient(90deg,{ACCENT},{ACCENT_DARK});"
                    ):
                        ui.label(f"{i + 1:02d}").classes("kdt-card-index text-xs font-bold").style(
                            "color:rgba(255,255,255,0.75);"
                        )
                        ui.icon("north_east", size="14px").style("color:rgba(255,255,255,0.75);")
                    with ui.column().classes("items-center text-center px-9 pt-7 pb-8 gap-0 w-full"):
                        logo_path = os.path.join(ASSETS_DIR, data["logo"]) if data.get("logo") else None
                        with ui.element("div").classes("kdt-logo-badge mb-3 mx-auto"):
                            with ui.element("div").classes(
                                "w-16 h-16 rounded-2xl flex items-center justify-center text-3xl overflow-hidden"
                            ).style(f"background:{ACCENT}14; box-shadow: inset 0 0 0 1px {GOLD}33;"):
                                if logo_path and os.path.exists(logo_path):
                                    # 파일시스템 경로 대신 /assets 정적 마운트 URL로 넘긴다 - ui.image()에
                                    # 로컬 경로를 그대로 주면 호출마다 동적 라우트를 새로 등록하는데,
                                    # main.py의 캐치올 페이지 라우트가 그보다 먼저 등록돼 있어서 그 뒤에
                                    # 추가되는 동적 라우트가 전부 가려져(404) 로고가 깨지는 문제가 있었다.
                                    ui.image(f"/assets/{data['logo']}").classes("w-full h-full").props(
                                        "fit=cover"
                                    )
                                else:
                                    ui.label(name[:2]).classes("text-2xl font-extrabold").style(
                                        f"color:{ACCENT};"
                                    )
                        ui.label(name).classes("kdt-serif font-extrabold text-xl").style(f"color:{INK};")
                        ui.label(data.get("subtitle", "")).classes("text-sm mt-1").style(f"color:{MUTED};")
                        with ui.row().classes("kdt-card-cta items-center gap-1 mt-4"):
                            ui.label("자세히 보기").classes("text-xs font-bold").style(f"color:{ACCENT};")
                            ui.icon("arrow_forward", size="13px").style(f"color:{ACCENT};")
