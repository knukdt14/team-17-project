"""
schedule_page.py
- 선택한 기수의 교육기간/장소/모집기간/혜택/문의를 보여주는 정적 페이지.
- model을 거치지 않고 cohorts.py의 데이터를 그대로 표시한다.
"""

import streamlit as st

from cohorts import get_cohort
from theme import page_header


def render():
    cohort = st.session_state.get("selected_cohort")
    data = get_cohort(cohort)
    if not data:
        st.warning("먼저 기수를 선택해주세요.")
        return

    page_header("📅", f"{cohort} 교육 일정", data.get("title", ""))

    st.subheader("교육 기간")
    for label, value in data.get("period", {}).items():
        st.markdown(f"**{label}** · {value}")

    st.subheader("교육 장소")
    for label, value in data.get("location", {}).items():
        st.markdown(f"**{label}** · {value}")

    st.subheader("모집 기간")
    st.markdown(data.get("apply_period", "정보 없음"))

    benefits = data.get("benefits", [])
    if benefits:
        st.subheader("참여 혜택")
        for b in benefits:
            st.markdown(f"- {b}")

    contact = data.get("contact", {})
    if contact:
        st.subheader("교육 문의")
        for label, value in contact.items():
            st.markdown(f"**{label}** · {value}")

    st.divider()
    st.caption("※ 위 일정은 모집공고 기준이며, 운영 상황에 따라 변경될 수 있습니다.")
