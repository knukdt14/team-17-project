"""
theme.py
- 앱 전체 브랜드 컬러 / 모션(애니메이션) 시스템 / 헤더 / 콘텐츠 레이아웃을 한 곳에서 관리한다.
- "AI 웹디자이너" 컨셉으로 다듬은 톤: 크림슨 레드 + 딥 잉크 + 골드 포인트를 쓰는 기관형
  팔레트에, Gowun Dodum(본문) + Jua(제목/포인트)로 조금 더 친근하고 귀여운 인상을 준다.
  카드/버튼/말풍선에 진입 애니메이션과 호버 인터랙션을 광범위하게 깔아서 Streamlit
  시절의 밋밋한 느낌을 벗어난다.
  헤더 좌측 로고는 기수를 선택하면 그 기수의 연계기업 로고로 바뀌고(_brand_logo_path),
  로고 위에 마우스를 올리면 "KDT AI·빅데이터" 문구 자리에 기수 선택 플라이아웃이 슬라이드
  인되어 바로 다른 기수로 전환할 수 있다.
- 구조적으로도 "좌측 사이드탭 + 우측 본문"이라는 관리자툴/Streamlit식 틀을 버렸다.
  네비게이션은 좌측 드로어가 아니라 헤더 안의 가로 필(pill) 메뉴로 넣고, 본문은
  .nicegui-content에 max-width를 줘서 화면 어디서든 하나의 단(單) 컬럼 콘텐츠 블록처럼
  보이게 한다. 관리자 모드도 세로 사이드바 대신 헤더 바로 아래 가로 콘솔 바 하나로 처리한다.
- 아이콘은 이모지 대신 Quasar/Material 아이콘(ui.icon, icon= prop)만 쓴다.
- frame()이 모든 페이지 공통 뼈대(헤더+콘솔 바)를 그리고, 각 페이지는 그 아래 본문만 채우면 된다.
"""

import os

from nicegui import app, ui

from api_client import ModelServiceError, upload_pdf
from auth import is_admin, render_login_widget
from cohorts import COHORT_LIST, get_cohort

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
KNU_LOGO_PATH = os.path.join(ASSETS_DIR, "logo_13.png")

ACCENT = "#C8102E"
ACCENT_DARK = "#8F0B21"
ACCENT_SOFT = "#C8102E14"
GOLD = "#AD8A3B"
INK = "#1B1F2A"
MUTED = "#6B7280"
BORDER = "#E9E5DD"
BG = "#FAF9F6"
# 관리자로 로그인하면 화면 전체가 살짝 어두워져서 "지금은 일반 화면이 아니다"가 한눈에
# 구분되게 한다.
ADMIN_BG = "#D7DBE2"
ADMIN_CONSOLE_BG = "#20242E"

NAV_ITEMS = [
    ("챗봇", "/chat"),
    ("일정", "/schedule"),
    ("오시는길", "/map"),
    ("운영진", "/faculty"),
]


