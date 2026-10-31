# React에서 FastAPI로 CSV 보내기

이번 단계의 목표는 **Swagger에서 실행하던 요청을 우리가 만든 React 화면에서 실행하는 것**이다.
Python의 CSV 검사와 waypoint 생성 코드는 그대로 사용한다. 시뮬레이션 실행과 그래프는 다음 작업이다.

## 1. 바뀐 사용자 흐름

이전에는 파일을 골라도 이름과 용량만 표시했다. 이제 버튼을 눌러 변환 결과까지 확인한다.

```text
CSV 선택 → Generate preview 클릭 → 처리 중 표시 → 성공 요약 또는 오류 표시
```

선택만으로 파일을 전송하지 않는다. 파일 변경·해제는 이전 결과도 지운다.

## 2. 서버와 주고받을 데이터 모양부터 확인하기

풀스택 작업에서는 화면과 서버가 어떤 데이터를 주고받을지 먼저 맞춘다. 이것이 API 계약이다.
기존 계약은 `docs/flight-preview-contract.md`, Python 데이터 구조는 `simulator/preview.py`에 있다.

| 방향 | 내용 |
| --- | --- |
| 요청 | `POST /api/flight-previews`, 파일 필드 `file`, 간격 필드 `downsample_sec` |
| 성공 | JSON: `sample_count`, `waypoint_count`, `duration_s`, 좌표 정보와 `waypoints` |
| 오류 | JSON: `error.code`, `error.issues`의 오류 코드·열·줄 번호 |

`src/api/flightPreviews.ts`에 같은 구조의 TypeScript 타입 `FlightPreview`를 추가했다.
타입은 개발 중 잘못된 필드 사용을 찾는 데 도움을 준다. 실제 HTTP 응답은 별개의 입력이므로
숫자·배열·필수 필드를 실행 중에도 확인한다. 이 검사는 Python의 CSV 내용 검사를 대신하지 않는다.

## 3. FormData와 fetch로 보내기

`FormData`는 파일과 입력값을 함께 담는 객체다. `fetch`는 HTTP 요청을 보낸다.
다음은 핵심만 남긴 기본 코드다.

```ts
const form = new FormData()
form.append('file', file)
form.append('downsample_sec', '1.0')

const response = await fetch('/api/flight-previews', {
  method: 'POST',
  body: form,
})
if (!response.ok) throw new Error('미리보기 생성 실패')
const preview = await response.json()
```

- `file`은 앞 단계에서 React state에 보관한 `File`이다.
- `'file'`이라는 필드명은 FastAPI의 매개변수명과 일치해야 한다.
- `await`는 응답을 기다렸다가 다음 문장을 실행한다. 화면 전체를 멈추게 하지는 않는다.
- `response.json()`은 JSON 응답을 JavaScript 객체로 읽는다.
- `fetch`는 422·500 같은 HTTP 오류에서도 응답 객체를 반환하므로 `response.ok`를 확인한다.
- `Content-Type`은 직접 지정하지 않는다. 브라우저가 파일 구분자(boundary)를 포함해 설정한다.

실제 `createFlightPreview()`는 여기에 네트워크 오류, HTTP 오류, 읽을 수 없는 JSON,
예상과 다른 성공 데이터 검사, 취소 신호를 추가했다. 다른 라이브러리를 설치하지 않고
브라우저에 있는 기능으로 구현했다.

## 4. 5173번과 8000번 서버를 연결하기

브라우저는 Vite의 5173번 포트에서 React 화면을 받는다. Python API는 8000번에서 실행된다.
`vite.config.ts`에 개발용 전달 규칙(proxy)을 추가했다.

```ts
server: {
  proxy: {
    '/api': { target: 'http://127.0.0.1:8000', changeOrigin: true },
  },
},
```

```text
브라우저 → 5173/api/flight-previews → Vite가 전달 → 8000/api/flight-previews
브라우저 ← JSON 응답              ← Vite가 전달 ← Python의 변환 결과
```

React는 상대 경로 `/api/flight-previews`를 사용한다. 이 개발 구성에서는 브라우저가
다른 출처의 API에 직접 접근하지 않으므로 별도의 CORS 허용 설정이 필요 없다.
프록시는 Python 서버를 실행해 주지는 않는다. 두 서버를 각각 실행해야 한다.
Vite 설정을 수정했다면 Vite도 재시작한다.

배포할 때는 호스팅 서버 또는 reverse proxy가 `/api`를 Python으로 전달하도록 구성해야 한다.
개발용 프록시 설정이 빌드된 HTML/JavaScript에 들어가는 것은 아니다.

