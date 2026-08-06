"""
chat_page.py
- 사용자용 챗봇 화면. model과의 통신은 api_client를 통해서만 한다.
- 대화 기록은 app.storage.user에 저장한다 (각 @ui.page 이동은 실제 페이지 전환이라,
  브라우저 쿠키 기반 저장소가 아니면 다른 탭으로 갔다 오는 사이 기록이 날아간다).
"""

import asyncio

from nicegui import app, ui

from api_client import ModelServiceError, ask_stream
from auth import is_admin
from sources import render_sources
from theme import frame, page_header

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
</style>
"""


async def _do_scroll():
    try:
        await ui.run_javascript("window.scrollTo(0, document.body.scrollHeight)")
    except Exception:
        pass


def _scroll_to_bottom():
    # ui.run_javascript()가 반환하는 AwaitableResponse는 진짜 코루틴이 아니라서
    # asyncio.create_task()에 그대로 넘기면 TypeError가 난다(실제로 이 버그 때문에
    # 질문을 보내면 사용자 말풍선만 뜨고 답변이 통째로 멈췄었음). async 래퍼로 한 번
    # 감싸서 진짜 코루틴을 넘기고, 동기 콜백(on_token) 안에서도 fire-and-forget으로 쓴다.
    asyncio.create_task(_do_scroll())


@ui.page("/chat")
def chat_page():
    frame(current_path="/chat")
    ui.add_head_html(_CHAT_CSS)

    # 관리자 모드는 기수 개념과 무관하게(벡터DB가 기수 구분 없이 통합돼 있음) 항상
    # 챗봇+업로드 화면을 바로 쓸 수 있어야 하므로 기수 선택 여부를 확인하지 않는다.
    if not is_admin() and not app.storage.user.get("selected_cohort"):
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        ui.link("기수 선택하러 가기", "/").classes("m-4")
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
        "💬",
        "KDT 규정집 챗봇",
        "국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.",
        right=lambda: ui.toggle(TIER_OPTIONS, value=tier["value"], on_change=_on_tier_change)
        .props("rounded unelevated toggle-color=primary")
        .classes("border"),
    )

    messages: list = app.storage.user.setdefault("chat_messages", [])
    chat_box = ui.column().classes("w-full gap-2")
    faq_box = ui.row().classes("w-full gap-2 flex-wrap mb-3 kdt-stagger")
    input_row = ui.row().classes("w-full items-center gap-2 mt-2")

    def _show_faq():
        faq_box.clear()
        if messages:
            return
        with faq_box:
            ui.label("💡 자주 묻는 질문").classes("text-sm text-gray-500 w-full")
            for q in FAQ_QUESTIONS:
                ui.button(q, on_click=lambda q=q: _ask(q)).props("outline no-caps color=primary").classes(
                    "text-xs normal-case"
                )

    def _render_history_message(message: dict):
        with chat_box:
            with ui.chat_message(
                name=LABELS.get(message["role"], ""), sent=(message["role"] == "user")
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
            with ui.chat_message(name=LABELS["user"], sent=True).classes("w-full"):
                ui.markdown(question)
        _scroll_to_bottom()

        answer = {"text": ""}
        with chat_box:
            with ui.chat_message(name=LABELS["assistant"]).classes("w-full"):
                with ui.column().classes("gap-0.5 w-full") as body:
                    content_md = ui.markdown("")
                    spinner = ui.html('<div class="kdt-typing"><span></span><span></span><span></span></div>')
        _scroll_to_bottom()

        def on_token(token: str):
            answer["text"] += token
            content_md.set_content(answer["text"])
            spinner.set_visibility(False)
            _scroll_to_bottom()

        is_error = False
        sources: list = []
        try:
            sources = await ask_stream(question, on_token, tier=tier["value"])
        except ModelServiceError as e:
            answer["text"] = str(e)
            content_md.set_content(answer["text"])
            content_md.classes("text-red-500")
            is_error = True

        spinner.delete()
        messages.append(
            {
                "role": "assistant",
                "content": answer["text"],
                "sources": sources,
                "is_error": is_error,
            }
        )

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
        question_input = ui.input(placeholder="질문을 입력하세요.").classes("flex-grow kdt-input").on(
            "keydown.enter", _submit
        )
        ui.button(icon="send", on_click=_submit).props("round color=primary")