def apply_global_style():
    ui.colors(primary=ACCENT, secondary=INK)
    body_bg = ADMIN_BG if is_admin() else BG
    ui.add_head_html(
        f"""
        <link rel="preconnect" href="https://fonts.googleapis.com">
        <style>
          @import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Jua&display=swap');

          :root {{
            --kdt-accent: {ACCENT};
            --kdt-accent-dark: {ACCENT_DARK};
            --kdt-gold: {GOLD};
            --kdt-ink: {INK};
            --kdt-muted: {MUTED};
            --kdt-border: {BORDER};
            --kdt-shadow-sm: 0 2px 8px rgba(27,31,42,0.06);
            --kdt-shadow-md: 0 12px 28px rgba(27,31,42,0.10), 0 2px 6px rgba(27,31,42,0.06);
            --kdt-shadow-glow: 0 18px 40px rgba(200,16,46,0.18);
          }}

          html, body, .q-field, .q-btn, .q-card {{
            font-family: 'Gowun Dodum', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
          }}

          .kdt-serif {{ font-family: 'Jua', 'Gowun Dodum', sans-serif !important; }}
          .kdt-kicker {{
            display: block;
            color: {GOLD};
            font-weight: 800;
            font-size: 0.72rem;
            letter-spacing: 0.18em;
            text-transform: uppercase;
          }}

          body {{
            background: {body_bg} !important;
            background-image:
              radial-gradient(circle at 12% 8%, rgba(200,16,46,0.045) 0%, transparent 45%),
              radial-gradient(circle at 88% 92%, rgba(173,138,59,0.05) 0%, transparent 45%);
            background-attachment: fixed;
            position: relative;
          }}

          /* 아주 옅은 그레인 텍스처 - 배경이 밋밋한 단색으로 안 보이게 잡아주는 디테일 */
          body::before {{
            content: "";
            position: fixed;
            inset: 0;
            z-index: 1;
            pointer-events: none;
            opacity: 0.035;
            mix-blend-mode: overlay;
            background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='140' height='140'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>");
          }}

          ::selection {{ background: {ACCENT}; color: #fff; }}

          ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
          ::-webkit-scrollbar-track {{ background: transparent; }}
          ::-webkit-scrollbar-thumb {{
            background: linear-gradient(180deg, {ACCENT}, {ACCENT_DARK});
            border-radius: 999px;
            border: 2px solid {BG};
          }}

          /* ---------- 모션 시스템 ---------- */
          @keyframes kdt-fade-up {{
            from {{ opacity: 0; transform: translateY(14px); }}
            to   {{ opacity: 1; transform: translateY(0); }}
          }}
          @keyframes kdt-fade-in {{
            from {{ opacity: 0; }}
            to   {{ opacity: 1; }}
          }}
          @keyframes kdt-pop-in {{
            0%   {{ opacity: 0; transform: scale(0.94) translateY(8px); }}
            100% {{ opacity: 1; transform: scale(1) translateY(0); }}
          }}
          @keyframes kdt-underline-grow {{
            from {{ width: 0; }}
            to   {{ width: 100%; }}
          }}
          @keyframes kdt-pulse-glow {{
            0%, 100% {{ box-shadow: 0 0 0 0 rgba(200,16,46,0.28); }}
            50%      {{ box-shadow: 0 0 0 8px rgba(200,16,46,0); }}
          }}

          .kdt-fade-up {{ animation: kdt-fade-up 0.6s cubic-bezier(.2,.7,.2,1) both; }}
          .kdt-stagger > * {{ opacity: 0; animation: kdt-pop-in 0.55s cubic-bezier(.2,.7,.2,1) both; }}
          .kdt-stagger > *:nth-child(1) {{ animation-delay: 0.02s; }}
          .kdt-stagger > *:nth-child(2) {{ animation-delay: 0.10s; }}
          .kdt-stagger > *:nth-child(3) {{ animation-delay: 0.18s; }}
          .kdt-stagger > *:nth-child(4) {{ animation-delay: 0.26s; }}
          .kdt-stagger > *:nth-child(5) {{ animation-delay: 0.34s; }}
          .kdt-stagger > *:nth-child(6) {{ animation-delay: 0.42s; }}

          /* ---------- 카드 ---------- */
          .q-card {{
            border-radius: 18px !important;
            border: 1px solid {BORDER} !important;
            box-shadow: var(--kdt-shadow-sm) !important;
            transition: transform 0.28s cubic-bezier(.2,.7,.2,1), box-shadow 0.28s ease, border-color 0.28s ease;
          }}
          .q-card:hover {{
            box-shadow: var(--kdt-shadow-md), 0 0 0 1px {GOLD}40 !important;
            border-color: {GOLD}70 !important;
          }}
          a.no-underline .q-card, .kdt-hover .q-card {{ will-change: transform; }}

          /* ---------- 버튼 ---------- */
          .q-btn {{
            transition: transform 0.18s ease, box-shadow 0.18s ease, filter 0.18s ease !important;
            border-radius: 12px;
          }}
          .q-btn:active {{ transform: scale(0.97); }}
          .q-btn.bg-primary, .q-btn[color=primary] {{
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%) !important;
            position: relative;
            overflow: hidden;
          }}
          /* 프라이머리 버튼에 은은한 샤인이 한 번 스윽 지나가는 호버 효과 */
          .q-btn.bg-primary::after, .q-btn[color=primary]::after {{
            content: "";
            position: absolute;
            top: 0; left: -60%;
            width: 35%; height: 100%;
            background: linear-gradient(115deg, transparent, rgba(255,255,255,0.4), transparent);
            transform: skewX(-20deg);
            transition: left 0.55s ease;
          }}
          .q-btn.bg-primary:hover::after, .q-btn[color=primary]:hover::after {{ left: 130%; }}

          .q-menu {{
            border-radius: 16px !important;
            box-shadow: var(--kdt-shadow-md) !important;
            animation: kdt-pop-in 0.18s ease both;
          }}

          /* ---------- 채팅 말풍선: 새로 생기면 자동으로 슬라이드-인 ---------- */
          .q-message {{ animation: kdt-fade-up 0.4s cubic-bezier(.2,.7,.2,1) both; }}
          .q-message-text--sent, .q-message-text--sent > div {{
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%) !important;
            color: #fff !important;
            box-shadow: 0 6px 16px rgba(200,16,46,0.22);
          }}
          .q-message-text--received, .q-message-text--received > div {{
            background: #FFFFFF !important;
            color: {INK} !important;
            border: 1px solid {BORDER};
            box-shadow: var(--kdt-shadow-sm);
          }}
          .q-message-name {{
            color: {MUTED} !important; font-weight: 700 !important; font-size: 0.72rem !important;
            letter-spacing: 0.02em;
          }}

          /* ---------- 토글(무료/유료) ---------- */
          .q-btn-toggle {{ transition: box-shadow 0.25s ease; }}
          .q-btn-toggle .q-btn {{ transition: background 0.25s ease, color 0.25s ease !important; }}

          /* ---------- 링크 ---------- */
          a {{ transition: color 0.2s ease; }}

          /* ---------- 본문 레이아웃: 좌측 사이드바 없이, 화면 중앙의 단일 컬럼 블록 ---------- */
          .nicegui-content {{
            max-width: 1040px;
            width: 100%;
            margin: 0 auto;
            padding: 40px 28px 72px !important;
            box-sizing: border-box;
          }}
          @media (max-width: 640px) {{
            .nicegui-content {{ padding: 24px 16px 48px !important; }}
          }}

          /* ---------- 헤더 가로 네비게이션 필 ---------- */
          .kdt-navlink {{
            color: {MUTED};
            font-size: 0.86rem;
            position: relative;
          }}
          .kdt-navlink:hover {{ color: {ACCENT}; background: {ACCENT}0d; }}
          .kdt-navlink-active {{
            color: #fff !important;
            background: linear-gradient(135deg, {ACCENT} 0%, {ACCENT_DARK} 100%) !important;
            box-shadow: 0 6px 16px rgba(200,16,46,0.28);
          }}
          .kdt-navlink::after {{
            content: "";
            position: absolute;
            left: 50%; bottom: 2px;
            width: 0; height: 2px;
            background: {GOLD};
            transition: width 0.25s ease, left 0.25s ease;
          }}
          .kdt-navlink:not(.kdt-navlink-active):hover::after {{ width: 60%; left: 20%; }}

          /* ---------- 헤더 로고 호버 시 기수 변경 플라이아웃 ---------- */
          .kdt-brand-text {{
            transition: opacity 0.2s ease, transform 0.2s ease;
          }}
          .kdt-brand:hover .kdt-brand-text {{
            opacity: 0;
            transform: translateX(6px);
          }}
          .kdt-brand-flyout {{
            position: absolute;
            left: 0; top: 50%;
            transform: translateY(-50%) translateX(-6px);
            opacity: 0;
            pointer-events: none;
            background: #fff;
            padding: 4px 6px;
            border-radius: 999px;
            border: 1px solid {GOLD}55;
            box-shadow: var(--kdt-shadow-md);
            transition: opacity 0.22s ease, transform 0.22s ease;
            white-space: nowrap;
            z-index: 60;
          }}
          .kdt-brand:hover .kdt-brand-flyout {{
            opacity: 1;
            transform: translateY(-50%) translateX(0);
            pointer-events: auto;
          }}

          /* ---------- 관리자 콘솔 바 ---------- */
          .kdt-admin-bar {{ animation: kdt-fade-up 0.5s cubic-bezier(.2,.7,.2,1) both; }}
          .kdt-admin-bar .q-field__control {{ background: rgba(255,255,255,0.06) !important; }}

          /* ---------- 스크롤 등장: 화면에 들어올 때 살아나는 요소 ---------- */
          .kdt-reveal {{
            opacity: 0;
            transform: translateY(26px);
            transition: opacity 0.75s cubic-bezier(.2,.7,.2,1), transform 0.75s cubic-bezier(.2,.7,.2,1);
          }}
          .kdt-reveal-in {{ opacity: 1; transform: translateY(0); }}
        </style>
        <script>
          document.addEventListener('DOMContentLoaded', function() {{
            var io = new IntersectionObserver(function(entries) {{
              entries.forEach(function(entry) {{
                if (entry.isIntersecting) {{
                  entry.target.classList.add('kdt-reveal-in');
                  io.unobserve(entry.target);
                }}
              }});
            }}, {{ threshold: 0.12 }});
            function scan(root) {{
              if (!root.querySelectorAll) return;
              root.querySelectorAll('.kdt-reveal:not(.kdt-reveal-in)').forEach(function(el) {{ io.observe(el); }});
            }}
            scan(document);
            new MutationObserver(function(muts) {{
              muts.forEach(function(m) {{
                m.addedNodes.forEach(function(n) {{ if (n.nodeType === 1) scan(n); }});
              }});
            }}).observe(document.body, {{ childList: true, subtree: true }});
          }});
        </script>
        """
    )


