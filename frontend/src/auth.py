"""
auth.py
- 관리자 로그인/권한 체크. 회원가입 없이 관리자 비밀번호 하나만 관리하는 단순 구조.
- 로그인 상태는 app.storage.user(브라우저별 서명 쿠키 세션)에 저장돼서, 페이지를
  이동해도(각 @ui.page는 별도 HTTP 요청) 로그인이 풀리지 않는다.
- ADMIN_PASSWORD 환경변수로 비밀번호를 바꿀 수 있다. 미설정 시 기본값을 쓰고 경고를 보여준다.
"""

import os

from nicegui import app, ui

_DEFAULT_ADMIN_PASSWORD = "1234"
_SESSION_KEY = "is_admin"


def _admin_password() -> str:
    return os.environ.get("ADMIN_PASSWORD", _DEFAULT_ADMIN_PASSWORD)


def is_admin() -> bool:
    return bool(app.storage.user.get(_SESSION_KEY, False))


def render_login_widget():
    """헤더 우측에 작은 로그인 버튼(팝오버 메뉴) 하나를 그린다. 배치는 호출하는 쪽
    (theme.frame)이 결정하고, 이 함수는 로그인 로직/내용에만 집중한다."""
    if is_admin():
        with ui.button(icon="vpn_key").props("flat round dense"):
            with ui.menu().classes("p-3"):
                with ui.column().classes("gap-2 w-48"):
                    ui.label("관리자로 로그인됨").classes("text-sm text-gray-500")

                    def _logout():
                        app.storage.user[_SESSION_KEY] = False
                        ui.navigate.reload()

                    ui.button("로그아웃", on_click=_logout).props("flat").classes("w-full")
    else:
        with ui.button(icon="lock").props("flat round dense"):
            with ui.menu().classes("p-3"):
                with ui.column().classes("gap-2 w-56"):
                    ui.label("관리자 로그인").classes("text-sm font-bold")
                    pw = ui.input(placeholder="비밀번호", password=True).classes("w-full")
                    error_label = ui.label("").classes("text-red-500 text-xs")

                    def _login():
                        if pw.value and pw.value == _admin_password():
                            app.storage.user[_SESSION_KEY] = True
                            # 관리자 화면도 같은 /chat, 같은 chat_messages 저장소를 쓰기 때문에
                            # 로그인 직전까지의 일반 사용자 대화가 그대로 보이면 안 된다 -
                            # 관리자로 들어가는 시점에 대화 기록을 비운다.
                            app.storage.user["chat_messages"] = []
                            # 관리자 모드의 메인 화면은 챗봇 + 업로드 콘솔이라, 로그인한
                            # 페이지가 어디였든 챗봇으로 이동시킨다.
                            ui.navigate.to("/chat")
                        else:
                            error_label.text = "비밀번호가 올바르지 않습니다."

                    pw.on("keydown.enter", _login)
                    ui.button("로그인", on_click=_login).classes("w-full")
                    if _admin_password() == _DEFAULT_ADMIN_PASSWORD:
                        with ui.row().classes("items-center gap-1"):
                            ui.icon("warning", size="14px").classes("text-amber-600")
                            ui.label("ADMIN_PASSWORD 환경변수 미설정 — 기본값 사용 중").classes(
                                "text-amber-600 text-xs"
                            )
