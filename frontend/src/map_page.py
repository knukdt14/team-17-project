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
  이 버튼은 반드시 새 탭에서 열려야 하는데, raw <a onclick=...> HTML은 NiceGUI가
  ui.html() 콘텐츠에 적용하는 살균(sanitize) 처리에 걸려 onclick이 씹히는 문제가 있었다.
  그래서 이 버튼만은 NiceGUI가 공식 지원하는 ui.link(new_tab=True) 컴포넌트로 만든다
  (진짜 <a target="_blank">를 프레임워크가 직접 보장해줌).
- 출발지는 브라우저 위치를 자동으로 가져오지 않는다 (환경에 따라 부정확할 수 있고,
  사용자 동의 없이 위치를 바로 요청하는 것도 좋은 UX가 아님). 대신 출발지를 직접
  입력하는 텍스트 필드 + "경로 찾기" 버튼을 기본으로 제공하고, 원하면 "내 위치 자동으로
  사용" 버튼으로 Geolocation을 켤 수 있게 옵션으로만 둔다.
- KAKAO_JS_KEY가 없으면 지도 없이 딥링크 버튼만 보여준다.
- main.py의 ui.sub_pages가 이 함수를 "/map" 콘텐츠로 호출하므로 @ui.page 데코레이터와
  frame() 호출은 여기서 하지 않는다(헤더는 root_page에서 한 번만 그린다).
