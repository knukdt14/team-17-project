"""
map_page.py
- 선택한 기수의 교육 장소를 카카오맵으로 보여준다.
- 좌표를 직접 관리하지 않고, 카카오맵 JS SDK의 Geocoder로 주소를 클라이언트에서
  좌표로 변환해 마커를 찍는다 (서버/모델 쪽 코드 변경 불필요).
- "카카오맵으로 길찾기" 버튼은 카카오맵 앱/웹으로 여는 딥링크일 뿐이라 Directions API를
  호출하지 않는다. 도착지만 넘기면 출발지(현재 위치)는 카카오맵 앱이 알아서 잡는다.
- KAKAO_JS_KEY가 없으면 지도 없이 딥링크 버튼만 보여준다.
"""

import json
import os
import re
from urllib.parse import quote

import streamlit as st
import streamlit.components.v1 as components

from cohorts import get_main_location
from theme import page_header

KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")

# Kakao Geocoder(주소 검색)는 도로명/지번 주소만 인식해서 "5층 교육장"처럼 건물명 뒤에
# 층/호실이 붙은 우리 데이터는 검색이 거의 실패한다. 대신 장소(POI) 검색인
# Places.keywordSearch를 쓰되, 검색어에서 층/교육장 표기를 빼고 건물명만 넘겨야
# 실제 POI와 매칭될 확률이 높다.
_SUFFIX_RE = re.compile(r"\s*(?:\d+층\s*)?교육장(?:\s*\d+(?:,\s*\d+)*)?\s*$|\s*\d+층\s*$")


def _place_keyword(location: str) -> str:
    simplified = _SUFFIX_RE.sub("", location).strip()
    return simplified or location


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

    keyword = _place_keyword(location)

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
      var keyword = {json.dumps(keyword)};
      var fullAddress = {json.dumps(location)};
      var container = document.getElementById('map');
      var center = new kakao.maps.LatLng(35.8714, 128.6014);
      var map = new kakao.maps.Map(container, {{ center: center, level: 4 }});

      function showError(msg) {{
        container.innerHTML = "<p style='padding:16px;color:#666;'>" + msg + "</p>";
      }}

      function placeMarker(y, x, label) {{
        var coords = new kakao.maps.LatLng(y, x);
        new kakao.maps.Marker({{ map: map, position: coords }});
        map.setCenter(coords);
        document.getElementById('route-link').href =
          "https://map.kakao.com/link/to/" + encodeURIComponent(label) + "," + y + "," + x;
      }}

      // 1) 건물명(장소/POI) 검색을 먼저 시도 - "교육장/층" 같은 표기가 있는 우리 데이터엔 이쪽이 더 잘 맞음.
      var places = new kakao.maps.services.Places();
      places.keywordSearch(keyword, function(data, status) {{
        if (status === kakao.maps.services.Status.OK && data.length > 0) {{
          placeMarker(data[0].y, data[0].x, keyword);
          return;
        }}
        // 2) 장소 검색이 실패하면 원본 전체 문자열로 도로명/지번 주소 검색을 한 번 더 시도.
        var geocoder = new kakao.maps.services.Geocoder();
        geocoder.addressSearch(fullAddress, function(result, gStatus) {{
          if (gStatus === kakao.maps.services.Status.OK) {{
            placeMarker(result[0].y, result[0].x, fullAddress);
          }} else {{
            showError("지도를 표시할 수 없습니다 (장소를 찾지 못했어요). 길찾기 버튼으로 검색해주세요.");
          }}
        }});
      }}, {{ location: center, radius: 20000 }});
    </script>
    """
    components.html(html, height=480)
