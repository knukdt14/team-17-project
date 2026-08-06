"""
main.py
- frontend 컨테이너의 NiceGUI 진입점.
- 예전에는 탭(챗봇/일정/오시는길/운영진)마다 별도 @ui.page라 브라우저가 매번 페이지를
  통째로 다시 받아왔다 - 그때마다 헤더도 처음부터 다시 그려져서 로고가 깜빡였다.
  지금은 루트 페이지 하나만 있고, 헤더(frame())는 그 안에서 딱 한 번만 그린 다음
  탭 내용은 ui.sub_pages로 URL만 바뀌면서 그 자리만 클라이언트 사이드로 교체된다.
  그래서 헤더는 유지된 채로 안 깜빡이고, 각 페이지 모듈은 @ui.page 없이 "내용만 그리는
  함수"로만 존재한다.
- 로그인/기수 선택/기수 변경처럼 헤더 자체가 바뀌어야 하는 동작은 예외적으로 완전한
  새로고침을 쓴다(auth.py, theme.py, landing.py에서 처리) - 이때는 화면이 다시 그려지는
  게 자연스럽고, 오히려 상태가 바뀌었다는 걸 보여주는 편이 맞다.
- RAG 로직/모델 관련 코드는 전혀 갖지 않는다. model 서비스(/ask, /ingest)만 직접 호출.
"""

import os

from nicegui import ui

from chat_page import chat_page
from faculty_page import faculty_page
from landing import landing
from map_page import map_page
from schedule_page import schedule_page
from theme import frame

ROUTES = {
    "/": landing,
    "/chat": chat_page,
    "/schedule": schedule_page,
    "/map": map_page,
    "/faculty": faculty_page,
}

# app.storage.user(로그인 상태/기수 선택/대화기록)를 서명된 쿠키로 암호화하는 데 쓰는 키.
# 데모/사내용이라 미설정 시 기본값을 쓰되, 배포 시에는 반드시 .env에 별도 값을 넣어야 한다.
STORAGE_SECRET = os.environ.get("NICEGUI_STORAGE_SECRET", "dev-secret-change-me")


@ui.page("/")
@ui.page("/{path:path}")
def root_page(path: str = ""):
    frame(current_path=f"/{path}" if path else "/")
    ui.sub_pages(ROUTES)


if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="KDT 규정집 챗봇",
        favicon="🎓",
        storage_secret=STORAGE_SECRET,
        reload=False,
    )
