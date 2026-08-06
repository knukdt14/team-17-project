"""
main.py
- frontend 컨테이너의 NiceGUI 진입점.
- 각 페이지 모듈을 import하면 모듈 안의 @ui.page 데코레이터가 라우트로 등록된다
  (등록만 되고, 실제 실행은 브라우저가 해당 경로로 들어올 때 이뤄진다).
- RAG 로직/모델 관련 코드는 전혀 갖지 않는다. model 서비스(/ask, /ingest)만 직접 호출.
"""

import os

from nicegui import ui

import admin_page  # noqa: F401  (import 자체가 @ui.page 라우트 등록)
import chat_page  # noqa: F401
import directions  # noqa: F401  (import 자체가 /api/directions 라우트 등록)
import faculty_page  # noqa: F401
import landing  # noqa: F401
import map_page  # noqa: F401
import schedule_page  # noqa: F401

# app.storage.user(로그인 상태/기수 선택/대화기록)를 서명된 쿠키로 암호화하는 데 쓰는 키.
# 데모/사내용이라 미설정 시 기본값을 쓰되, 배포 시에는 반드시 .env에 별도 값을 넣어야 한다.
STORAGE_SECRET = os.environ.get("NICEGUI_STORAGE_SECRET", "dev-secret-change-me")

if __name__ in {"__main__", "__mp_main__"}:
    ui.run(
        host="0.0.0.0",
        port=8501,
        title="KDT 규정집 챗봇",
        favicon="🎓",
        storage_secret=STORAGE_SECRET,
        reload=False,
    )
