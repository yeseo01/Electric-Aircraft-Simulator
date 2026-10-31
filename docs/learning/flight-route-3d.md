# 평면 경로 옆에 3D 비행 경로 추가하기

큰 화면에서 **평면 경로 → 3D 경로 → CSV 입력** 순서로 패널을 배치했다.
같은 API 응답을 세 가지 관점으로 보여주므로 Python 계산이나 API는 변경하지 않았다.

## 1. 2D와 무엇이 다른가?

| 화면 | 좌표 |
| --- | --- |
| 평면 경로 | x = east_m, y = north_m |
| 3D 경로 | x = east_m, y = north_m, z = relative_altitude_m |
| 고도 프로파일 | x = time_s, y = relative_altitude_m |

3D의 높이는 첫 CSV 샘플 대비 기압고도 변화다. GPS 고도·지상고·ENU Up은 아니다.
원본 waypoint 순서를 유지하며 값을 정렬하거나 보간하지 않는다.

## 2. 왜 Plotly를 추가했나?

기존 ECharts 6 평면/고도 차트는 유지했다. ECharts GL의 명시된 호환 대상은
ECharts 5라서 기존 의존성을 내리는 대신 3D 전용 Plotly 번들을 사용했다.
Plotly의 `scatter3d`는 선과 마커, 세 축, 회전·확대·툴팁을 제공한다.

기본 형태는 다음과 같다.

```ts
Plotly.newPlot(element, [{
  type: 'scatter3d',
  mode: 'lines',
  x: preview.waypoints.map(p => p.east_m),
  y: preview.waypoints.map(p => p.north_m),
  z: preview.waypoints.map(p => p.relative_altitude_m),
}])
```

실제 `route3dFigure.ts`에는 시간 툴팁, 출발·도착 마커, 남색 스타일과 축 이름도 추가했다.

## 3. 축척과 카메라는 별개다

동·북 이동 거리에 비해 고도 변화가 작으면 같은 미터 축척에서는 경로가 납작해 보인다.
상승·하강을 쉽게 확인할 수 있도록 **기본 수직 배율을 10×**로 바꿨다.
Vertical scale에서 1×(동일 축척), 5×, 10×, 20×, 50×를 고를 수 있다.
배율은 화면과 접근성 설명에 항상 표시한다.

중요한 점은 `z` 값 자체를 곱하지 않는다는 것이다. 아래처럼 화면의 축 비율만 바꾼다.

```ts
const displaySpans = [eastSpan, northSpan, altitudeSpan * verticalScale]
const maxSpan = Math.max(...displaySpans)
const aspectratio = {
  x: displaySpans[0] / maxSpan,
  y: displaySpans[1] / maxSpan,
  z: displaySpans[2] / maxSpan,
}
```

좌표·축 눈금·툴팁은 원래 미터 값이다. 예를 들어 실제 상승량이 100m라면 10×에서도
수치는 100m이며, 높이만 강조해 보인다. 수평 축끼리는 같은 축척을 유지한다.
가장 긴 표시 축을 1로 정규화해 카메라 안에 맞추며, 정지 비행에도 최소 범위를 준다.
배율 변경 시 3D 차트를 기본 시점으로 다시 그린다.

카메라는 보는 방향과 확대 정도다. 드래그는 카메라 방향을, 휠은 확대 정도를 바꾼다.
**Reset view**는 `Plotly.relayout()`으로 카메라만 초기화한다. 데이터와 다른 차트는 그대로다.

## 4. 3D 코드도 역할별로 나눴다

| 파일 | 역할 |
| --- | --- |
| `route3dFigure.ts` | API 데이터 → 3D 데이터·축·카메라 설정 |
| `plotly3dRuntime.ts` | 필요할 때 라이브러리를 불러오기 |
| `FlightRoute3D.tsx` | React 요소에 그리기, 상태·크기 변경·정리 |
| `App.tsx`, `App.css` | 중앙 패널과 반응형 배치 |

## 5. 라이브러리는 필요할 때 불러온다

```ts
const { default: Plotly } = await import('plotly.js-gl3d-dist-min')
```

일반 `import`와 달리 이 코드는 실행될 때 파일을 내려받는다. 3D 번들이 크므로
미리보기 성공 후 3D 컴포넌트가 생겼을 때만 읽는다. 로딩 중에는 Preparing 3D view를
표시한다. npm으로 설치한 코드를 로컬에서 실행하며 CSV를 외부 Plotly 서비스에 보내지 않는다.
빌드는 성공하지만 Vite는 이 vendor 파일의 크기에 대해 경고한다. 첫 3D 로딩 이후에는
같은 번들을 다시 import할 때 브라우저의 모듈 캐시를 사용한다.

## 6. 비동기 처리와 정리

파일을 바꾸는 동안 라이브러리 다운로드나 그리기가 끝날 수 있다. 그래서 컴포넌트가
없어졌는지 확인하고, effect마다 별도 그래프 요소를 만든다. 이전 작업의 늦은 정리가
새 파일의 차트를 지우지 않도록 하기 위해서다.

`ResizeObserver`는 패널 크기 변경에 맞춰 그래프를 조절한다. 제거 시 observer를
해제하고 `Plotly.purge()`로 그래프와 WebGL 자원을 정리한다. 실패하면 3D 패널에
안내를 표시하고, 기존 2D 경로와 고도 차트는 계속 사용할 수 있다.

## 직접 확인하기

1. 기존처럼 Python API와 Vite를 함께 실행한다. 새 의존성은 `frontend`에서 `npm ci`로 설치한다.
2. CSV 선택 후 Generate preview를 누른다.
3. 중앙 3D 패널을 드래그하고 휠로 확대한다.
4. Reset view를 눌러 처음 시점으로 복원한다.
5. 파일 변경·해제 시 이전 3D 경로가 사라지는지 확인한다.

테스트는 x/y/z와 시간 매핑, 음수 고도, 1×의 같은 미터 축척, 수직 배율 변경 시 원본
데이터와 축 눈금 유지, 정지 경로, 시점 복원,
크기 조절, 로딩 실패, 늦은 비동기 작업 정리를 확인한다. WebGL 렌더링과 마우스 동작은
합성 비행 데이터로 실제 브라우저에서 확인한다. 개인 CSV는 Git에 포함하지 않는다.

참고: [Plotly 3D 선 그래프](https://plotly.com/javascript/3d-line-plots/),
[3D 축](https://plotly.com/javascript/3d-axes/),
[Plotly 함수](https://plotly.com/javascript/plotlyjs-function-reference/),
[ECharts GL 호환 안내](https://github.com/ecomfe/echarts-gl#installing).