## 5. React state로 화면 바꾸기

`src/App.tsx`에서 선택 파일과 요청 상태를 관리한다.

| 상태 | 화면 |
| --- | --- |
| `idle` | 파일 선택 후 실행 가능 |
| `loading` | 처리 안내 표시, 생성 버튼 비활성화 |
| `success` | 원본 샘플 수, waypoint 수, 전체 비행 시간 표시 |
| `error` | 오류와 재시도 안내 표시 |

처리 순서는 다음과 같다.

```ts
setPreviewState({ status: 'loading' })
try {
  const preview = await createFlightPreview(file, controller.signal)
  setPreviewState({ status: 'success', preview })
} catch (error) {
  // 실제 코드에서는 취소 여부와 요청 일치 여부도 확인한다.
  setPreviewState({ status: 'error', message: '요청 실패' })
}
```

실제 코드는 `status`에 따라 필요한 데이터도 함께 저장한다. `success`에는 `preview`,
`error`에는 `message`가 있다. 독립된 여러 boolean 대신 하나의 상태를 쓰므로
“성공인데 동시에 처리 중” 같은 모순을 줄인다.

## 6. 파일 변경과 오류 처리

A 파일 요청 중 B 파일을 선택하면 A의 늦은 결과가 B 화면에 표시될 수 있다.
`AbortController`로 이전 브라우저 요청을 취소하고, 응답 시에도 현재 요청인지 확인한다.
`useRef`는 현재 요청의 controller를 보관한다. 화면에 표시할 값은 `useState`,
요청 식별처럼 화면에 직접 표시하지 않는 값은 `useRef`에 둔다.

브라우저 요청 취소는 서버의 계산 중단을 보장하지 않는다. 핵심 목적은 이전 응답이
현재 화면을 덮어쓰지 않도록 하는 것이다. 화면이 사라질 때도 요청을 정리한다.

오류 문구는 서버의 영어 메시지와 비교하지 않고 안정된 `code`로 선택한다.
예를 들어 `missing_column`, `column: LAT`, `row: 1`이면 필요한 열과 CSV 줄 번호를 안내한다.
서버가 꺼져 있으면 API 실행을 확인하고 다시 버튼을 누르도록 안내한다.
오류가 나도 선택 파일은 유지되어 바로 재시도할 수 있다.

## 7. 직접 확인하기

저장소 최상위에서 첫 번째 터미널:

```bash
.venv/bin/python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
```

두 번째 터미널:

```bash
cd frontend
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

1. `http://127.0.0.1:5173`에서 CSV 선택 후 Generate preview 클릭.
2. 성공 시 샘플 수·waypoint 수·초 단위 비행 시간이 표시되는지 확인.
3. LAT 열을 뺀 합성 CSV로 요청해 열·줄 번호가 표시되는지 확인.
4. API 터미널에서 Ctrl+C로 서버를 끄고 요청해 연결 오류 안내 확인.
5. API를 다시 켜고 같은 파일로 재시도.

브라우저 개발자 도구의 Network 탭에서는 `flight-previews` 요청의 URL, POST,
Form Data, 응답 상태 코드, JSON을 확인할 수 있다. 요청은 버튼을 누를 때만 발생한다.
개인 비행 CSV나 개발자 도구의 실제 비행 응답을 Git에 추가하지 않는다.

`npm test`는 기존 선택 동작과 함께 전송 형식, 오류, 재시도, 중복 요청 방지,
파일 변경 후 이전 응답 무시를 검사한다. `npm run build`는 TypeScript 검사와 빌드를 실행한다.

## 변경 파일 읽는 순서

1. `src/api/flightPreviews.ts`: 데이터를 보내고 응답을 해석하는 함수.
2. `vite.config.ts`: `/api`를 Python으로 전달하는 개발 설정.
3. `src/App.tsx`: 버튼 → 요청 → 상태 변경 → 결과 화면.
4. `src/App.css`: 버튼·결과·오류 스타일.
5. `src/api/flightPreviews.test.ts`, `src/App.test.tsx`: 실패·취소까지 확인하는 테스트.

참고: [MDN fetch](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API/Using_Fetch),
[MDN FormData](https://developer.mozilla.org/en-US/docs/Web/API/XMLHttpRequest_API/Using_FormData_Objects),
[Vite proxy](https://vite.dev/config/server-options.html#server-proxy),
[React useRef](https://react.dev/reference/react/useRef).