def _clear_cohort():
    # 기수를 바꾸면 이전 기수에서 나눴던 대화가 새 기수 화면에 그대로 남아있으면 안 되니
    # 같이 비운다.
    app.storage.user["selected_cohort"] = None
    app.storage.user["chat_messages"] = []


def _switch_cohort(name: str):
    # 헤더 로고 위 호버 플라이아웃에서 바로 기수를 바꿀 때도, 서로 다른 기수의 대화가
    # 섞이지 않도록 _clear_cohort()와 같은 원칙으로 대화 기록을 같이 비운다.
    app.storage.user["selected_cohort"] = name
    app.storage.user["chat_messages"] = []
    ui.navigate.to("/chat")


def _brand_logo_path(cohort: str | None) -> str:
    """상단바 로고: 기수를 선택하면 그 기수의 연계기업 로고로, 아니면 경북대 로고로."""
    if cohort:
        logo = get_cohort(cohort).get("logo")
        if logo:
            path = os.path.join(ASSETS_DIR, logo)
            if os.path.exists(path):
                return path
    return KNU_LOGO_PATH


def _brand_mark():
    cohort = app.storage.user.get("selected_cohort")
    logo_path = _brand_logo_path(cohort)
    with ui.row().classes("items-center gap-3 kdt-brand"):
        ui.element("div").classes("w-1 h-9 rounded-full").style(
            f"background:linear-gradient(180deg,{ACCENT},{GOLD});"
        )
        if os.path.exists(logo_path):
            ui.image(logo_path).classes("w-8 h-8 transition-transform hover:scale-110").props("fit=contain")
        with ui.element("div").classes("relative").style("min-width:180px;"):
            with ui.column().classes("gap-0 kdt-brand-text"):
                ui.label("KDT AI·빅데이터").classes("font-extrabold text-base leading-tight").style(
                    f"color:{INK};"
                )
                ui.label("경북대학교 데이터융복합연구원").classes("text-[11px] leading-tight").style(
                    f"color:{MUTED};"
                )
            if not is_admin():
                with ui.row().classes("kdt-brand-flyout items-center gap-1"):
                    for name in COHORT_LIST:
                        active = name == cohort
                        ui.button(name, on_click=lambda name=name: _switch_cohort(name)).props(
                            ("unelevated color=primary" if active else "flat") + " dense no-caps"
                        ).classes("text-xs")


