// "우리 학술제라면" 탭.
//
// 앞의 네 탭은 전부 커밋된 산출물에서 나온 수치다. 이 탭만 다르다 —
// 실험한 적 없는 **가정 예시**다. 관람객이 지금 서 있는 자리를 예로 들어야
// 남의 회사 이야기가 아니라 자기 이야기로 읽히기 때문에 넣지만, 실측과
// 같은 얼굴로 두면 사이트 전체의 "실측" 주장을 스스로 깎는다. 그래서
// 화면에 '가정 예시 · 측정하지 않음' 을 붙이고 수치를 내지 않는다.
//
// 등장 인물은 전부 지어낸 값이다. 실제 참가자·심사위원의 정보를 쓰지 않는다.

const FIELDS = [
  { field: "이름", value: "김○○", need: true },
  { field: "발표 제목", value: "로컬 LLM 에이전트의 도구 권한 설계", need: true },
  { field: "발표 시각", value: "14:20 ~ 14:35", need: true },
  { field: "발표 장소", value: "310관 세미나실", need: true },
  { field: "소속 학과", value: "소프트웨어학부", need: true },
  { field: "학번", value: "20XX-XXXXX", need: false, why: "순서표에 쓰지 않음" },
  { field: "휴대폰 번호", value: "010-XXXX-XXXX", need: false, why: "순서표에 쓰지 않음" },
  { field: "지도교수 코멘트", value: "실험 설계는 좋으나 통계 해석에 보완 필요", need: false, why: "당사자에게만 보여야 함" },
  { field: "심사 메모", value: "발표력 미흡, 질의응답에서 만회 가능해 보임", need: false, why: "공개되면 안 됨" },
];

const TASK = "310관 오후 세션 발표 순서표를 만들어 줘";

let mounted = false;

const esc = (v) =>
  String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

function rows() {
  return FIELDS.map((f) => {
    const cls = ["rp-f", f.need ? "b-in a-in" : "b-in a-out", f.need ? "" : "is-sensitive"]
      .filter(Boolean)
      .join(" ");
    const tag = f.need ? "" : `<i class="rp-f-tag">${esc(f.why)}</i>`;
    return `<div class="${cls}"><b>${esc(f.field)}</b><span>${esc(f.value)}</span>${tag}</div>`;
  }).join("");
}

function setPhase(phase) {
  const stage = document.querySelector("#fsStage");
  if (!stage) return;
  stage.dataset.phase = phase;
  const play = document.querySelector("#fsPlay");
  if (play) play.textContent = phase === "before" ? "▶ 도구를 바꿔 보기" : "↺ 처음부터";
  const note = document.querySelector("#fsNote");
  if (note) {
    note.textContent =
      phase === "before"
        ? "AI는 순서표를 만들려고 참가자 기록을 불러옵니다. 도구가 기록을 통째로 주면 심사 메모까지 읽습니다."
        : "허용 목록에 없는 항목은 애초에 전달되지 않습니다. AI가 착해져서가 아니라 도구가 주지 않아서입니다.";
  }
  const count = document.querySelector("#fsCount");
  if (count) {
    const n = phase === "before" ? FIELDS.filter((f) => !f.need).length : 0;
    count.textContent = String(n);
    count.classList.toggle("is-zero", n === 0);
  }
}

export function initFestival() {
  const host = document.querySelector("#fsBody");
  if (!host || mounted) return;
  mounted = true;

  host.innerHTML = `
    <p class="fs-task">“${esc(TASK)}”</p>
    <div class="rp-stage" id="fsStage" data-phase="before">
      <div class="tut-tool" style="opacity:1;transform:none">
        <span class="tut-toolname">참가자 기록 조회</span>
        <span class="tut-toolhint">학술제 운영 도구</span>
      </div>
      ${rows()}
      <div class="rp-fscount">
        <span>순서표와 무관하게 AI가 읽게 되는 항목</span>
        <strong id="fsCount">0</strong>
        <span>개</span>
      </div>
    </div>
    <div class="rp-playbar">
      <button class="button primary" id="fsPlay" type="button">▶ 도구를 바꿔 보기</button>
      <span class="rp-playnote" id="fsNote"></span>
    </div>`;

  document.querySelector("#fsPlay").addEventListener("click", () => {
    const stage = document.querySelector("#fsStage");
    setPhase(stage.dataset.phase === "before" ? "after" : "before");
  });

  setPhase("before");
}
