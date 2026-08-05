"""
chat_page.py
- 사용자용 챗봇 화면. model과의 통신은 api_client를 통해서만 한다.
- 대화 기록은 app.storage.user에 저장한다 (각 @ui.page 이동은 실제 페이지 전환이라,
  브라우저 쿠키 기반 저장소가 아니면 다른 탭으로 갔다 오는 사이 기록이 날아간다).
"""

from nicegui import app, ui

from api_client import ModelServiceError, ask_stream, send_feedback
from sources import render_sources
from theme import frame, page_header

# 챗봇 화면에 바로 보여줄 자주 묻는 질문(규정 관련 위주).
# 일정처럼 기수마다 값이 달라지는 정보는 여기 넣지 않는다 — 벡터DB가 기수 구분 없이
# 통합돼 있어서, 기수별 정보를 챗봇으로 물으면 다른 기수 내용이 섞여 나올 수 있다.
FAQ_QUESTIONS = [
    "출석 인정 기준이 어떻게 되나요?",
    "수료 조건이 무엇인가요?",
    "훈련장려금은 어떻게 지급되나요?",
]

AVATARS = {"user": "🙂", "assistant": "🎓"}


@ui.page("/chat")
def chat_page():
    frame(current_path="/chat")

    if not app.storage.user.get("selected_cohort"):
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        ui.link("기수 선택하러 가기", "/").classes("m-4")
        return

    page_header("💬", "KDT 규정집 챗봇", "국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.")

    messages: list = app.storage.user.setdefault("chat_messages", [])
    chat_box = ui.column().classes("w-full gap-2")
    faq_box = ui.row().classes("w-full gap-2 flex-wrap mb-3")
    input_row = ui.row().classes("w-full items-center gap-2 mt-2")

    def _feedback_row(message: dict):
        async def _send(rating: str):
            if message.get("feedback_sent") == rating:
                return
            message["feedback_sent"] = rating
            await send_feedback(message.get("question", ""), message["content"], rating)

        with ui.row().classes("gap-1 mt-1 -ml-2"):
            ui.button(icon="thumb_up", on_click=lambda: _send("up")).props("flat dense round size=sm")
            ui.button(icon="thumb_down", on_click=lambda: _send("down")).props("flat dense round size=sm")

    def _render_history_message(message: dict):
        with chat_box:
            with ui.chat_message(
                name=AVATARS.get(message["role"], ""), sent=(message["role"] == "user")
            ).classes("w-full"):
                if message.get("is_error"):
                    ui.label(message["content"]).classes("text-red-500")
                else:
                    ui.markdown(message["content"])
                    if message["role"] == "assistant":
                        render_sources(message.get("sources"))
                        _feedback_row(message)

    for m in messages:
        _render_history_message(m)

    async def _ask(question: str):
        faq_box.clear()

        messages.append({"role": "user", "content": question})
        with chat_box:
            with ui.chat_message(name=AVATARS["user"], sent=True).classes("w-full"):
                ui.markdown(question)

        answer = {"text": ""}
        with chat_box:
            with ui.chat_message(name=AVATARS["assistant"]).classes("w-full") as msg:
                content_md = ui.markdown("")
                spinner = ui.spinner("dots", size="2em", color="primary")

        def on_token(token: str):
            answer["text"] += token
            content_md.set_content(answer["text"])
            spinner.set_visibility(False)

        is_error = False
        sources: list = []
        try:
            sources = await ask_stream(question, on_token)
        except ModelServiceError as e:
            answer["text"] = str(e)
            content_md.set_content(answer["text"])
            content_md.classes("text-red-500")
            is_error = True

        spinner.delete()
        assistant_message = {
            "role": "assistant",
            "content": answer["text"],
            "sources": sources,
            "is_error": is_error,
            "question": question,
        }
        messages.append(assistant_message)

        if not is_error:
            with msg:
                render_sources(sources)
                _feedback_row(assistant_message)

    async def _submit():
        q = question_input.value.strip() if question_input.value else ""
        if not q:
            return
        question_input.value = ""
        await _ask(q)

    if not messages:
        with faq_box:
            ui.label("💡 자주 묻는 질문").classes("text-sm text-gray-500 w-full")
            for q in FAQ_QUESTIONS:
                ui.button(q, on_click=lambda q=q: _ask(q)).props("outline no-caps color=primary").classes(
                    "text-xs normal-case"
                )

    with input_row:
        question_input = ui.input(placeholder="질문을 입력하세요.").classes("flex-grow").on(
            "keydown.enter", _submit
        )
        ui.button(icon="send", on_click=_submit).props("round color=primary")