def _admin_console_bar():
    """관리자 전용 콘솔: 세로 사이드바 대신 헤더 바로 아래 가로로 한 줄 깔아서, 화면
    구조 자체는 일반 모드와 똑같이 "본문 한 덩어리"를 유지한다. PDF를 업로드하면 model이
    청킹 후 벡터DB에 바로 반영하고 디스크에 저장(save_local)해서, 컨테이너를 재시작해도
    남아있다."""
    with ui.row().classes("w-full items-center gap-5 px-6 py-3.5 flex-wrap kdt-admin-bar").style(
        f"background:{ADMIN_CONSOLE_BG};"
    ):
        with ui.row().classes("items-center gap-2"):
            ui.icon("admin_panel_settings").style(f"color:{GOLD}; font-size:1.35rem;")
            ui.label("관리자 모드").classes("font-extrabold text-sm text-white")
        ui.label("PDF를 올리면 벡터DB에 바로 반영되어 챗봇 답변에 곧장 쓰입니다.").classes(
            "text-xs"
        ).style("color:#B7BCC9;")

        status_label = ui.label("").classes("text-xs")

        async def _handle_upload(e):
            content = await e.file.read()
            status_label.text = "업로드 및 반영 중..."
            status_label.style("color:#B7BCC9;")
            try:
                data = await upload_pdf(e.file.name, content)
                status_label.text = f"{data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)"
                status_label.style("color:#4ADE80;")
            except ModelServiceError as err:
                status_label.text = str(err)
                status_label.style("color:#F87171;")

        ui.upload(on_upload=_handle_upload, auto_upload=True, label="PDF 업로드").props(
            "accept=.pdf flat dense dark"
        ).classes("w-64 ml-auto")