"""

import json
import os
import re
from urllib.parse import quote

from nicegui import app, ui

from cohorts import get_main_location
from theme import ACCENT, INK, MUTED, page_header

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


def map_page():
    cohort = app.storage.user.get("selected_cohort")
    location = get_main_location(cohort)

    if not location:
        page_header("place", "오시는길")
        ui.label("먼저 기수를 선택해주세요.").classes("text-gray-500")
        return

    page_header("place", "오시는길", "", kicker="LOCATION")

    search_link = f"https://map.kakao.com/link/search/{quote(location)}"

    with ui.card().classes("w-full p-5 mb-4 kdt-fade-up"):
        ui.label(cohort).classes("text-xs font-bold").style(f"color:{ACCENT};")
        ui.label(location).classes("text-lg font-extrabold mt-0.5").style(f"color:{INK};")

    if not KAKAO_JS_KEY:
        ui.label("지도 미리보기는 KAKAO_JS_KEY가 설정되면 표시됩니다. 지금은 길찾기 링크만 이용해주세요.").classes(
            "text-sm mb-3"
        ).style(f"color:{MUTED};")
        ui.link("카카오맵으로 길찾기", search_link, new_tab=True).classes(
            "block w-full text-center bg-yellow-300 text-gray-900 font-bold rounded-xl py-3 no-underline"
        )
        return

    keyword = _place_keyword(location)
    known_address = _KNOWN_ADDRESSES.get(keyword)

    # 출발지 수동 입력 - 자동으로 위치를 잡지 않고, 사용자가 직접 입력한 걸 우선한다.
    with ui.card().classes("w-full p-4 mb-4 kdt-fade-up"):
        ui.label("출발지에서 경로 보기").classes("text-sm font-bold mb-2").style(f"color:{INK};")
        with ui.row().classes("w-full items-center gap-2 flex-nowrap"):
            origin_input = ui.input(
                placeholder="출발지 주소나 건물명 (예: 대구역, OO아파트, 시청 등)"
            ).classes("flex-grow").props("dense outlined")

            def _find_route_from_text():
                text = (origin_input.value or "").strip()
                if not text:
                    ui.notify("출발지를 입력해주세요.", type="warning")
                    return
                ui.run_javascript(f"window.kdtRouteFromText && window.kdtRouteFromText({json.dumps(text)});")

            ui.button("경로 찾기", icon="directions", on_click=_find_route_from_text).props(
                "no-caps unelevated color=primary"
            )
        ui.button(
            "내 위치 자동으로 사용",
            icon="my_location",
            on_click=lambda: ui.run_javascript(
                "window.kdtRouteFromGeolocation && window.kdtRouteFromGeolocation();"
            ),
        ).props("flat no-caps dense").classes("mt-1 text-xs px-0").style(f"color:{MUTED};")

    with ui.card().classes("w-full p-3 kdt-reveal"):
        ui.html(
            f"""
            <div id="kdt-map" style="width:100%;height:520px;border-radius:12px;"></div>
            <div id="kdt-route-info" style="display:none;margin-top:12px;padding:10px 14px;
                 border-radius:10px;font-size:0.85rem;font-weight:700;"></div>
            """
        )
        with ui.row().classes("items-center gap-3 mt-3 flex-nowrap"):
            ui.link("카카오맵 앱으로 길찾기", search_link, new_tab=True).props("id=kdt-route-link").classes(
                "px-4 py-2.5 rounded-xl font-bold no-underline text-sm whitespace-nowrap"
            ).style("background:#FEE500;color:#191919;")
            ui.label(
                "이 페이지에서 자동으로 경로가 안 그려지면 이 버튼으로 카카오맵 앱/웹에서 바로 안내받을 수 있어요."
            ).classes("text-xs").style(f"color:{MUTED};")

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
            var routeColor = {json.dumps(ACCENT)};

            // initMap()이 끝나야 채워지는 것들 - 그 전에 버튼이 눌리면 "아직 준비 중" 안내로 막는다.
            var map = null;
            var geocoder = null;
            var places = null;
            var destLatG = null;
            var destLngG = null;
            var myLocationOverlay = null;
            var routeLine = null;

            function showError(container, msg) {{
              container.innerHTML = "<p style='padding:16px;color:#c0392b;font-size:0.85rem;'>" + msg + "</p>";
            }}

            function setRouteInfo(text, visible, isError) {{
              var info = document.getElementById('kdt-route-info');
              if (!info) return;
              info.textContent = text || "";
              info.style.display = visible ? "block" : "none";
              info.style.color = isError ? "#c0392b" : routeColor;
              info.style.background = isError ? "#c0392b14" : (routeColor + "14");
            }}

            // 구글맵 스타일의 "내 위치" 파란 점 - 목적지 핀과 모양이 완전히 달라서
            // 지도 위에서 어느 게 내 위치고 어느 게 목적지인지 헷갈리지 않는다.
            // 다시 검색할 때마다 이전 점은 지우고 새로 찍는다.
            function placeMyLocationDot(lat, lng) {{
              if (myLocationOverlay) {{
                myLocationOverlay.setMap(null);
              }}
              myLocationOverlay = new kakao.maps.CustomOverlay({{
                map: map,
                position: new kakao.maps.LatLng(lat, lng),
                content:
                  '<div style="width:16px;height:16px;border-radius:50%;' +
                  'background:#4285F4;border:3px solid #fff;' +
                  'box-shadow:0 0 0 2px #4285F4, 0 2px 6px rgba(0,0,0,0.35);"></div>',
                yAnchor: 0.5,
                xAnchor: 0.5,
                zIndex: 10
              }});
            }}

            // 출발지 좌표가 정해지면(수동 입력이든 위치 자동감지든) 여기서 공통으로 경로를
            // 조회해서 그린다. 다시 호출되면 이전 경로선은 지우고 새로 그린다.
            // onFail이 주어지면(=검색 결과 후보가 더 있을 때) "경로 자체를 못 찾음" 실패 시
            // 바로 에러 메시지를 띄우지 않고 onFail을 불러서 다음 후보를 시도할 기회를 준다.
            function startRouteFromCoords(originLat, originLng, onFail) {{
              if (!map || destLatG === null) {{
                setRouteInfo("지도가 아직 준비 중입니다. 잠시 후 다시 시도해주세요.", true, true);
                return;
              }}

              placeMyLocationDot(originLat, originLng);
              setRouteInfo("경로 계산 중...", true, false);

              var originParam = originLng + "," + originLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/directions?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam);

              fetch(url).then(function(res) {{
                return res.json().then(function(body) {{
                  if (!res.ok) {{
                    var err = new Error("directions request failed");
                    err.body = body;
                    throw err;
                  }}
                  return body;
                }});
              }}).then(function(data) {{
                if (!data.path || data.path.length === 0) {{
                  if (onFail) {{ onFail(); return; }}
                  setRouteInfo("경로를 찾을 수 없습니다. 길찾기 버튼으로 이용해주세요.", true, true);
                  return;
                }}

                var linePath = data.path.map(function(p) {{
                  return new kakao.maps.LatLng(p[1], p[0]);
                }});

                if (routeLine) {{
                  routeLine.setMap(null);
                }}
                routeLine = new kakao.maps.Polyline({{
                  map: map,
                  path: linePath,
                  strokeWeight: 5,
                  strokeColor: routeColor,
                  strokeOpacity: 0.85,
                  strokeStyle: "solid"
                }});

                // NiceGUI처럼 지도 컨테이너 크기가 생성 이후에 바뀌는(반응형 레이아웃) 환경에서는
                // 카카오맵이 내부에 캐싱해둔 픽셀 크기가 실제 DOM 크기와 어긋나서 setBounds/좌표
                // 계산이 엉뚱한 곳으로 튀는 게 잘 알려진 증상이다. relayout()으로 크기를 다시
                // 맞춰준 다음 자동맞춤(setBounds)을 호출하면 해결된다. 직접 줌레벨을 계산하는
                // 방식은 거리별로 미세조정이 계속 필요해서(1차 시도 때 너무 확대돼 버림) 대신
                // 카카오 SDK가 알아서 모든 좌표가 화면에 들어오게 계산해주는 setBounds를 쓴다.
                map.relayout();

                var bounds = new kakao.maps.LatLngBounds();
                bounds.extend(new kakao.maps.LatLng(originLat, originLng));
                bounds.extend(new kakao.maps.LatLng(destLatG, destLngG));
                linePath.forEach(function(p) {{ bounds.extend(p); }});
                // 패딩 없이 setBounds만 쓰면 출발/도착 마커가 지도 테두리에 딱 붙어서 잘려
                // 보일 수 있어서, 네 방향에 여백을 좀 준다.
                map.setBounds(bounds, 60, 60, 60, 60);

                var distanceKm = (data.distance_m || 0) / 1000;
                if (data.distance_m) {{
                  var km = distanceKm.toFixed(1);
                  var min = Math.round((data.duration_s || 0) / 60);
                  setRouteInfo("입력하신 위치에서 약 " + km + "km · " + min + "분 (교통상황에 따라 달라질 수 있어요)", true, false);
                }} else {{
                  setRouteInfo("", false, false);
                }}
              }}).catch(function(err) {{
                // "경로 자체를 못 찾음"(no_route)이고 시도할 다음 후보가 있으면 그쪽으로 넘긴다.
                var detail = err && err.body && err.body.detail;
                var isNoRoute = detail && typeof detail === "object" && detail.reason === "no_route";
                if (isNoRoute && onFail) {{
                  onFail();
                  return;
                }}
                var msg = isNoRoute
                  ? "이 출발지 주변에서 차로 갈 수 있는 경로를 찾지 못했어요. 더 구체적인 위치(예: 정확한 출입구, 인근 도로명)로 다시 입력해보시거나, 길찾기 버튼을 이용해주세요."
                  : "경로를 불러오지 못했습니다. 카카오맵 앱으로 길찾기 버튼을 이용해주세요.";
                setRouteInfo(msg, true, true);
              }});
            }}

            // POI 검색 결과가 여러 개일 때, 1등 후보가 도로 탐색 실패로 막히면 다음 후보로
            // 순서대로 재시도한다. 큰 시설(역/터미널 등)은 대표 좌표가 건물 한가운데로 잡혀서
            // 차량 진입 도로에 안 붙는 경우가 흔한데, 같은 검색의 다른 후보(주차장/입구 등)는
            // 도로에 붙어있는 경우가 많아서 이렇게 하면 실사용에서 성공률이 꽤 올라간다.
            function tryOriginCandidates(candidates, idx) {{
              if (idx >= candidates.length) {{
                setRouteInfo(
                  "이 위치 주변에서 차로 갈 수 있는 경로를 찾지 못했어요. 더 구체적인 위치(예: 정확한 출입구, 인근 도로명)로 다시 입력해보시거나, 길찾기 버튼을 이용해주세요.",
                  true, true
                );
                return;
              }}
              var candidate = candidates[idx];
              startRouteFromCoords(parseFloat(candidate.y), parseFloat(candidate.x), function() {{
                tryOriginCandidates(candidates, idx + 1);
              }});
            }}

            // "내 위치 자동으로 사용" 버튼 전용 - 사용자가 명시적으로 눌렀을 때만 위치 권한을 요청한다.
            window.kdtRouteFromGeolocation = function() {{
              if (!navigator.geolocation) {{
                setRouteInfo("이 브라우저는 위치 감지를 지원하지 않습니다. 출발지를 직접 입력해주세요.", true, true);
                return;
              }}
              setRouteInfo("내 위치 확인 중...", true, false);
              navigator.geolocation.getCurrentPosition(function(pos) {{
                startRouteFromCoords(pos.coords.latitude, pos.coords.longitude);
              }}, function() {{
                setRouteInfo("위치 권한이 거부됐거나 가져오지 못했습니다. 출발지를 직접 입력해주세요.", true, true);
              }}, {{ timeout: 8000 }});
            }};

            // 출발지 텍스트 입력 - keywordSearch(POI) 먼저, 실패하면 주소 검색으로 폴백.
            window.kdtRouteFromText = function(text) {{
              if (!map || !places || !geocoder) {{
                setRouteInfo("지도가 아직 준비 중입니다. 잠시 후 다시 시도해주세요.", true, true);
                return;
              }}
              setRouteInfo("\\"" + text + "\\" 위치 찾는 중...", true, false);

              places.keywordSearch(text, function(data, status) {{
                if (status === kakao.maps.services.Status.OK && data.length > 0) {{
                  // 최대 4개 후보까지만 순서대로 시도 (그 이상은 실사용에서 큰 의미 없이 느려지기만 함)
                  tryOriginCandidates(data.slice(0, 4), 0);
                  return;
                }}
                geocoder.addressSearch(text, function(result, gStatus) {{
                  if (gStatus === kakao.maps.services.Status.OK) {{
                    startRouteFromCoords(parseFloat(result[0].y), parseFloat(result[0].x));
                  }} else {{
                    setRouteInfo(
                      "입력하신 위치를 찾지 못했습니다. 더 구체적으로 입력해보세요 (예: 'OO역', 'OO구 OO동').",
                      true, true
                    );
                  }}
                }});
              }});
            }};

            // #kdt-map은 NiceGUI가 클라이언트에서 Vue로 그리는 DOM이라, 이 스크립트가
            // 실행되는 시점엔 아직 화면에 존재하지 않을 수 있다. 생길 때까지 잠깐씩 재시도한다.
            // 그리고 "DOM에 존재한다"와 "실제 화면 크기(레이아웃)를 다 잡았다"는 다른 얘기다 -
            // Vue가 요소를 막 넣은 직후에는 태그는 있어도 offsetWidth/Height가 0일 수 있는데,
            // 이 상태에서 지도를 만들면 카카오맵이 크기를 0으로 기억해버려서, 나중에 relayout을
            // 불러도 "아주 작은 화면에 전체 경로를 욱여넣으려는" 계산이 되어 지도가 확 축소된
            // 화면(한국 전체~일본까지 보이는 수준)으로 나온다. 그래서 크기가 실제로 잡힐 때까지
            // 기다렸다가 지도를 만든다.
            function waitForContainer(retriesLeft) {{
              var container = document.getElementById('kdt-map');
              var ready = container && container.offsetWidth > 0 && container.offsetHeight > 0;
              if (!ready) {{
                if (retriesLeft > 0) {{
                  setTimeout(function() {{ waitForContainer(retriesLeft - 1); }}, 100);
                  return;
                }}
                // 5초 넘게 기다렸는데도 컨테이너 크기가 안 잡히면(느린 네트워크 등) 아무 설명
                // 없이 빈 화면으로 남기지 말고, 최소한 원인과 대안을 알려준다.
                setRouteInfo("지도를 불러오는 데 시간이 오래 걸리고 있습니다. 새로고침하거나 길찾기 버튼을 이용해주세요.", true, true);
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
                map = new kakao.maps.Map(container, {{ center: center, level: 4 }});

                // waitForContainer에서 크기를 확인하고 들어왔어도, 이후에 사이드바 열림/닫힘,
                // 창 크기 변경, 폰트 로딩 등으로 컨테이너 크기가 또 바뀔 수 있다. 그때마다
                // 자동으로 relayout해서 카카오맵이 기억하는 크기가 항상 실제 화면과 맞도록
                // 감시해둔다 (구형 브라우저 대비 ResizeObserver 미지원 시 window resize로 대체).
                if (typeof ResizeObserver !== 'undefined') {{
                  new ResizeObserver(function() {{
                    if (map) map.relayout();
                  }}).observe(container);
                }} else {{
                  window.addEventListener('resize', function() {{
                    if (map) map.relayout();
                  }});
                }}

                // 목적지 핀을 기본 카카오 마커 대신 브랜드 컬러로 - "내 위치" 파란 점과
                // 시각적으로 확실히 구분되게 한다.
                var pinSvg = 'data:image/svg+xml;charset=UTF-8,' + encodeURIComponent(
                  '<svg xmlns="http://www.w3.org/2000/svg" width="32" height="40" viewBox="0 0 32 40">' +
                  '<path d="M16 0C7.163 0 0 7.163 0 16c0 12 16 24 16 24s16-12 16-24C32 7.163 24.837 0 16 0z" fill="' + routeColor + '"/>' +
                  '<circle cx="16" cy="15" r="6.5" fill="#fff"/>' +
                  '</svg>'
                );
                var pinImage = new kakao.maps.MarkerImage(
                  pinSvg, new kakao.maps.Size(32, 40), {{ offset: new kakao.maps.Point(16, 40) }}
                );

                function placeMarker(y, x, label) {{
                  var coords = new kakao.maps.LatLng(y, x);
                  new kakao.maps.Marker({{ map: map, position: coords, image: pinImage, title: label }});
                  // 지도 생성 시점엔 NiceGUI(Vue)가 아직 컨테이너 최종 크기를 확정하기 전일 수
                  // 있어서, 첫 마커를 찍을 때도 relayout으로 크기를 다시 맞춘 뒤 중심을 잡는다.
                  map.relayout();
                  map.setCenter(coords);
                  var link = document.getElementById('kdt-route-link');
                  if (link) {{
                    link.href = "https://map.kakao.com/link/to/" + encodeURIComponent(label) + "," + y + "," + x;
                  }}
                  // 카카오 API가 좌표를 문자열로 주는 경우가 있어서, 이후 숫자 연산(중간점 계산 등)에서
                  // "문자열 이어붙이기"로 잘못 처리돼 NaN이 나오지 않도록 여기서 숫자로 확정해둔다.
                  destLatG = parseFloat(y);
                  destLngG = parseFloat(x);
                }}

                geocoder = new kakao.maps.services.Geocoder();
                places = new kakao.maps.services.Places();

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
