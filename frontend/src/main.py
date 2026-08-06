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
- 카카오맵 JS SDK <script>도 여기 root_page()에서 딱 한 번(진짜 브라우저 페이지 로드 시점)
  선언적으로 붙인다. map_page.py가 방문할 때마다 document.createElement('script')로 직접
  붙였더니, sub_pages로 재진입할 때 간헐적으로 로딩이 멈추는(새로고침해야만 되는) 문제가
  있었다 - <script src> 태그가 실제 HTML 문서 로드의 일부로 파싱될 때와, 나중에 JS로
  동적으로 끼워넣을 때 카카오 SDK 내부 초기화 타이밍이 미묘하게 달라서 생기는 문제로
  보인다. head에 한 번만 선언해두면(모든 탭에서 공유) 예전 버전(탭마다 완전한 페이지
  새로고침이던 시절)과 동일하게 항상 안정적으로 초기화된다.
"""

import os

from nicegui import app, ui

import directions  # noqa: F401  (import 자체가 /api/directions 라우트 등록 - sub_pages와 무관한 FastAPI 라우트)
from chat_page import chat_page
from faculty_page import faculty_page
from landing import landing
from map_page import map_page
from poster_page import poster_page
from schedule_page import schedule_page
from theme import frame

KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")

ROUTES = {
    "/": landing,
    "/chat": chat_page,
    "/schedule": schedule_page,
    "/map": map_page,
    "/faculty": faculty_page,
    "/intro": poster_page,
}

# app.storage.user(로그인 상태/기수 선택/대화기록)를 서명된 쿠키로 암호화하는 데 쓰는 키.
# 데모/사내용이라 미설정 시 기본값을 쓰되, 배포 시에는 반드시 .env에 별도 값을 넣어야 한다.
STORAGE_SECRET = os.environ.get("NICEGUI_STORAGE_SECRET", "dev-secret-change-me")

# 기수 소개 포스터 등 정적 이미지 - frontend/assets/<기수>/파일명 으로 넣으면
# poster_page.py가 /assets/<기수>/파일명 URL로 그대로 보여준다.
_ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")
os.makedirs(_ASSETS_DIR, exist_ok=True)
app.add_static_files("/assets", _ASSETS_DIR)


@ui.page("/")
@ui.page("/{path:path}")
def root_page(path: str = ""):
    if KAKAO_JS_KEY:
        # 실제 <head>에 들어가는 진짜 <script> 태그라, 브라우저가 문서를 파싱하면서 정상적으로
        # 로드/초기화한다(카카오 SDK가 기대하는 원래 방식). map_page.py는 이게 준비될 때까지
        # window.kakao.maps.LatLng 존재 여부만 폴링해서 기다린다.
        ui.add_head_html(
            f'<script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}&libraries=services"></script>'
        )
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