def _nav_pills(current_path: str, cohort: str):
    with ui.row().classes("items-center gap-1 flex-wrap"):
        for label, path in NAV_ITEMS:
            active = path == current_path
            ui.link(label, path).classes(
                "kdt-navlink px-4 py-2 rounded-full font-bold no-underline transition-all"
                + (" kdt-navlink-active" if active else "")
            )
        ui.element("div").classes("w-px h-5 mx-1").style(f"background:{BORDER};")
        ui.button(
            cohort,
            icon="swap_horiz",
            on_click=lambda: (_clear_cohort(), ui.navigate.to("/")),
        ).props("flat dense no-caps").classes("text-xs font-bold").style(f"color:{MUTED};")


def frame(current_path: str = ""):
    """헤더(브랜드+네비게이션+로그인)만 공통 뼈대로 그린다. 좌측 사이드바는 없다 -
    네비게이션은 헤더 안의 가로 필 메뉴로, 관리자 콘솔은 헤더 바로 아래 가로 바로 넣어서
    본문은 항상 화면 중앙의 단일 컬럼 블록 하나로 유지된다(.nicegui-content, 좌우 사이드
    패널 없음)."""
    apply_global_style()
    cohort = app.storage.user.get("selected_cohort")
    admin = is_admin()

    with ui.header().classes("items-center justify-between px-6 py-3 gap-4 flex-wrap").style(
        f"background: rgba(255,255,255,0.85); backdrop-filter: blur(10px); "
        f"border-bottom: 1px solid {BORDER}; box-shadow: 0 1px 0 {GOLD}55;"
    ):
        _brand_mark()
        if admin:
            with ui.row().classes("items-center gap-1.5"):
                ui.icon("admin_panel_settings").style(f"color:{ACCENT}; font-size:1.1rem;")
                ui.label("관리자 모드").classes("text-xs font-bold").style(f"color:{ACCENT};")
        elif cohort:
            _nav_pills(current_path, cohort)
        render_login_widget()

    if admin:
        _admin_console_bar()


def page_header(icon: str, title: str, subtitle: str = "", *, kicker: str = "", logo: str | None = None, right=None):
    """오른쪽에 부가 컨트롤(예: 챗봇의 무료/유료 토글)을 같이 놓고 싶을 때는
    right에 그 내용을 그리는 콜백을 넘기면 된다. icon은 이모지가 아니라 Material 아이콘
    이름(예: "forum", "event", "place", "groups")을 받는다. logo를 넘기면 아이콘 대신
    그 이미지를 보여준다(예: 챗봇 페이지의 경북대 로고). kicker는 제목 위에 붙는
    골드색 영문 소문구(예: "PROGRAM SCHEDULE")로, 없으면 생략된다."""
    with ui.row().classes("items-center justify-between w-full mb-6 flex-wrap gap-3 kdt-fade-up"):
        with ui.row().classes("items-center gap-3"):
            with ui.element("div").classes(
                "w-12 h-12 min-w-[3rem] rounded-xl flex items-center justify-center overflow-hidden"
            ).style(
                f"background:linear-gradient(135deg,{ACCENT_SOFT},transparent); "
                f"box-shadow: inset 0 0 0 1px {ACCENT}22;"
            ):
                if logo and os.path.exists(logo):
                    ui.image(logo).classes("w-7 h-7").props("fit=contain")
                else:
                    ui.icon(icon).style(f"color:{ACCENT}; font-size:1.4rem;")
            with ui.column().classes("gap-0"):
                if kicker:
                    ui.label(kicker).classes("kdt-kicker")
                ui.label(title).classes("kdt-serif text-2xl font-extrabold").style(f"color:{INK};")
                if subtitle:
                    ui.label(subtitle).classes("text-sm").style(f"color:{MUTED};")
        if right:
            right()
