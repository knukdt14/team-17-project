"""
chat_page.py
- 사용자용 챗봇 화면. model과의 통신은 api_client를 통해서만 한다.
- 대화 기록은 app.storage.user에 저장한다 (서명된 쿠키 기반이라 탭을 옮겨 다니거나
  새로고침해도 유지된다).
- main.py의 ui.sub_pages가 이 함수를 "/chat" 콘텐츠로 호출하므로 @ui.page 데코레이터와
  frame() 호출은 여기서 하지 않는다(헤더는 root_page에서 한 번만 그린다).
"""

import asyncio
import urllib.parse

from nicegui import app, ui

from api_client import ModelServiceError, ask_stream, delete_file, list_files, upload_pdf
from auth import is_admin
from sources import render_sources
from theme import ACCENT, ACCENT_DARK, BORDER, GOLD, INK, KNU_LOGO_PATH, MUTED, page_header

# 무료/유료 버전 데모 토글 - model이 tier에 따라 solar(무료)/groq_llama(유료)로 답변한다.
# 과금 로직은 없고 시각적으로만 구분되는 데모용 기능.
TIER_OPTIONS = {"free": "무료 버전", "paid": "유료 버전"}

# 챗봇 화면에 바로 보여줄 자주 묻는 질문(규정 관련 위주).
# 일정처럼 기수마다 값이 달라지는 정보는 여기 넣지 않는다 — 벡터DB가 기수 구분 없이
# 통합돼 있어서, 기수별 정보를 챗봇으로 물으면 다른 기수 내용이 섞여 나올 수 있다.
FAQ_QUESTIONS = [
    "출석 인정 기준이 어떻게 되나요?",
    "수료 조건이 무엇인가요?",
    "훈련장려금은 어떻게 지급되나요?",
]

# 이모지 아바타 대신 말풍선 위에 붙는 작은 텍스트 라벨로 - q-chat-message의 name 속성.
LABELS = {"user": "사용자", "assistant": "AI 어시스턴트"}


def _avatar_svg(text: str, color_from: str, color_to: str) -> str:
    """q-chat-message의 avatar는 이미지 URL만 받아서, 이니셜 배지를 SVG data URI로 만들어 쓴다."""
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{color_from}"/><stop offset="1" stop-color="{color_to}"/>'
        f"</linearGradient></defs>"
        f'<circle cx="32" cy="32" r="32" fill="url(#g)"/>'
        f'<text x="32" y="40" font-family="Pretendard,Arial,sans-serif" font-size="20" '
        f'font-weight="800" fill="#fff" text-anchor="middle">{text}</text></svg>'
    )
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


AVATARS = {"user": _avatar_svg("나", INK, "#3A4256"), "assistant": _avatar_svg("AI", ACCENT, ACCENT_DARK)}


def _format_size(num_bytes: int) -> str:
    if num_bytes < 1024:
        return f"{num_bytes}B"
    if num_bytes < 1024 * 1024:
        return f"{num_bytes / 1024:.0f}KB"
    return f"{num_bytes / 1024 / 1024:.1f}MB"


