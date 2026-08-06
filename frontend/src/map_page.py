"""
map_page.py
- 선택한 기수의 교육 장소를 카카오맵으로 보여준다.
- 좌표를 직접 관리하지 않고, 카카오맵 JS SDK로 장소(POI)를 검색해 마커를 찍는다
  (서버/모델 쪽 코드 변경 불필요).
- Kakao Geocoder(주소 검색)는 도로명/지번 주소만 인식해서 "5층 교육장"처럼 건물명 뒤에
  층/호실이 붙은 우리 데이터는 검색이 거의 실패한다. 검색은 3단계 폴백으로 진행한다:
  1) 장소(POI) 검색 Places.keywordSearch(건물명) - 등록된 유명 장소면 여기서 바로 잡힘
  2) 실패하면 _KNOWN_ADDRESSES에 등록해둔 실제 도로명주소로 Geocoder.addressSearch
     (대학 내부 교육관처럼 POI로 등록 안 된 건물을 위한 보강 - 좌표를 사람이 직접
     추정하지 않고, 검증된 정식 주소를 카카오 자체 지오코더에 맡긴다)
  3) 그래도 실패하면 원본 전체 문자열(예: "경일대학교 산학교육관 6층 교육장")로 마지막 시도
- "카카오맵으로 길찾기" 버튼은 카카오맵 앱/웹으로 여는 딥링크일 뿐이라 Directions API를
  호출하지 않는다. 도착지만 넘기면 출발지(현재 위치)는 카카오맵 앱이 알아서 잡는다.
- KAKAO_JS_KEY가 없으면 지도 없이 딥링크 버튼만 보여준다.
"""

import json
import os
import re
from urllib.parse import quote

from nicegui import app, ui

from cohorts import get_main_location
from theme import ACCENT, INK, MUTED, frame, page_header

KAKAO_JS_KEY = os.environ.get("KAKAO_JS_KEY", "")

_SUFFIX_RE = re.compile(r"\s*(?:\d+층\s*)?교육장(?:\s*\d+(?:,\s*\d+)*)?\s*$|\s*\d+층\s*$")


def _place_keyword(location: str) -> str:
    simplified = _SUFFIX_RE.sub("", location).strip()
    return simplified or location


# keywordSearch(POI 검색)이 등록 안 된 건물명(예: 대학 내부 특정 교육관)에서 실패할 때를
# 대비한 폴백. 건물명을 실제 도로명주소로 매핑해두면 Kakao Geocoder가 거의 항상 정확히
# 찾아준다 (사람이 좌표를 직접 추정/하드코딩하지 않아도 됨). _place_keyword()로 뽑은
# 건물명이 key라서, cohorts.py에 새 장소가 추가돼도 여기 없으면 기존 로직(keywordSearch
# -> 원본 문자열 addressSearch)으로 자연스럽게 폴백된다.
_KNOWN_ADDRESSES = {
    "포항시 북구청 문화예술팩토리": "경북 포항시 북구 삼호로 36",
    "경북대학교 복현회관": "대구광역시 북구 대학로 80",
    "경일대학교 산학교육관": "경상북도 경산시 하양읍 가마실길 50",
    "대구 스마트시티센터": "대구광역시 수성구 유니버시아드로 119",
}


