# 합성 데이터의 근거 — 왜 이 필드들인가

> "회사 데이터를 진짜 이렇게까지 구현할 수밖에 없었나? 어떤 공개 데이터셋이나 기존 연구로
> 뒷받침할 수 있나?" 에 대한 답.

합성 데이터는 임의로 만들면 편향이 어디서 들어왔는지 말할 수 없다. 이 문서는 두 가지를 고정한다.
**스키마를 어디서 가져왔는가**(실제 SaaS API), **민감도 판단의 근거가 무엇인가**(정보 흐름 규범).

## 1. 왜 실제 사내 데이터를 쓰지 않았는가

실제 사내 워크스페이스 데이터는 그 자체가 개인정보다. 연구에 쓰려면 그 데이터를 모델에게
전달해야 하는데, 이 연구가 측정하려는 대상이 바로 **모델에게 전달되는 개인정보의 양**이다.
측정 대상을 만들어내지 않고는 측정할 수 없다.

합성 워크스페이스는 이 영역의 표준 관행이다.

| 선행 연구 | 접근 |
|---|---|
| [AgentDojo](https://arxiv.org/abs/2406.13352) (NeurIPS 2024) | 합성 워크스페이스(이메일·캘린더·뱅킹) 위에서 도구 사용 에이전트의 보안을 평가. 97개 과제 / 629 보안 테스트 |
| [PrivacyLens](https://arxiv.org/abs/2409.00138) | 프라이버시 규범 seed → vignette → 에이전트 궤적으로 확장해 **행동 단계의 유출**을 측정 |
| [ConfAIde](https://arxiv.org/abs/2310.17884) (ICLR 2024) | contextual integrity 기반으로 "누가 무엇을 알아야 하는가"를 계층적으로 평가 |

우리 연구가 이들과 다른 점은 **측정 지점**이다. 위 연구들은 모델의 *출력*에서 유출을 본다.
우리는 **도구 경계에서 모델에게 전달되는 양**을 별도 계층으로 분리해 측정한다
(capacity / delivery / behaviour 3계층). 모델이 무엇을 말했는지가 아니라 무엇을 *받았는지*가
인터페이스 설계로 통제 가능한 지점이기 때문이다.

## 2. 스키마는 실제 SaaS API에서 가져왔다

필드 이름을 임의로 짓지 않았다. 세 개의 실제 업무 API 스키마에 대응시켰다.
아래 표의 API 필드명은 2026-08 공식 문서에서 확인한 것이다.

### 2.1 연락처 → [Google People API](https://developers.google.com/people/api/rest/v1/people) `Person`

| 우리 필드 | People API | 대응 |
|---|---|---|
| `id` | `resourceName` | 식별자 |
| `name` | `names[].displayName` | 직접 |
| `email` | `emailAddresses[].value` | 직접 |
| `phone` | `phoneNumbers[].value` | 직접 |
| `department` | `organizations[].department` | 직접 |
| `role` | `organizations[].title` | 직접 |
| `notes` | `biographies[].value` | 직접 |

`notes`가 자유 서술 필드라는 점이 중요하다. People API의 `biographies`도 마찬가지로 구조가 없는
자유 텍스트이며, 실무에서 이런 필드에 업무 외 정보가 쌓인다. 우리가 `notes`에 민감 정보를
배치한 것은 임의 설정이 아니라 **자유 서술 필드의 실제 사용 양상**을 반영한 것이다.

### 2.2 이메일 → [Gmail API](https://developers.google.com/gmail/api/reference/rest/v1/users.messages) `Message`

| 우리 필드 | Gmail API | 대응 |
|---|---|---|
| `id` | `id` | 직접 |
| `from` | `payload.headers[name="From"].value` | 직접 (RFC 2822 헤더) |
| `to` | `payload.headers[name="To"].value` | 직접 |
| `subject` | `payload.headers[name="Subject"].value` | 직접 |
| `date` | `payload.headers[name="Date"].value` | 직접 |
| `body` | `payload.body.data` | 직접 |
| `category` | `labelIds` | 근사 — 라벨을 단일 분류로 축약 |
| `priority` | — | **우리 확장**. Gmail의 일급 필드가 아니다 |

`subject`/`from`/`date`는 헤더로 얻을 수 있지만 `body`는 별도 페이로드라는 구조가 그대로 반영돼
있다. 이것이 이 연구에서 의미가 있는 이유는, **메일 목록을 훑는 업무 대부분이 헤더만으로
충분한데 도구는 본문까지 함께 반환**한다는 것이 곧 과잉 노출의 발생 지점이기 때문이다.

### 2.3 캘린더 → [Google Calendar API](https://developers.google.com/calendar/api/v3/reference/events) `Event`

| 우리 필드 | Calendar API | 대응 |
|---|---|---|
| `events[].title` | `summary` | 직접 |
| `events[].time` | `start.dateTime` / `end.dateTime` | 근사 — 시작·종료를 한 문자열로 축약 |
| `events[].location` | `location` | 직접 |
| `events[].participants` | `attendees[].displayName` | 직접 |
| `events[].type` | — | **우리 확장** (회의/개인 등 분류) |
| `date`, `day`, `slots` | — | **우리 확장**. 날짜별 묶음과 빈 시간대는 조회 편의를 위한 구조 |

`attendees`가 `Event` 안에 중첩된 배열이라는 점이 이 연구의 설계에 직접 영향을 줬다.
일정 정보를 허용하면서 참석자 명단만 제외하려면 **중첩 경로 단위의 projection**이 필요하다.
`delivery_audit_v3`의 `events[].participants` 표기는 이 실제 구조에서 나온 것이다.

### 2.4 정리

고유 필드 25개(도구 중복을 펼치면 경로 40개) 기준으로 **직접 대응 16 / 근사 2 / 우리 확장 7**.

| 도메인 | 고유 필드 | 직접 | 근사 | 확장 |
|---|---|---|---|---|
| 연락처 | 7 | **7** | 0 | 0 |
| 이메일 | 8 | 6 | 1 (`category`) | 1 (`priority`) |
| 캘린더 | 10 | 3 | 1 (`events[].time`) | 6 (`date`, `day`, `events`, `events[].type`, `id`, `slots`) |
| 합계 | 25 | 16 | 2 | 7 |

확장이 캘린더에 몰려 있는데, 이는 날짜별 묶음과 빈 시간대처럼 **조회 편의를 위한 구조**이지
정보 항목이 아니다. 중요한 것은 그 다음이다 — **민감 라벨이 걸린 네 필드
(`notes`·`phone`·`body`·`events[].participants`)는 전부 실제 API의 직접 대응 필드다.**
민감도 판단이 우리가 지어낸 필드 위에서 이뤄지지 않았다는 뜻이다.

(이 표의 수치는 `data/*.json`에서 기계적으로 산출한 것이며, 스키마가 바뀌면 다시 세야 한다.)

## 3. 민감도 판단의 근거

"어떤 필드가 민감한가"는 필드 자체의 속성이 아니다. `phone`은 인사팀 연락처 갱신 업무에서는
필수이고 회의실 예약 업무에서는 불필요하다. 이 연구가 민감도를 **시나리오별로** 라벨링한 것은
contextual integrity — *정보 흐름은 그 맥락의 규범을 따를 때 프라이버시가 보호된다*는
관점([ConfAIde](https://arxiv.org/abs/2310.17884), [PrivacyLens](https://arxiv.org/abs/2409.00138)가
공통으로 채택) 을 따른 것이다.

구현상 두 가지로 나타난다.

- **`forbidden_sensitive_field_paths`는 시나리오마다 다르다.** 43개 시나리오에서
  `get_contact.notes` 37회, `get_email.body` 36회, `get_contact.phone` 34회,
  `search_calendar.events[].participants` 2회 금지됐다. 전역 규칙이 아니다.
- **민감도는 레코드 도메인 기준으로 해석한다.** `get_contact.notes`를 금지한 판단은
  *연락처의 notes*에 대한 것이므로 `search_contacts.notes`에도 동일하게 적용된다
  (`delivery_audit_v3.record_domain`).

## 4. 데이터 규모와 그 한계

합성 워크스페이스 55항목 — 연락처 15 · 이메일 33 · 캘린더 7일.

이 규모는 **43개 시나리오가 서로 다른 레코드를 요구하도록** 정하고, 각 시나리오가 최소 1개의
업무 외 민감 필드를 포함하도록 구성한 결과다. 다만 규모의 한계는 명확하다.

- 연락처 15명은 실제 사내 디렉터리보다 두 자릿수 작다. 검색 도구가 반환하는 레코드 수가
  현실보다 적으므로, **실제 환경의 과잉 노출은 여기서 측정한 것보다 클 가능성이 높다.**
  이 방향의 편향은 우리 결론을 과대평가하지 않는다.
- 단일 도메인(사내 업무공간)이므로 도메인이 바뀌면 민감도 판단 자체가 달라진다.
- 한국어 단일 언어다.

## 5. 재현

데이터는 `data/contacts.json`·`emails.json`·`calendar.json`에 커밋돼 있고,
라벨은 `data/scenario_review_v3.csv`에 검토 이력(1차 → 2차 → 조정)과 함께 있다.
필드 어휘는 하드코딩이 아니라 이 데이터에서 기계적으로 추출된다
(`policy_authoring_v3.build_field_vocabulary`).