_CHAT_CSS = """
<style>
  .kdt-typing { display:inline-flex; gap:5px; align-items:center; padding:4px 0; }
  .kdt-typing span {
    width:7px; height:7px; border-radius:50%;
    background: var(--kdt-accent);
    animation: kdt-typing-bounce 1.1s ease-in-out infinite;
  }
  .kdt-typing span:nth-child(2) { animation-delay: 0.15s; }
  .kdt-typing span:nth-child(3) { animation-delay: 0.30s; }
  @keyframes kdt-typing-bounce {
    0%, 60%, 100% { transform: translateY(0); opacity: 0.45; }
    30% { transform: translateY(-6px); opacity: 1; }
  }
  .kdt-input .q-field__control {
    border-radius: 14px !important;
    transition: box-shadow 0.2s ease, border-color 0.2s ease;
  }
  .kdt-input .q-field--focused .q-field__control {
    box-shadow: 0 0 0 3px var(--kdt-accent, #C8102E)22;
  }

  /* 질문 입력창을 화면 하단에 고정 - 스크롤 위치와 무관하게 항상 손 닿는 자리에 있게 */
  .kdt-composer-anchor {
    height: 104px;
  }
  .kdt-composer-fixed {
    position: fixed;
    left: 50%;
    bottom: 20px;
    transform: translateX(-50%);
    width: calc(100% - 48px);
    max-width: 984px;
    z-index: 900;
  }

  /* 관리자 PDF 업로드 버튼 - 색(primary)은 그대로 두고 크기만 키운다 */
  .kdt-upload-lg .q-uploader__header-content { padding: 18px 22px; }
  .kdt-upload-lg .q-uploader__title { font-size: 1.05rem; }
  .kdt-upload-lg .q-uploader__subtitle { font-size: 0.82rem; }
</style>
"""


_SCROLL_JS = """
(function() {
  function kdtScrollChat() {
    var el = document.querySelector('.kdt-chat-end');
    if (el) { el.scrollIntoView({block: 'end'}); }
    else { window.scrollTo(0, document.body.scrollHeight); }
  }
  requestAnimationFrame(function() { requestAnimationFrame(kdtScrollChat); });
  setTimeout(kdtScrollChat, 150);
})()
"""


# 관리자 테스트용 챗봇은 페이지 전체가 아니라 작은 박스 하나 안에서 스크롤되므로,
# window/문서 스크롤이 아니라 그 박스(.kdt-mini-chat-scroll) 자신의 scrollTop만 움직인다.
_MINI_SCROLL_JS = """
(function() {
  function kdtScrollMini() {
    var el = document.querySelector('.kdt-mini-chat-scroll');
    if (el) { el.scrollTop = el.scrollHeight; }
  }
  requestAnimationFrame(function() { requestAnimationFrame(kdtScrollMini); });
  // 마크다운/폰트 로딩 등으로 두 번의 rAF 이후에도 높이가 살짝 바뀔 수 있어
  // 150ms 뒤에 한 번 더 보정한다(_do_scroll의 페이지 전체 버전과 동일한 이유).
  setTimeout(kdtScrollMini, 150);
})()
"""


