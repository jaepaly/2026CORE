// 필드 경로를 사람 말로 옮긴다.
//
// 화면에 `search_emails.subject` 라고 적으면 이 분야 사람만 읽을 수 있다.
// 이 데모는 전공자가 아닌 심사위원과 관람객이 QR 로 들어와 혼자 보는 화면이므로,
// 기본은 "메일 제목" 처럼 읽히는 이름이어야 한다.
//
// 다만 경로 표기 자체가 증거이기도 하다 — 정책이 어떤 문법으로 쓰였는지가
// 연구 2 의 관찰 대상이다. 그래서 경로를 지우지 않고 표기만 전환한다
// (패널의 "실제 경로 보기" 스위치).

const TOOL_LABEL = {
  search_contacts: "주소록 검색",
  get_contact: "주소록 상세",
  search_emails: "메일 검색",
  get_email: "메일 상세",
  search_calendar: "일정 조회",
  create_event: "일정 생성",
};

const TOOL_DOMAIN = {
  search_contacts: "주소록",
  get_contact: "주소록",
  search_emails: "메일",
  get_email: "메일",
  search_calendar: "일정",
  create_event: "일정",
};

const FIELD_LABEL = {
  주소록: {
    id: "식별자",
    name: "이름",
    email: "이메일 주소",
    phone: "전화번호",
    department: "부서",
    role: "직급",
    notes: "개인 메모",
  },
  메일: {
    id: "식별자",
    subject: "제목",
    from: "보낸 사람",
    to: "받는 사람",
    date: "날짜",
    category: "분류",
    priority: "중요도",
    body: "본문",
  },
  일정: {
    id: "식별자",
    date: "날짜",
    day: "요일",
    slots: "빈 시간",
    events: "일정 목록",
    "events[].title": "일정 제목",
    "events[].time": "시각",
    "events[].location": "장소",
    "events[].participants": "참석자",
    "events[].type": "유형",
    status: "상태",
    participants: "참석자",
    title: "제목",
    time: "시각",
  },
};

export function toolLabel(tool) {
  return TOOL_LABEL[tool] || tool;
}

/** "search_emails.subject" -> "메일 제목". 모르는 경로는 원문 그대로 둔다 —
 *  지어낸 이름을 붙이면 화면이 산출물과 어긋난다. */
export function fieldLabel(path) {
  if (!path || !path.includes(".")) return path;
  const [tool, field] = [path.slice(0, path.indexOf(".")), path.slice(path.indexOf(".") + 1)];
  const domain = TOOL_DOMAIN[tool];
  if (!domain) return path;
  const name = (FIELD_LABEL[domain] || {})[field];
  return name ? `${domain} ${name}` : path;
}

/** 도구 없이 필드 이름만 있을 때(레코드 행). 레코드 id 로 영역을 추정한다. */
export function bareFieldLabel(field, recordId = "") {
  let domain = "주소록";
  if (recordId.startsWith("e")) domain = "메일";
  else if (recordId.startsWith("cal") || recordId.startsWith("sandbox")) domain = "일정";
  const name = (FIELD_LABEL[domain] || {})[field];
  return name || field;
}
