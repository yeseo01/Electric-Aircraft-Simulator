# CSV의 waypoint를 대시보드 그래프로 표시하기

이번 단계에서는 기존 API 응답을 그대로 사용하고 React 화면과 그래프를 추가했다.
참고 이미지의 짙은 남색 배경, 청록색 강조, 큰 경로 패널과 작은 정보 카드를 반영했다.
파일을 고르기 전에는 안내와 빈 값을 표시하며, 업로드한 CSV의 결과만 그린다.

## 1. 화면을 역할별로 배치하기

`src/App.tsx`의 `workspace-grid` 안에 네 패널을 배치했다.

| 패널 | 역할 |
| --- | --- |
| Flight route | 동·북 좌표로 경로 표시, 출발·도착 표시 |
| Mission input | 기존 CSV 선택·전송·오류·재시도 기능 |
| Altitude profile | 경과 시간에 따른 상대 기압고도 표시 |
| Preview summary | 실제 샘플 수·waypoint 수·비행 시간·기준 고도 표시 |

`App.css`의 CSS Grid로 큰 화면에서 두 열을 사용한다. 900px 이하에서는 한 열로
바꾸고 입력 패널을 먼저 배치한다. `index.css`와 `CsvFilePicker.css`도 같은 색상과
타이포그래피로 맞췄다. 새로운 시뮬레이터 계산이나 배터리 수치를 만들지는 않았다.

## 2. ECharts는 무엇인가?

ECharts는 브라우저에서 차트를 그리는 JavaScript 라이브러리다. React는 패널과
입력 상태를 관리하고, ECharts는 숫자 데이터를 축·선·마커·툴팁으로 그린다.

가장 간단한 구조는 아래와 같다. `element`는 크기가 지정된 HTML 요소다.

```ts
const chart = init(element, undefined, { renderer: 'svg' })
chart.setOption({
  xAxis: { type: 'value' },
  yAxis: { type: 'value' },
  series: [{ type: 'line', data: [[0, 0], [10, 20], [30, 15]] }],
})
```

`init`은 요소에 차트를 만들고, `setOption`은 그릴 데이터와 표현 방법을 설정한다.
실제 코드에서는 필요한 Line·Scatter·Grid·Tooltip·DataZoom·SVG 모듈만 등록한다.
의존성은 `package.json`, 설치 버전은 `package-lock.json`에 기록했다.
빌드에서 차트와 SVG 렌더러를 별도 파일로 나눠 한 파일이 지나치게 커지는 것도 피했다.

## 3. JSON을 차트 데이터로 바꾸기

API의 waypoint 하나는 이런 모양이다.

```ts
{
  time_s: 10,
  east_m: 200,
  north_m: 100,
  relative_altitude_m: 30,
}
```

핵심 변환은 `map`이다.

```ts
const route = preview.waypoints.map(p => [p.east_m, p.north_m])
const altitude = preview.waypoints.map(p => [p.time_s, p.relative_altitude_m])
```

`map`은 원본 배열의 순서를 유지하면서 각 항목을 새 모양으로 바꾼다.
경로의 x는 동쪽 거리, y는 북쪽 거리다. 동쪽 거리로 정렬하면 되돌아가는 경로가
달라지므로 실제 비행 순서를 유지한다. 고도 그래프는 실제 경과 시간을 사용하며,
단순 배열 인덱스나 일정한 간격으로 바꾸지 않는다.

실제 경로 데이터에는 툴팁용 시간과 고도도 함께 담았다. 첫 항목과 마지막 항목은
별도 scatter series로 표시하여 출발·도착을 구분한다. 선의 `smooth`를 끄고
원본 waypoint를 직선으로 연결하여 측정 사이에 임의의 곡선을 만들지 않는다.

## 4. 단위와 축척을 정확하게 표시하기

- 경로: `east_m`와 `north_m`, 단위 m. 첫 샘플 주변의 로컬 좌표다.
- 고도: 첫 CSV 샘플의 기압고도를 뺀 변화량이다. GPS 고도나 지상고가 아니다.
- 시간: 첫 샘플부터 경과한 초다.

`routeBounds()`는 경로 전체가 들어가도록 여백을 잡고, 패널의 실제 가로·세로 크기로
축 범위를 조정한다. 가로 100m와 세로 100m가 같은 길이로 보이게 하여 경로 모양의
왜곡을 줄인다. 움직이지 않은 비행도 축 범위가 0이 되지 않도록 최소 여백을 준다.

고도 그래프의 슬라이더와 내부 확대는 시간 축만 조절한다. 패널 크기가 바뀔 때
사용자가 선택한 고도 그래프의 시간 범위는 유지한다.

## 5. React 안에서 차트를 만들고 정리하기

`FlightChart.tsx`는 재사용할 수 있는 컴포넌트다.

```tsx
<FlightChart kind="route" preview={preview} />
<FlightChart kind="altitude" preview={preview} />
```

내부에서는 다음 순서로 동작한다.

1. `useRef`로 차트를 그릴 HTML 요소를 찾는다.
2. `useEffect`에서 ECharts를 만들고 옵션을 적용한다.
3. `ResizeObserver`로 요소 크기 변화를 감지해 `resize()`를 호출한다.
4. 화면에서 제거되거나 다른 preview로 바뀌면 observer를 해제하고 `dispose()`한다.

브라우저 크기뿐 아니라 Codex의 옆 패널 크기가 바뀌어도 차트가 맞춰진다.
정리를 생략하면 새 파일을 올릴 때 이전 그래프나 이벤트가 남을 수 있다.
React 개발 모드의 StrictMode에서 생성과 정리가 반복돼도 안전한지 검사했다.

## 6. 기존 상태 관리와 연결하기

`App.tsx`에서 상태가 `success`일 때만 차트에 preview를 넘긴다.
파일 변경·해제, 재요청, 오류 상황에서는 차트를 제거하고 빈 상태로 돌아간다.
이렇게 하면 이전 파일의 경로가 새 파일의 결과처럼 남지 않는다.
선택 파일 전송, 취소, 늦은 응답 무시는 앞 단계의 코드를 그대로 사용한다.

## 7. 무엇을 검증했나?

- 동·북 좌표, 비행 순서, 출발·도착 지점이 올바르게 매핑되는지.
- 고도에 절대 고도나 배열 인덱스를 잘못 사용하는 일이 없는지.
- 음수 상대 고도, 정지 경로, 화면 비율이 다른 경우를 처리하는지.
- 파일 변경 시 그래프가 제거되는지, observer와 ECharts 인스턴스가 정리되는지.
- React 화면에서 합성 CSV를 API로 보내 실제 SVG 그래프가 그려지는지.

```bash
npm test
npm run build
```

실행 방법은 `frontend/README.md`와 같다. Python(8000)과 Vite(5173)를 함께 실행하고
CSV 선택 → Generate preview를 누른다. 차트 수치에 마우스를 올려 보고,
고도 슬라이더를 움직이고, 파일을 바꿔 이전 그래프가 사라지는지 확인한다.
개인 CSV와 생성된 결과는 Git에 추가하지 않는다.

다음 단계는 이 프로파일을 실제 시뮬레이터에 넘겨 시뮬레이션을 실행하는 기능이다.
현재 그래프는 CSV에서 만든 비행 프로파일이며 시뮬레이션 예측 결과가 아니다.

참고: [ECharts 시작하기](https://echarts.apache.org/handbook/en/get-started/),
[필요한 모듈만 import하기](https://echarts.apache.org/handbook/en/basics/import/),
[크기 조절과 정리](https://echarts.apache.org/handbook/en/concepts/chart-size/).