def _build_mini_test_chat():
    """PDF 업로드 버튼 옆에 붙는 작은 테스트용 챗봇. 일반 사용자용 챗봇(화면 하단 고정
    입력창 + 전체 폭)과 완전히 분리된 독립 위젯으로, 고정된 크기의 박스 안에 메시지
    영역(스크롤)과 입력창까지 다 들어있다. 검색 범위는 항상 scope="uploaded"(관리자가
    업로드한 파일만) 고정. 업로드 패널의 "추천 질문" 버튼이 바로 호출할 수 있도록
    _ask 함수를 반환한다."""
    tier = {"value": app.storage.user.get("llm_tier", "free")}
    messages: list = app.storage.user.setdefault("chat_messages", [])

    with ui.column().classes("gap-0 kdt-fade-up").style(
        f"width: 360px; min-width: 300px; height: 480px; flex-shrink: 0; "
        f"border:1px solid {BORDER}; border-radius:14px; overflow:hidden; "
        f"display:flex; flex-direction:column; box-shadow: var(--kdt-shadow-sm);"
    ):
        with ui.row().classes("items-center justify-between w-full px-3 py-2").style(
            f"background:linear-gradient(135deg,{ACCENT},{ACCENT_DARK}); flex: 0 0 auto;"
        ):
            with ui.column().classes("gap-0"):
                ui.label("테스트용 챗봇").classes("text-sm font-extrabold").style("color:#fff;")
                ui.label("업로드한 PDF만 검색").classes("text-[10px]").style("color:#ffffffcc;")

            def _on_tier_change(e):
                tier["value"] = e.value
                app.storage.user["llm_tier"] = e.value
                messages.clear()
                chat_box.clear()

            # 빨간 헤더 배경 위에 그냥 올리면 비활성 글자색이 배경과 겹쳐 잘 안 보였다 -
            # 흰 배경 알약 안에 넣어서 항상 또렷하게 보이게 한다(선택 텍스트는 primary=빨강,
            # 비선택 텍스트는 어두운 회색으로 고정).
            ui.toggle(TIER_OPTIONS, value=tier["value"], on_change=_on_tier_change).props(
                "dense rounded unelevated size=sm toggle-color=primary text-color=grey-9"
            ).classes("text-[10px]").style("background:#fff;")

        chat_box = ui.column().classes("w-full gap-2 px-3 py-2 kdt-mini-chat-scroll").style(
            "flex: 1 1 auto; overflow-y: auto; min-height: 0;"
        )

        with ui.row().classes("items-center gap-1 px-2 py-2 w-full").style(
            f"flex: 0 0 auto; border-top:1px solid {BORDER};"
        ):
            question_input = (
                ui.input(placeholder="질문 입력...")
                .classes("flex-grow")
                .props("dense borderless")
                .on("keydown.enter", lambda: _submit())
            )
            ui.button(icon="send", on_click=lambda: _submit()).props("round dense flat color=primary")

    async def _do_mini_scroll():
        try:
            # ui.run_javascript()는 "현재 슬롯"(어떤 client/페이지에 보낼지)이 필요한데,
            # asyncio.create_task()로 띄운 새 task는 그 슬롯 스택을 물려받지 못해
            # RuntimeError("slot stack ... is empty")가 나며 조용히 실패했었다(추천 질문을
            # 누르거나 답변이 와도 스크롤이 전혀 안 되던 원인). with chat_box:로 이 task
            # 안에서 슬롯을 명시적으로 다시 잡아준다.
            with chat_box:
                await ui.run_javascript(_MINI_SCROLL_JS)
        except Exception:
            pass

    def _scroll_mini_to_bottom():
        asyncio.create_task(_do_mini_scroll())

    def _render_history_message(message: dict):
        with chat_box:
            with ui.chat_message(
                name=LABELS.get(message["role"], ""),
                avatar=AVATARS.get(message["role"]),
                sent=(message["role"] == "user"),
            ).classes("w-full"):
                with ui.column().classes("gap-0.5 w-full"):
                    if message.get("is_error"):
                        ui.label(message["content"]).classes("text-red-500 text-xs")
                    else:
                        ui.markdown(message["content"]).classes("text-xs")
                        if message["role"] == "assistant":
                            render_sources(message.get("sources"))

    for m in messages:
        _render_history_message(m)
    if not messages:
        with chat_box:
            ui.label("업로드한 PDF에 대해 질문해보세요.").classes("text-xs text-center w-full mt-6").style(
                f"color:{MUTED};"
            )

    async def _ask(question: str):
        if not messages:
            chat_box.clear()
        messages.append({"role": "user", "content": question})
        with chat_box:
            with ui.chat_message(name=LABELS["user"], avatar=AVATARS["user"], sent=True).classes("w-full"):
                ui.markdown(question).classes("text-xs")
        _scroll_mini_to_bottom()

        answer = {"text": ""}
        with chat_box:
            with ui.chat_message(name=LABELS["assistant"], avatar=AVATARS["assistant"]).classes("w-full"):
                with ui.column().classes("gap-0.5 w-full") as body:
                    content_md = ui.markdown("").classes("text-xs")
                    spinner = ui.html('<div class="kdt-typing"><span></span><span></span><span></span></div>')
        _scroll_mini_to_bottom()

        def on_token(token: str):
            answer["text"] += token
            if content_md.is_deleted:
                return
            content_md.set_content(answer["text"])
            spinner.set_visibility(False)
            _scroll_mini_to_bottom()

        is_error = False
        sources: list = []
        try:
            sources = await ask_stream(question, on_token, tier=tier["value"], scope="uploaded")
        except ModelServiceError as e:
            answer["text"] = str(e)
            is_error = True
            if not content_md.is_deleted:
                content_md.set_content(answer["text"])
                content_md.classes("text-red-500")

        messages.append(
            {"role": "assistant", "content": answer["text"], "sources": sources, "is_error": is_error}
        )

        if content_md.is_deleted:
            return
        if not spinner.is_deleted:
            spinner.delete()
        if not is_error:
            with body:
                render_sources(sources)
        _scroll_mini_to_bottom()

    async def _submit():
        q = question_input.value.strip() if question_input.value else ""
        if not q:
            return
        question_input.value = ""
        await _ask(q)

    return _ask


