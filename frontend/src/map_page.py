"""
map_page.py
- 선택한 기수의 교육 장소를 카카오맵으로 보여준다.
- 좌표를 직접 관리하지 않고, 카카오맵 JS SDK의 Geocoder로 주소를 클라이언트에서
  좌표로 변환해 마커를 찍는다 (서버/모델 쪽 코드 변경 불필요).
- "카카오맵으로 길찾기" 버튼은 카카오맵 앱/웹으로 여는 딥링크일 뿐이라 Directions API를
  호출하지 않는다. 도착지만 넘기면 출발지(현재 위치)는 카카오맵 앱이 알아서 잡는다.
- KAKAO_JS_KEY가 없으면 지도 없이 딥링크 버튼만 보여준다.
"""

import os
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from cohorts import get_main_location
from theme import page_header

KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")


def render():
    cohort = st.session_state.get("selected_cohort")
    location = get_main_location(cohort)

    if not location:
        page_header("📍", "오시는길")
        st.warning("먼저 기수를 선택해주세요.")
        return

    page_header("📍", "오시는길", f"{cohort} 교육 장소 · {location}")

    search_link = f"https://map.kakao.com/link/search/{quote(location)}"

    if not KAKAO_JS_KEY:
        st.info("지도 미리보기는 KAKAO_JS_KEY가 설정되면 표시됩니다. 지금은 길찾기 링크만 이용해주세요.")
        st.link_button("🚗 카카오맵으로 길찾기", search_link, use_container_width=True)
        return

    html = f"""
    <div id="map" style="width:100%;height:400px;border-radius:8px;"></div>
    <div style="margin-top:12px;">
      <a id="route-link" href="{search_link}" target="_blank"
         style="display:inline-block;padding:10px 16px;background:#FEE500;color:#191919;
                border-radius:6px;text-decoration:none;font-weight:bold;">
        🚗 카카오맵으로 길찾기
      </a>
    </div>
    <script src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}&libraries=services"></script>
    <script>
      var address = "{location}";
      var container = document.getElementById('map');
      var map = new kakao.maps.Map(container, {{
        center: new kakao.maps.LatLng(35.8714, 128.6014),
        level: 4
      }});
      var geocoder = new kakao.maps.services.Geocoder();
      geocoder.addressSearch(address, function(result, status) {{
        if (status === kakao.maps.services.Status.OK) {{
          var coords = new kakao.maps.LatLng(result[0].y, result[0].x);
          new kakao.maps.Marker({{ map: map, position: coords }});
          map.setCenter(coords);
          document.getElementById('route-link').href =
            "https://map.kakao.com/link/to/" + encodeURIComponent(address) + "," + result[0].y + "," + result[0].x;
        }} else {{
          container.innerHTML =
            "<p style='padding:16px;color:#666;'>지도를 표시할 수 없습니다 (주소 검색 실패). 길찾기 버튼으로 검색해주세요.</p>";
        }}
      }});
    </script>
    """
    components.html(html, height=480)
