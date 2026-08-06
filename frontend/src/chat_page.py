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

from api_client import ModelServiceError, ask_stream
from auth import is_admin
from sources import render_sources
from theme import ACCENT, ACCENT_DARK, GOLD, INK, KNU_LOGO_PATH, page_header

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


async def _do_scroll():
    try:
        # scrollHeight를 직접 계산하는 대신 맨 아래 앵커 엘리먼트를 scrollIntoView로
        # 스크롤한다 - 실제로 스크롤되는 요소가 window인지 다른 컨테이너인지 몰라도 항상
        # 맞는 곳을 스크롤해준다. NiceGUI가 새 메시지를 DOM에 그려 넣기 전에 스크롤하면
        # 옛 레이아웃 기준으로 계산돼서 새 메시지가 화면 밖에 남는 문제가 있었어서, 두 번의
        # requestAnimationFrame으로 레이아웃이 확정된 다음 스크롤하고, 마크다운/폰트 로딩 등으로
        # 그 이후에도 높이가 살짝 바뀔 수 있어 150ms 뒤에 한 번 더 보정한다.
        await ui.run_javascript(_SCROLL_JS)
    except Exception:
        pass


def _scroll_to_bottom():
    # ui.run_javascript()가 반환하는 AwaitableResponse는 진짜 코루틴이 아니라서
    # asyncio.create_task()에 그대로 넘기면 TypeError가 난다(실제로 이 버그 때문에
    # 질문을 보내면 사용자 말풍선만 뜨고 답변이 통째로 멈췄었음). async 래퍼로 한 번
    # 감싸서 진짜 코루틴을 넘기고, 동기 콜백(on_token) 안에서도 fire-and-forget으로 쓴다.
    asyncio.create_task(_do_scroll())


def chat_page():
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
        "forum",
        "KDT 규정집 챗봇",
        "국민내일배움카드 / KDT 규정집 등 사내 규정에 대해 물어보세요.",
        kicker="AI CHATBOT",
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
        question_input = (
            ui.input(placeholder="질문을 입력하세요.")
            .classes("flex-grow kdt-input")
            .props("borderless")
            .on("keydown.enter", _submit)
        )
        ui.button(icon="send", on_click=_submit).props("round color=primary")
