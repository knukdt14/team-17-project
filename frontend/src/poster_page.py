"""
poster_page.py
- 선택한 기수의 소개 포스터/커리큘럼 이미지를 온전히 크게 보여주는 전용 페이지.
- schedule_page.py의 "소개 보기" 링크를 누르면 화면 안에 끼워넣지 않고 여기로 이동한다
  (사진을 작게 욱여넣지 않고 페이지 하나를 통째로 써서 원래 크기 느낌을 살리기 위함).
- 이미지마다 +/- 버튼으로 50%씩 확대/축소할 수 있고, 더블클릭할 때마다 50%씩 더 확대되다가
  최대 배율을 넘으면 100%로 돌아온다. 확대된 상태에서는 마우스로 드래그해서 이동할 수 있다.
- 이미지 위에 마우스가 올라가 있는 동안은 키보드 +/-로도 확대/축소된다.
"""

from nicegui import app, events, ui

from cohorts import get_cohort, get_posters
from theme import ACCENT, MUTED, frame, page_header

_ZOOM_STEP = 0.5
_ZOOM_MIN = 0.5
_ZOOM_MAX = 3.0

# 드래그로 스크롤 이동시키는 JS. mousedown 시점의 좌표/스크롤 위치를 기억해뒀다가,
# mousemove마다 그 차이만큼 scrollLeft/scrollTop을 옮긴다 (지도 앱 등에서 흔한 "손으로 끌기" 패턴).
# 서버로 매 mousemove를 안 보내고 클라이언트 JS에서 전부 처리해야 끊김 없이 부드럽다.
_DRAG_JS = """
(() => {{
  const el = getElement({viewport_id});
  let dragging = false, startX = 0, startY = 0, startLeft = 0, startTop = 0;
  el.addEventListener('mousedown', (e) => {{
    dragging = true;
    startX = e.pageX; startY = e.pageY;
    startLeft = el.scrollLeft; startTop = el.scrollTop;
    el.style.cursor = 'grabbing';
  }});
  window.addEventListener('mouseup', () => {{ dragging = false; el.style.cursor = ''; }});
  el.addEventListener('mouseleave', () => {{ dragging = false; el.style.cursor = ''; }});
  el.addEventListener('mousemove', (e) => {{
    if (!dragging) return;
    e.preventDefault();
    el.scrollLeft = startLeft - (e.pageX - startX);
    el.scrollTop = startTop - (e.pageY - startY);
  }});
}})();
"""


def _zoomable_image(poster: dict):
    # 세로 포스터는 처음부터 적당히 작게, 가로로 넓은 표는 페이지 폭에 맞춰 시작하고,
    # 그 이후 확대/축소는 이 시작 폭을 기준으로 배율만 곱해서 계산한다.
    base_width = min(poster["width"], 520) if poster["portrait"] else min(poster["width"], 900)
    state = {"scale": 1.0, "hover": False}

    with ui.column().classes("w-full items-center gap-2"):
        viewport = ui.element("div").classes("w-full rounded-xl").style(
            "max-height: 75vh; overflow: auto; background:#F3F4F6; "
            "box-shadow: 0 6px 24px rgba(0,0,0,0.15); text-align:center; cursor: grab;"
        )
        viewport.on("mouseenter", lambda: state.update(hover=True))
        viewport.on("mouseleave", lambda: state.update(hover=False))
        with viewport:
            img = ui.image(poster["url"]).style(
                f"width: {base_width}px; max-width: none; display:inline-block;"
            )
            img.on("dblclick", lambda: _cycle_zoom())

        ui.run_javascript(_DRAG_JS.format(viewport_id=viewport.id))

        def _apply():
            img.style(f"width: {round(base_width * state['scale'])}px; max-width: none; display:inline-block;")
            percent_label.set_text(f"{round(state['scale'] * 100)}%")

        def _zoom(delta: float):
            state["scale"] = min(_ZOOM_MAX, max(_ZOOM_MIN, round(state["scale"] + delta, 2)))
            _apply()

        def _reset():
            state["scale"] = 1.0
            _apply()

        def _cycle_zoom():
            # 더블클릭할 때마다 50%씩 더 확대되다가, 최대 배율을 넘으면 100%로 리셋.
            next_scale = round(state["scale"] + _ZOOM_STEP, 2)
            state["scale"] = 1.0 if next_scale > _ZOOM_MAX else next_scale
            _apply()

        def _on_key(e: events.KeyEventArguments):
            if not state["hover"] or not e.action.keydown:
                return
            if e.key in ("+", "="):
                _zoom(_ZOOM_STEP)
            elif e.key in ("-", "_"):
                _zoom(-_ZOOM_STEP)

        ui.keyboard(on_key=_on_key)

        with ui.row().classes("items-center gap-1"):
            ui.button(icon="remove", on_click=lambda: _zoom(-_ZOOM_STEP)).props("round dense flat size=sm")
            percent_label = ui.label("100%").classes("text-xs w-12 text-center").style(f"color:{MUTED};")
            ui.button(icon="add", on_click=lambda: _zoom(_ZOOM_STEP)).props("round dense flat size=sm")
            ui.button("원래 크기", on_click=_reset).props("flat dense size=sm").style(f"color:{ACCENT};")
            ui.button(
                icon="download",
                on_click=lambda: ui.download(poster["url"], filename=poster["url"].rsplit("/", 1)[-1]),
            ).props("round dense flat size=sm").tooltip("이미지 다운로드")


@ui.page("/intro")
def poster_page():
    frame(current_path="/schedule")

    cohort = app.storage.user.get("selected_cohort")
    if not cohort:
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        return

    posters = get_posters(cohort)
    page_header("📋", f"{cohort} 소개", get_cohort(cohort).get("title", ""))

    if not posters:
        ui.label("등록된 소개 이미지가 없습니다.").classes("text-gray-500")
    else:
        with ui.column().classes("w-full items-center gap-8"):
            for poster in posters:
                _zoomable_image(poster)

    ui.button("← 일정으로 돌아가기", on_click=lambda: ui.navigate.to("/schedule")).props("flat").classes(
        "mt-8"
    ).style(f"color:{ACCENT};")