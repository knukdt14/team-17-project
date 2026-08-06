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
- ui.sub_pages는 탭 이동을 브라우저 새로고침 없이 client-side로 처리하는데,
  ui.add_body_html()로 넣은 <script>는 이런 재진입 상황에서 다시 실행되지 않을 수 있다
  (다른 탭 갔다가 "오시는길"로 돌아오면 지도가 아예 안 뜨는 문제로 나타남). 그래서 지도
  초기화/경로 로직은 ui.run_javascript()로 호출한다 - 이건 map_page()가 실행될 때마다
  "지금 붙어있는 클라이언트에게 이 JS를 실행해라"고 그때그때 보내는 방식이라 재진입에도
  항상 실행된다.
- 카카오맵 SDK <script>는 여기서 붙이지 않는다. 처음엔 이 함수 안에서 JS로 동적으로
  <script> 태그를 만들어 붙였는데(autoload=false + kakao.maps.load() 방식), sub_pages
  재진입 시 간헐적으로 초기화가 멈추는(새로고침해야만 되는) 문제가 있었다. 그래서
  main.py의 root_page()가 진짜 페이지 로드 시점에 <head>에 한 번만 선언적으로 붙이는
  방식으로 되돌렸다(예전에 항상 안정적으로 동작하던 방식과 동일). 여기서는 그게 준비될
  때까지 window.kakao.maps.LatLng 존재 여부만 기다린다(waitUntilReady).
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
    "경일대학교 산학교육관": "경상북도 경산시 하양읍 부호리 359",
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
        # 검색하면 여러 후보(예: "동대구역"의 역 본체/1호선/대경선/주차장 등)가 나올 수 있는데,
        # 지금까지는 자동으로 순서대로 시도만 했다. 이 리스트에 후보들을 보여주면 사용자가
        # 원하는 걸 직접 골라서 바로 경로를 볼 수 있다 - 자동 시도 동작 자체는 그대로 두고,
        # 추가 선택지로만 얹는다(JS의 renderCandidates()가 채운다).
        ui.html('<div id="kdt-candidates" style="display:none;"></div>').classes("w-full")
        with ui.row().classes("items-center gap-4 mt-1 flex-wrap"):
            ui.button(
                "내 위치 자동으로 사용",
                icon="my_location",
                on_click=lambda: ui.run_javascript(
                    "window.kdtRouteFromGeolocation && window.kdtRouteFromGeolocation();"
                ),
            ).props("flat no-caps dense").classes("text-xs px-0").style(f"color:{MUTED};")
            ui.button(
                "대중교통으로 보기",
                icon="directions_transit",
                on_click=lambda: ui.run_javascript("window.kdtShowTransit && window.kdtShowTransit();"),
            ).props("flat no-caps dense").classes("text-xs px-0").style(f"color:{MUTED};")

    with ui.card().classes("w-full p-3 kdt-reveal"):
        # 카드(w-full)는 flex 컨테이너라서, ui.html()이 만드는 wrapper div도 명시적으로
        # w-full을 안 주면 flex item 기본 동작(shrink-to-fit)으로 폭이 0에 수렴한다.
        # 그러면 안의 #kdt-map(style width:100%)도 "0의 100%"라 결국 0폭이 되고, 카카오맵이
        # 그 순간의 컨테이너 크기를 기준으로 지도를 만들어서 화면 왼쪽 일부에만 좁게 그려진다.
        ui.html(
            f"""
            <div id="kdt-map" style="width:100%;height:520px;border-radius:12px;"></div>
            <div id="kdt-route-info" style="display:none;margin-top:12px;padding:10px 14px;
                 border-radius:10px;font-size:0.85rem;font-weight:700;"></div>
            <div id="kdt-transit-info" style="display:none;margin-top:12px;"></div>
            """
        ).classes("w-full")
        with ui.row().classes("items-center gap-3 mt-3 flex-nowrap"):
            ui.link("카카오맵 앱으로 길찾기", search_link, new_tab=True).props("id=kdt-route-link").classes(
                "px-4 py-2.5 rounded-xl font-bold no-underline text-sm whitespace-nowrap"
            ).style("background:#FEE500;color:#191919;")
            ui.label(
                "이 페이지에서 자동으로 경로가 안 그려지면 이 버튼으로 카카오맵 앱/웹에서 바로 안내받을 수 있어요."
            ).classes("text-xs").style(f"color:{MUTED};")

    # main.py가 ui.sub_pages로 화면을 client-side 라우팅하면서 map_page()가 매번 다시
    # 호출되는데, ui.add_body_html()로 넣은 <script>는 (특히 sub_pages 전환처럼 브라우저가
    # 실제로 새로고침되지 않는 상황에서) 두 번째 방문부터는 다시 실행이 안 되는 경우가 있다
    # (NiceGUI GitHub 이슈로도 보고된 문제). 그래서 ui.run_javascript()로 바꿨다 - 이건
    # "지금 붙어있는 클라이언트한테 이 JS를 실행해라"라고 그때그때 보내는 방식이라, 처음
    # 진입이든 tab 이동으로 재진입이든 map_page()가 호출될 때마다 항상 실행된다.
    # 카카오맵 SDK <script> 자체는 여기서 붙이지 않는다 - main.py의 root_page()가 진짜
    # 페이지 로드 시점에 <head>에 한 번만 선언적으로 붙여준다(예전에 항상 잘 되던 방식).
    # 여기서는 그게 준비될 때까지 window.kakao.maps.LatLng 존재 여부만 기다린다.
    ui.run_javascript(
        f"""
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
            var altRouteLines = [];
            var transitLines = [];
            // "대중교통으로 보기"가 자동차 경로랑 같은 출발지를 쓸 수 있게, 마지막으로 쓴
            // 출발지 좌표를 기억해둔다.
            var lastOriginLat = null;
            var lastOriginLng = null;

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
            function clearAltRoutes() {{
              altRouteLines.forEach(function(line) {{ line.setMap(null); }});
              altRouteLines = [];
            }}

            function clearTransit() {{
              transitLines.forEach(function(line) {{ line.setMap(null); }});
              transitLines = [];
              var info = document.getElementById('kdt-transit-info');
              if (info) {{ info.style.display = 'none'; info.innerHTML = ''; }}
            }}

            // 메인 경로(추천 기준) 말고, 다른 기준(최소시간/최단거리)으로도 한 번씩 더 불러서
            // 옅고 얇은 선으로 같이 그려준다 - 진짜 카카오맵 앱처럼 여러 경로를 한 화면에서
            // 비교해볼 수 있게. 메인 경로 요청이 이미 성공한 뒤에만 "추가"로 시도하는 것이라,
            // 이게 실패해도(예: 카카오맵 API가 그 기준으로는 경로를 못 찾음) 메인 경로 표시에는
            // 전혀 영향이 없다.
            function fetchAltRoutes(originLat, originLng) {{
              var altStyles = {{
                TIME: {{ color: "#2E7D32", label: "최소시간" }},
                DISTANCE: {{ color: "#6B7280", label: "최단거리" }}
              }};
              ["TIME", "DISTANCE"].forEach(function(priority) {{
                var originParam = originLng + "," + originLat;
                var destParam = destLngG + "," + destLatG;
                var url = "/api/directions?origin=" + encodeURIComponent(originParam)
                        + "&destination=" + encodeURIComponent(destParam)
                        + "&priority=" + priority;
                fetch(url).then(function(res) {{ return res.ok ? res.json() : null; }}).then(function(data) {{
                  if (!data || !data.path || data.path.length === 0) return;
                  var altPath = data.path.map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                  var style = altStyles[priority];
                  altRouteLines.push(new kakao.maps.Polyline({{
                    map: map,
                    path: altPath,
                    strokeWeight: 4,
                    strokeColor: style.color,
                    strokeOpacity: 0.55,
                    strokeStyle: "shortdash"
                  }}));
                }}).catch(function() {{ /* 대안 경로는 실패해도 조용히 무시 - 메인 경로만 있어도 충분 */ }});
              }});
            }}

            function startRouteFromCoords(originLat, originLng, onFail) {{
              if (!map || destLatG === null) {{
                setRouteInfo("지도가 아직 준비 중입니다. 잠시 후 다시 시도해주세요.", true, true);
                return;
              }}

              lastOriginLat = originLat;
              lastOriginLng = originLng;
              clearAltRoutes();
              clearTransit();
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

                fetchAltRoutes(originLat, originLng);
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

            // keywordSearch 결과가 여러 개일 때, 자동 재시도(tryOriginCandidates)만 믿지 않고
            // 사용자가 직접 원하는 후보를 골라 바로 경로를 볼 수 있게 목록으로 보여준다.
            // NiceGUI의 ui.html() 살균 처리를 거치지 않고(=onclick 안 씹힘) 여기서 직접
            // DOM을 만들고 addEventListener를 붙이는 순수 JS라 문제 없다.
            function renderCandidates(candidates) {{
              var box = document.getElementById('kdt-candidates');
              if (!box) return;
              if (!candidates || candidates.length === 0) {{
                box.style.display = 'none';
                box.innerHTML = '';
                return;
              }}
              var html = '<div style="font-size:0.75rem;font-weight:700;margin:6px 0 4px;color:' + routeColor + ';">검색 결과 - 원하는 위치를 골라주세요</div>';
              html += '<div style="display:flex;flex-wrap:wrap;gap:6px;">';
              candidates.slice(0, 6).forEach(function(c, idx) {{
                var addr = c.road_address_name || c.address_name || '';
                html += '<button type="button" data-idx="' + idx + '" style="' +
                  'border:1px solid ' + routeColor + '55;background:#fff;color:' + routeColor + ';' +
                  'border-radius:999px;padding:5px 12px;font-size:0.75rem;font-weight:600;cursor:pointer;">' +
                  (c.place_name || '이름 없음') + (addr ? ' · ' + addr : '') +
                  '</button>';
              }});
              html += '</div>';
              box.innerHTML = html;
              box.style.display = 'block';
              box.querySelectorAll('button[data-idx]').forEach(function(btn) {{
                btn.addEventListener('click', function() {{
                  var c = candidates[parseInt(btn.getAttribute('data-idx'), 10)];
                  startRouteFromCoords(parseFloat(c.y), parseFloat(c.x));
                }});
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
                  // 후보 목록을 바로 보여주고(사용자가 직접 고를 수 있게), 동시에 1등 후보부터
                  // 자동으로도 시도한다 - 아무것도 안 고르고 기다리기만 해도 이전처럼 동작한다.
                  renderCandidates(data);
                  // 최대 4개 후보까지만 순서대로 시도 (그 이상은 실사용에서 큰 의미 없이 느려지기만 함)
                  tryOriginCandidates(data.slice(0, 4), 0);
                  return;
                }}
                renderCandidates([]);
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

            // "대중교통으로 보기" 버튼 전용. 자동차 경로(startRouteFromCoords)와는 완전히 다른
            // API(/api/transit)와 다른 그리기 로직을 쓰는 별도 기능이라, 이게 실패해도 자동차
            // 경로 기능에는 전혀 영향이 없다. 도보/버스/지하철 구간을 각각 다른 색으로 그리고,
            // 구간별 안내 텍스트도 같이 보여준다.
            var transitModeStyle = {{
              WALK:   {{ color: "#9CA3AF", weight: 4, style: "shortdot",  label: "도보" }},
              BUS:    {{ color: "#2563EB", weight: 5, style: "solid",     label: "버스" }},
              SUBWAY: {{ color: "#059669", weight: 5, style: "solid",     label: "지하철" }}
            }};

            window.kdtShowTransit = function() {{
              if (lastOriginLat === null || destLatG === null) {{
                setRouteInfo("먼저 출발지를 입력해서 자동차 경로를 한 번 찾아주세요 (같은 출발지를 대중교통 경로에도 씁니다).", true, true);
                return;
              }}

              var info = document.getElementById('kdt-transit-info');
              if (info) {{
                info.style.display = 'block';
                info.innerHTML = "<div style='padding:10px 14px;border-radius:10px;font-size:0.85rem;font-weight:700;color:" + routeColor + ";background:" + routeColor + "14;'>대중교통 경로 찾는 중...</div>";
              }}

              var originParam = lastOriginLng + "," + lastOriginLat;
              var destParam = destLngG + "," + destLatG;
              var url = "/api/transit?origin=" + encodeURIComponent(originParam)
                      + "&destination=" + encodeURIComponent(destParam);

              fetch(url).then(function(res) {{
                return res.json().then(function(body) {{
                  if (!res.ok) {{
                    var err = new Error("transit request failed");
                    err.body = body;
                    throw err;
                  }}
                  return body;
                }});
              }}).then(function(data) {{
                var route = data.routes && data.routes[0];
                if (!route) {{
                  if (info) info.innerHTML = "<div style='padding:10px 14px;border-radius:10px;font-size:0.85rem;font-weight:700;color:#c0392b;background:#c0392b14;'>대중교통 경로를 찾을 수 없습니다.</div>";
                  return;
                }}

                clearTransit();
                var bounds = new kakao.maps.LatLngBounds();
                var stepHtml = [];

                route.steps.forEach(function(step) {{
                  var style = transitModeStyle[step.mode] || transitModeStyle.WALK;
                  var path = (step.path || []).map(function(p) {{ return new kakao.maps.LatLng(p[1], p[0]); }});
                  if (path.length > 1) {{
                    transitLines.push(new kakao.maps.Polyline({{
                      map: map,
                      path: path,
                      strokeWeight: style.weight,
                      strokeColor: style.color,
                      strokeOpacity: 0.85,
                      strokeStyle: style.style
                    }}));
                    path.forEach(function(p) {{ bounds.extend(p); }});
                  }}
                  var min = Math.round((step.duration_s || 0) / 60);
                  var label = style.label + (step.vehicle_name ? " " + step.vehicle_name : "");
                  stepHtml.push(
                    "<span style='display:inline-flex;align-items:center;gap:4px;padding:4px 10px;margin:2px 4px 2px 0;" +
                    "border-radius:999px;font-size:0.72rem;font-weight:700;color:#fff;background:" + style.color + ";'>" +
                    label + (min > 0 ? " · " + min + "분" : "") + "</span>"
                  );
                }});

                if (transitLines.length > 0) {{
                  map.relayout();
                  map.setBounds(bounds, 60, 60, 60, 60);
                }}

                var km = ((route.distance_m || 0) / 1000).toFixed(1);
                var totalMin = Math.round((route.duration_s || 0) / 60);
                var fareText = route.fare != null ? " · 요금 약 " + route.fare.toLocaleString() + "원" : "";
                var summary =
                  "<div style='padding:10px 14px;border-radius:10px 10px 0 0;font-size:0.85rem;font-weight:700;color:" + routeColor + ";background:" + routeColor + "14;'>" +
                  "대중교통 약 " + km + "km · " + totalMin + "분 · 환승 " + (route.transfers || 0) + "회" + fareText +
                  "</div>" +
                  "<div style='padding:8px 14px;background:#fff;border:1px solid " + routeColor + "22;border-top:none;border-radius:0 0 10px 10px;'>" +
                  stepHtml.join("") +
                  "</div>";
                // clearTransit()이 이전 결과를 지우면서 패널을 숨겨놓기 때문에(재검색 대비),
                // 새 결과를 채운 지금 다시 보이게 켜줘야 한다.
                if (info) {{
                  info.innerHTML = summary;
                  info.style.display = 'block';
                }}
              }}).catch(function(err) {{
                var detail = err && err.body && err.body.detail;
                var msg = (detail && typeof detail === "object") ? (detail.result_msg || "대중교통 경로를 불러오지 못했습니다.")
                  : (typeof detail === "string" ? detail : "대중교통 경로를 불러오지 못했습니다.");
                if (info) info.innerHTML = "<div style='padding:10px 14px;border-radius:10px;font-size:0.85rem;font-weight:700;color:#c0392b;background:#c0392b14;'>" + msg + "</div>";
              }});
            }};

            // 두 가지가 다 준비돼야 지도를 만들 수 있다:
            // 1) #kdt-map DOM - NiceGUI가 클라이언트에서 Vue로 그리는 요소라 이 스크립트가
            //    실행되는 시점엔 아직 없거나, 있어도 "실제 화면 크기(레이아웃)"는 아직 0일 수
            //    있다(태그만 막 들어간 직후). 크기가 0인 채로 지도를 만들면 카카오맵이 크기를
            //    0으로 기억해버려서 지도가 확 축소된 화면(한국 전체~일본까지 보이는 수준)으로
            //    나온다.
            // 2) 카카오맵 SDK(window.kakao.maps.LatLng) - root_page()의 <head> 스크립트가
            //    비동기로 로드/초기화되는 중이라, 우리 스크립트가 그보다 먼저 실행됐을 수 있다.
            // 그래서 둘 다 실제로 준비될 때까지 잠깐씩(최대 10초) 재시도한다.
            function waitUntilReady(retriesLeft) {{
              var container = document.getElementById('kdt-map');
              var containerReady = container && container.offsetWidth > 0 && container.offsetHeight > 0;
              var sdkReady = window.kakao && window.kakao.maps && window.kakao.maps.LatLng;
              if (!containerReady || !sdkReady) {{
                if (retriesLeft > 0) {{
                  setTimeout(function() {{ waitUntilReady(retriesLeft - 1); }}, 100);
                  return;
                }}
                // 10초 넘게 기다렸는데도 준비가 안 되면(느린 네트워크, SDK 로드 실패 등) 아무
                // 설명 없이 빈 화면으로 남기지 말고, 최소한 원인과 대안을 알려준다.
                var reason = !sdkReady
                  ? "카카오맵 스크립트를 불러오지 못했습니다 (네트워크 차단 또는 잘못된 키)."
                  : "지도를 불러오는 데 시간이 오래 걸리고 있습니다.";
                setRouteInfo(reason + " 새로고침하거나 길찾기 버튼을 이용해주세요.", true, true);
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

                // waitUntilReady에서 크기를 확인하고 들어왔어도, 이후에 사이드바 열림/닫힘,
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

            waitUntilReady(100);
          }})();
        """
    )