@ui.page("/map")
def map_page():
    frame(current_path="/map")

    cohort = app.storage.user.get("selected_cohort")
    location = get_main_location(cohort)

    if not location:
        page_header("📍", "오시는길")
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500")
        return

    page_header("📍", "오시는길", "")

    search_link = f"https://map.kakao.com/link/search/{quote(location)}"

    with ui.card().classes("w-full p-5 mb-4 kdt-fade-up"):
        ui.label(cohort).classes("text-xs font-bold").style(f"color:{ACCENT};")
        ui.label(location).classes("text-lg font-extrabold mt-0.5").style(f"color:{INK};")

    if not KAKAO_JS_KEY:
        ui.label("지도 미리보기는 KAKAO_JS_KEY가 설정되면 표시됩니다. 지금은 길찾기 링크만 이용해주세요.").classes(
            "text-sm mb-3"
        ).style(f"color:{MUTED};")
        ui.link("🚗 카카오맵으로 길찾기", search_link).props("target=_blank").classes(
            "block w-full text-center bg-yellow-300 text-gray-900 font-bold rounded-xl py-3 no-underline"
        )
        return

    keyword = _place_keyword(location)
    known_address = _KNOWN_ADDRESSES.get(keyword)

    with ui.card().classes("w-full p-3 kdt-fade-up").style("animation-delay: 0.1s;"):
        ui.html(
            f"""
            <div id="kdt-map" style="width:100%;height:520px;border-radius:12px;"></div>
            <a id="kdt-route-link" href="{search_link}" target="_blank"
               style="display:inline-block;margin-top:14px;padding:11px 18px;background:#FEE500;
                      color:#191919;border-radius:10px;text-decoration:none;font-weight:bold;
                      font-size:0.9rem;">
              🚗 카카오맵 앱으로 길찾기
            </a>
            <span style="display:inline-block;margin-left:10px;font-size:0.8rem;color:{MUTED};">
              누르면 카카오맵 앱/웹에서 현재 위치 기준 경로를 바로 안내받을 수 있어요.
            </span>
            """
        )

    ui.add_body_html(
        f"""
        <script
          src="https://dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_JS_KEY}&libraries=services"
          onerror="var c=document.getElementById('kdt-map'); if(c) c.innerHTML=
            '<p style=\\'padding:16px;color:#c0392b;font-size:0.85rem;\\'>카카오맵 스크립트를 불러오지 못했습니다 (네트워크 차단 또는 잘못된 키). 길찾기 버튼으로 이용해주세요.</p>';"
        ></script>
        <script>
          (function() {{
            var keyword = {json.dumps(keyword)};
            var fullAddress = {json.dumps(location)};
            var knownAddress = {json.dumps(known_address)};

            function showError(container, msg) {{
              container.innerHTML = "<p style='padding:16px;color:#c0392b;font-size:0.85rem;'>" + msg + "</p>";
            }}

            // #kdt-map은 NiceGUI가 클라이언트에서 Vue로 그리는 DOM이라, 이 스크립트가
            // 실행되는 시점엔 아직 화면에 존재하지 않을 수 있다. 생길 때까지 잠깐씩 재시도한다.
            function waitForContainer(retriesLeft) {{
              var container = document.getElementById('kdt-map');
              if (!container) {{
                if (retriesLeft > 0) {{
                  setTimeout(function() {{ waitForContainer(retriesLeft - 1); }}, 100);
                }}
                return;
              }}
              initMap(container);
            }}

            function initMap(container) {{
              if (typeof kakao === 'undefined' || !kakao.maps) {{
                showError(container, "카카오맵 SDK를 불러오지 못했습니다. Kakao Developers 콘솔에 이 사이트 도메인이 등록되어 있는지 확인해주세요. 길찾기 버튼으로 이용해주세요.");
                return;
              }}

              try {{
                var center = new kakao.maps.LatLng(35.8714, 128.6014);
                var map = new kakao.maps.Map(container, {{ center: center, level: 4 }});

                function placeMarker(y, x, label) {{
                  var coords = new kakao.maps.LatLng(y, x);
                  new kakao.maps.Marker({{ map: map, position: coords }});
                  map.setCenter(coords);
                  var link = document.getElementById('kdt-route-link');
                  if (link) {{
                    link.href = "https://map.kakao.com/link/to/" + encodeURIComponent(label) + "," + y + "," + x;
                  }}
                }}

                var geocoder = new kakao.maps.services.Geocoder();

                function geocodeAddress(address, label, onFail) {{
                  geocoder.addressSearch(address, function(result, gStatus) {{
                    if (gStatus === kakao.maps.services.Status.OK) {{
                      placeMarker(result[0].y, result[0].x, label);
                    }} else {{
                      onFail();
                    }}
                  }});
                }}

                function finalFallback() {{
                  geocodeAddress(fullAddress, fullAddress, function() {{
                    showError(container, "지도를 표시할 수 없습니다 (장소를 찾지 못했어요). 길찾기 버튼으로 검색해주세요.");
                  }});
                }}

                var places = new kakao.maps.services.Places();
                places.keywordSearch(keyword, function(data, status) {{
                  if (status === kakao.maps.services.Status.OK && data.length > 0) {{
                    placeMarker(data[0].y, data[0].x, keyword);
                    return;
                  }}
                  // 대학 내부 교육관처럼 keywordSearch(POI 검색)로는 안 잡히는 건물은,
                  // 등록해둔 실제 도로명주소로 한 번 더 시도한다 (있으면 거의 항상 성공).
                  if (knownAddress) {{
                    geocodeAddress(knownAddress, knownAddress, finalFallback);
                  }} else {{
                    finalFallback();
                  }}
                }}, {{ location: center, radius: 20000 }});
              }} catch (err) {{
                showError(container, "지도를 불러오는 중 오류가 발생했습니다 (" + err.message + "). 길찾기 버튼으로 이용해주세요.");
              }}
            }}

            waitForContainer(50);
          }})();
        </script>
        """
    )
