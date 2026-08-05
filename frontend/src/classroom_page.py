"""
classroom_page.py
- 선택한 기수의 강의실 사진을 보여준다. frontend/assets/에 있는 이미지를 그대로 표시한다.
- 아직 사진이 없는 기수는 준비중 안내만 보여준다.
"""

import os

import streamlit as st

from cohorts import get_cohort

ASSETS_DIR = os.path.join(os.path.dirname(__file__), "..", "assets")


def render():
    cohort = st.session_state.get("selected_cohort")
    data = get_cohort(cohort)

    st.title("🏫 강의실 사진")
    if not data:
        st.warning("먼저 기수를 선택해주세요.")
        return

    photo = data.get("photo")
    if not photo:
        st.info(f"{cohort} 강의실 사진은 아직 준비 중입니다.")
        return

    photo_path = os.path.join(ASSETS_DIR, photo)
    if not os.path.exists(photo_path):
        st.warning(f"사진 파일을 찾을 수 없습니다: {photo}")
        return

    st.image(photo_path, caption=f"{cohort} 강의실", use_container_width=True)