def _admin_manager():
    """관리자 전용 화면 전체를 구성한다: PDF 자료 관리(업로드+추천 질문)와 그 옆에 작게
    붙는 테스트용 챗봇, 그리고 아래에 전체 폭을 쓰는 PDF 목록(페이지네이션)."""
    with ui.column().classes("w-full gap-3 p-6 mb-6 kdt-fade-up").style(
        f"background:#fff; border:1px solid {GOLD}30; border-radius:18px; box-shadow: var(--kdt-shadow-sm);"
    ):
        ui.label("PDF 자료 관리").classes("text-base font-extrabold").style(f"color:{INK};")
        ui.label(
            "PDF를 업로드하면 벡터DB에 바로 반영됩니다. 오른쪽 테스트용 챗봇은 여기 목록의 "
            "'업로드됨' 파일만 검색해서 답변합니다."
        ).classes("text-xs").style(f"color:{MUTED};")

        # 접고 펼치는 아코디언 대신 페이지를 넘기는 방식 - 목록이 길어져도 박스 높이가
        # 늘어나지 않고 항상 일정하게 유지된다. 한 페이지 분량이 박스 높이(480px)를 거의
        # 꽉 채우도록 8개로 잡았다 - 기본 제공 규정집만 11종이라 8개씩이어도 2페이지 이상은
        # 항상 나온다.
        PAGE_SIZE = 8
        list_state = {"files": [], "page": 0}

        with ui.row().classes("w-full gap-4 items-start flex-wrap"):
            with ui.column().classes("gap-2 flex-grow").style("min-width: 240px;"):
                upload_widget = (
                    ui.upload(auto_upload=True, label="+ PDF 업로드")
                    # 한 번에 여러 파일을 고르면 업로드 확인 다이얼로그가 동시에 여러 개
                    # 뜨는 문제가 있어(업로드마다 확인을 받으므로), 한 번에 한 개씩만
                    # 선택하도록 제한한다.
                    .props("accept=.pdf flat :multiple=false")
                    .classes("w-80 kdt-upload-lg")
                )
                upload_status = ui.label("").classes("text-xs")
                faq_box = ui.column().classes("w-full gap-2")

            with ui.column().classes("gap-2").style(
                "width: 300px; min-width: 260px; height: 480px; flex-shrink: 0; "
                f"border:1px solid {BORDER}; border-radius:14px; padding:12px; "
                "display:flex; flex-direction:column; box-shadow: var(--kdt-shadow-sm);"
            ):
                list_title = ui.label("등록된 PDF 목록").classes("text-sm font-bold").style(f"color:{INK};")
                files_box = ui.column().classes("w-full gap-2 mt-1").style(
                    "flex: 1 1 auto; overflow-y: auto; min-height: 0;"
                )
                with ui.row().classes("w-full items-center justify-center gap-3").style(
                    "flex: 0 0 auto;"
                ) as pager_row:
                    prev_btn = ui.button(icon="chevron_left", on_click=lambda: _change_page(-1)).props(
                        "flat round dense size=sm"
                    )
                    page_label = ui.label("").classes("text-xs font-bold").style(f"color:{MUTED};")
                    next_btn = ui.button(icon="chevron_right", on_click=lambda: _change_page(1)).props(
                        "flat round dense size=sm"
                    )

            ask_fn = _build_mini_test_chat()

        async def _confirm_delete(filename: str) -> bool:
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3"):
                ui.label(f"'{filename}' 을(를) 정말 삭제하시겠습니까?").classes("text-sm font-bold").style(
                    f"color:{INK};"
                )
                ui.label(
                    "삭제하면 챗봇 검색 대상에서 즉시 제외되고 파일도 함께 지워집니다."
                ).classes("text-xs").style(f"color:{MUTED};")
                with ui.row().classes("justify-end gap-2 w-full"):
                    ui.button("취소", on_click=lambda: dialog.submit(False)).props("flat")
                    ui.button("삭제", on_click=lambda: dialog.submit(True)).props(
                        "color=negative unelevated"
                    )
            result = bool(await dialog)
            dialog.delete()
            return result

        async def _refresh_files():
            files_box.clear()
            pager_row.set_visibility(False)
            with files_box:
                ui.spinner(size="24px")
            try:
                files = await list_files()
            except ModelServiceError as e:
                files_box.clear()
                with files_box:
                    ui.label(str(e)).classes("text-red-500 text-xs")
                return

            list_title.set_text(f"등록된 PDF 목록 ({len(files)})")
            list_state["files"] = files
            list_state["page"] = 0
            _render_page()

        def _render_page():
            files = list_state["files"]
            total = len(files)
            total_pages = max(1, -(-total // PAGE_SIZE))  # 올림 나눗셈
            list_state["page"] = max(0, min(list_state["page"], total_pages - 1))
            page = list_state["page"]
            page_files = files[page * PAGE_SIZE : page * PAGE_SIZE + PAGE_SIZE]

            files_box.clear()
            if not page_files:
                with files_box:
                    ui.label("등록된 PDF가 없습니다.").classes("text-xs").style(f"color:{MUTED};")
            else:
                with files_box:
                    for f in page_files:
                        _render_file_card(f)

            pager_row.set_visibility(total > PAGE_SIZE)
            page_label.text = f"{page + 1} / {total_pages}"
            (prev_btn.disable() if page <= 0 else prev_btn.enable())
            (next_btn.disable() if page >= total_pages - 1 else next_btn.enable())

        def _change_page(delta: int):
            list_state["page"] += delta
            _render_page()

        def _render_file_card(f: dict):
            origin_label = "기본 제공" if f["origin"] == "base" else "업로드됨"
            origin_color = MUTED if f["origin"] == "base" else ACCENT

            async def _on_delete(filename=f["filename"]):
                if not await _confirm_delete(filename):
                    return
                try:
                    await delete_file(filename)
                    # ui.notify()도 ui.run_javascript()와 마찬가지로 호출 시점에 유효한
                    # 슬롯이 필요하다. 삭제 확인 다이얼로그가 열렸다 닫히는 사이 이 버튼이
                    # 속했던 원래 슬롯이 무효화되는 경우가 있어(다이얼로그 진입/이탈로 슬롯
                    # 스택이 흔들림), 항상 살아있는 files_box를 슬롯으로 다시 잡아준다.
                    with files_box:
                        ui.notify(f"{filename} 삭제 완료", type="positive")
                except ModelServiceError as e:
                    with files_box:
                        ui.notify(str(e), type="negative")
                await _refresh_files()

            with ui.row().classes("items-center gap-2 w-full p-2 flex-nowrap").style(
                f"border:1px solid {BORDER}; border-radius:10px;"
            ):
                ui.icon("picture_as_pdf", size="20px").style(f"color:{ACCENT}; flex-shrink:0;")
                with ui.column().classes("gap-0 flex-grow min-w-0"):
                    ui.label(f["filename"]).classes("text-xs font-bold truncate w-full").style(f"color:{INK};")
                    ui.label(
                        f"{origin_label} · {_format_size(f['size_bytes'])} · 청크 {f['chunk_count']}개"
                    ).classes("text-[10px]").style(f"color:{origin_color};")
                ui.button(icon="delete", on_click=_on_delete).props(
                    "flat round dense size=sm color=negative"
                ).style("flex-shrink:0;")

        async def _confirm_upload(filename: str) -> bool:
            with ui.dialog() as dialog, ui.card().classes("p-4 gap-3"):
                ui.label(f"'{filename}' 을(를) 업로드 하시겠습니까?").classes("text-sm font-bold").style(
                    f"color:{INK};"
                )
                ui.label(
                    "업로드하면 벡터DB에 바로 반영되어 테스트용 챗봇 검색 대상이 됩니다."
                ).classes("text-xs").style(f"color:{MUTED};")
                with ui.row().classes("justify-end gap-2 w-full"):
                    ui.button("취소", on_click=lambda: dialog.submit(False)).props("flat")
                    ui.button("업로드", on_click=lambda: dialog.submit(True)).props("unelevated")
            result = bool(await dialog)
            dialog.delete()
            return result

        # 업로드 두 개가 겹치면(같은 파일을 두 번 누르는 등) 나중에 끝난 응답이 먼저 끝난
        # 응답의 "추천 질문"을 덮어써야 하는데, 네트워크/LLM 응답 속도에 따라 완료 순서가
        # 시작한 순서와 다를 수 있다. 매 업로드마다 일련번호를 매겨서, 화면에는 항상
        # "가장 나중에 시작한 업로드"의 결과만 반영되도록 한다.
        upload_seq = {"n": 0}

        async def _handle_upload(e):
            uploaded_count = sum(1 for f in list_state["files"] if f["origin"] == "uploaded")
            if uploaded_count >= 5:
                upload_status.text = "업로드 가능한 PDF는 최대 5개까지입니다. 기존 파일을 삭제한 후 다시 시도해주세요."
                upload_status.style("color:#DC2626;")
                return

            if not await _confirm_upload(e.file.name):
                return

            upload_seq["n"] += 1
            my_seq = upload_seq["n"]

            content = await e.file.read()
            upload_status.text = f"{e.file.name} 업로드 및 반영 중..."
            upload_status.style(f"color:{MUTED};")
            try:
                data = await upload_pdf(e.file.name, content)
                await _refresh_files()
                if upload_seq["n"] != my_seq:
                    # 이 응답이 도착하기 전에 더 최근 업로드가 시작됐다 - 그 업로드의 결과를
                    # 덮어쓰지 않도록 상태 표시/추천 질문 갱신은 건너뛴다.
                    return
                upload_status.text = f"{data['filename']} 반영 완료 (청크 {data['chunks_added']}개 추가)"
                upload_status.style("color:#16A34A;")
                faq_box.clear()
                questions = data.get("faq_questions") or []
                if questions:
                    with faq_box:
                        ui.label("자동 생성된 추천 질문 - 눌러서 바로 테스트해보세요").classes(
                            "text-xs font-bold mt-1"
                        ).style(f"color:{GOLD};")
                        with ui.column().classes("w-full gap-1"):
                            for q in questions:
                                ui.button(
                                    q, icon="chat_bubble_outline", on_click=lambda q=q: ask_fn(q)
                                ).props("outline no-caps align=left").classes("text-xs normal-case w-full")
            except ModelServiceError as err:
                if upload_seq["n"] == my_seq:
                    upload_status.text = str(err)
                    upload_status.style("color:#DC2626;")

        upload_widget.on_upload(_handle_upload)
        asyncio.create_task(_refresh_files())


def chat_page():
    ui.add_head_html(_CHAT_CSS)

    if not is_admin() and not app.storage.user.get("selected_cohort"):
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        ui.link("기수 선택하러 가기", "/").classes("m-4")
        return

    # 관리자 화면은 일반 사용자 챗봇(화면 하단 고정 입력창 + 전체 폭)과 구조 자체가
    # 다르다 - PDF 자료 관리 패널과 그 안에 작게 붙는 테스트용 챗봇으로 완전히 분리된
    # 화면이라, 아래 일반 사용자용 코드와 섞지 않고 여기서 끝낸다.
    if is_admin():
        _admin_manager()
        return

    tier = {"value": app.storage.user.get("llm_tier", "free")}

    def _on_tier_change(e):
        tier["value"] = e.value
        app.storage.user["llm_tier"] = e.value
        # 무료<->유료는 서로 다른 모델이라, 지금까지의 대화를 그대로 이어붙이면 어느 모델이
        # 만든 답변인지 헷갈린다. 버전을 바꾸면 새 대화로 취급해서 화면/기록을 같이 비운다.
        messages.clear()
        chat_box.clear()
        _show_faq()

    page_header(
        "forum",
        "KDT 규정집 챗봇",
        "국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.",
        logo=KNU_LOGO_PATH,
        right=lambda: ui.toggle(TIER_OPTIONS, value=tier["value"], on_change=_on_tier_change)
        .props("rounded unelevated toggle-color=primary")
        .classes("border"),
    )

    messages: list = app.storage.user.setdefault("chat_messages", [])
    chat_box = ui.column().classes("w-full gap-2")
    faq_box = ui.column().classes("w-full gap-3 mb-3")
    # 입력창은 고정 위치라 문서 흐름에서 빠지므로, 마지막 메시지가 입력창에 가려지지
    # 않도록 그 자리만큼 빈 공간을 하나 남겨두고, 이 엘리먼트를 스크롤 목적지로 쓴다.
    ui.element("div").classes("w-full kdt-composer-anchor kdt-chat-end")
    input_row = ui.row().classes(
        "kdt-composer-fixed items-center gap-2 p-2 pl-4"
    ).style(f"background:#fff; border:1px solid {GOLD}40; border-radius:999px; box-shadow: var(--kdt-shadow-md);")

    async def _do_scroll():
        try:
            # scrollHeight를 직접 계산하는 대신 맨 아래 앵커 엘리먼트를 scrollIntoView로
            # 스크롤한다 - 실제로 스크롤되는 요소가 window인지 다른 컨테이너인지 몰라도 항상
            # 맞는 곳을 스크롤해준다. NiceGUI가 새 메시지를 DOM에 그려 넣기 전에 스크롤하면
            # 옛 레이아웃 기준으로 계산돼서 새 메시지가 화면 밖에 남는 문제가 있었어서, 두 번의
            # requestAnimationFrame으로 레이아웃이 확정된 다음 스크롤하고, 마크다운/폰트 로딩 등으로
            # 그 이후에도 높이가 살짝 바뀔 수 있어 150ms 뒤에 한 번 더 보정한다.
            #
            # with chat_box:로 슬롯을 다시 잡아주는 이유는 _build_mini_test_chat의
            # _do_mini_scroll 주석 참고 - asyncio.create_task()로 띄운 task는 슬롯 스택을
            # 물려받지 못해 그냥 두면 ui.run_javascript()가 RuntimeError로 조용히 실패한다.
            with chat_box:
                await ui.run_javascript(_SCROLL_JS)
        except Exception:
            pass

    def _scroll_to_bottom():
        # ui.run_javascript()가 반환하는 AwaitableResponse는 진짜 코루틴이 아니라서
        # asyncio.create_task()에 그대로 넘기면 TypeError가 난다(실제로 이 버그 때문에
        # 질문을 보내면 사용자 말풍선만 뜨고 답변이 통째로 멈췄었음). async 래퍼로 한 번
        # 감싸서 진짜 코루틴을 넘기고, 동기 콜백(on_token) 안에서도 fire-and-forget으로 쓴다.
        asyncio.create_task(_do_scroll())

    def _show_faq():
        faq_box.clear()
        if messages:
            return
        with faq_box:
            with ui.column().classes("w-full gap-3 p-5 kdt-stagger").style(
                f"background:linear-gradient(160deg,{ACCENT}0d,transparent 65%); "
                f"border:1px solid {GOLD}30; border-radius:18px;"
            ):
                with ui.row().classes("items-center gap-1.5 w-full"):
                    ui.icon("tips_and_updates", size="16px").style(f"color:{GOLD};")
                    ui.label("자주 묻는 질문").classes("text-sm font-bold").style(f"color:{INK};")
                with ui.row().classes("w-full gap-2 flex-wrap"):
                    for q in FAQ_QUESTIONS:
                        ui.button(q, icon="chat_bubble_outline", on_click=lambda q=q: _ask(q)).props(
                            "outline no-caps color=primary"
                        ).classes("text-xs normal-case")

    def _render_history_message(message: dict):
        with chat_box:
            with ui.chat_message(
                name=LABELS.get(message["role"], ""),
                avatar=AVATARS.get(message["role"]),
                sent=(message["role"] == "user"),
            ).classes("w-full"):
                # q-chat-message는 default slot 안의 자식이 여러 개면 각각을 별도 말풍선으로
                # 그린다. 답변+출처를 한 말풍선 안에 이어 붙이려면 자식을 하나(이 column)로
                # 묶어야 한다.
                with ui.column().classes("gap-0.5 w-full"):
                    if message.get("is_error"):
                        ui.label(message["content"]).classes("text-red-500")
                    else:
                        ui.markdown(message["content"])
                        if message["role"] == "assistant":
                            render_sources(message.get("sources"))

    for m in messages:
        _render_history_message(m)

    async def _ask(question: str):
        faq_box.clear()

        messages.append({"role": "user", "content": question})
        with chat_box:
            with ui.chat_message(name=LABELS["user"], avatar=AVATARS["user"], sent=True).classes("w-full"):
                ui.markdown(question)
        _scroll_to_bottom()

        answer = {"text": ""}
        with chat_box:
            with ui.chat_message(name=LABELS["assistant"], avatar=AVATARS["assistant"]).classes("w-full"):
                with ui.column().classes("gap-0.5 w-full") as body:
                    content_md = ui.markdown("")
                    spinner = ui.html('<div class="kdt-typing"><span></span><span></span><span></span></div>')
        _scroll_to_bottom()

        def on_token(token: str):
            answer["text"] += token
            # 스트리밍 도중 사용자가 다른 탭으로 이동하면 ui.sub_pages가 이 화면 전체를
            # 지워버리는데, 그 뒤로도 이 콜백은 계속 불린다. 지워진 엘리먼트를 계속 건드리면
            # "부모 슬롯이 삭제됨" 예외가 나서(그 예외 처리 과정에서 또 예외가 나며) 이후
            # 상호작용까지 깨졌었다 - 지워졌으면 텍스트만 누적하고 화면 갱신은 건너뛴다.
            if content_md.is_deleted:
                return
            content_md.set_content(answer["text"])
            spinner.set_visibility(False)
            _scroll_to_bottom()

        is_error = False
        sources: list = []
        try:
            sources = await ask_stream(question, on_token, tier=tier["value"], scope="all")
        except ModelServiceError as e:
            answer["text"] = str(e)
            is_error = True
            if not content_md.is_deleted:
                content_md.set_content(answer["text"])
                content_md.classes("text-red-500")

        messages.append(
            {
                "role": "assistant",
                "content": answer["text"],
                "sources": sources,
                "is_error": is_error,
            }
        )

        if content_md.is_deleted:
            return

        if not spinner.is_deleted:
            spinner.delete()
        if not is_error:
            with body:
                render_sources(sources)
        _scroll_to_bottom()

    async def _submit():
        q = question_input.value.strip() if question_input.value else ""
        if not q:
            return
        question_input.value = ""
        await _ask(q)

    _show_faq()

    with input_row:
        question_input = (
            ui.input(placeholder="질문을 입력하세요.")
            .classes("flex-grow kdt-input")
            .props("borderless")
            .on("keydown.enter", _submit)
        )
        ui.button(icon="send", on_click=_submit).props("round color=primary")
