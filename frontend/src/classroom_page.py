"""
classroom_page.py
- 선택한 기수의 강의실 사진을 보여준다. frontend/assets/에 있는 이미지를 그대로 표시한다.
- 아직 사진이 없는 기수는 준비중 안내만 보여준다.
"""

import os

from nicegui import app, ui

from cohorts import get_cohort
from theme import frame, page_header

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


@ui.page("/classroom")
def classroom_page():
    frame(current_path="/classroom")
    page_header("🏫", "강의실 사진")

    cohort = app.storage.user.get("selected_cohort")
    data = get_cohort(cohort)
    if not data:
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500 m-4")
        return

    photo = data.get("photo")
    if not photo:
        ui.label(f"{cohort} 강의실 사진은 아직 준비 중입니다.").classes("text-gray-500")
        return

    photo_path = os.path.join(ASSETS_DIR, photo)
    if not os.path.exists(photo_path):
        ui.label(f"사진 파일을 찾을 수 없습니다: {photo}").classes("text-amber-600")
        return

    ui.image(photo_path).classes("w-full rounded-2xl shadow-md")
    ui.label(f"{cohort} 강의실").classes("text-gray-500 text-sm text-center mt-2")
