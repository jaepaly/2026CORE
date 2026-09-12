// 첫 진입 튜토리얼 오버레이.
//
// 이 연구의 주장은 한 문장으로 줄어든다 — "같은 요청, 같은 모델, 허용 필드
// 목록만 다름 -> 민감정보가 사라진다". 그런데 기존 페이지는 그 문장을
// 이해시키는 섹션이 9화면 아래에 있고, A/B/C/D 라는 코드를 13화면 뒤에
// 정의한다. 이 오버레이는 같은 문장을 다섯 걸음으로 먼저 보여준다.
//
// 화면에 나오는 값은 전부 demo/tutorial_data.json 에서 오고, 그 파일은
// 커밋된 runs.jsonl 에서 생성된다(demo/build_tutorial_data.py). 튜토리얼이
// 지어낸 예시이면 "실측"이라는 이 연구의 강점을 여기서 스스로 버리게 된다.

/** 다섯 비트를 탭에 나눠 붙인다.
 *
 *  탭마다 따로 온보딩을 만들면 5단계 x 4탭 = 20단계가 되어 안내가 아니라
 *  장애물이 된다. 그래서 새로 만들지 않고 원래 다섯 걸음을 소속 탭으로
 *  쪼갠다 — 문제 탭이 1~3(업무 -> 호출 -> 전부 넘어옴), 실측 탭이
 *  4~5(사람이 쓴 허용 목록 -> 0건)를 맡는다. 뒤 두 탭은 각자 본문 설명이
 *  이미 있으므로 오버레이를 띄우지 않는다. */
const TAB_OF_STEP = { task: "intro", call: "intro", exposed: "intro", policy: "replay", protected: "replay" };

const reduceMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const esc = (v) =>
  String(v ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

// 단계 정의. 각 단계는 같은 DOM 위에서 data-step 만 바꾼다 — 단계마다 다시
// 그리면 "무엇이 사라졌는지"가 보이지 않는다. 사라지는 움직임 자체가 설명이다.
const STEPS = [
  {
    key: "task",
    title: "업무 하나를 AI에게 맡깁니다",
    lead: (d) => `"${d.task}"`,
    note: "평범한 사내 업무입니다. 여기까지는 특별할 것이 없습니다.",
  },
  {
    key: "call",
    title: "AI가 주소록을 조회합니다",
    lead: () => "일을 하려면 사람 정보가 필요하니 AI가 도구를 부릅니다.",
    note: (d) => `호출한 도구: ${d.tool}`,
  },
  {
    key: "exposed",
    title: "그런데 이만큼이 돌아옵니다",
    lead: (d) =>
      `일정을 잡는 데 필요한 건 이름뿐인데, ${d.recordName} 씨의 항목이 전부 넘어갔습니다.`,
    note: "빨간 항목은 이 업무와 상관없는 민감정보입니다.",
  },
  {
    key: "policy",
    title: "바꾸는 건 이것 하나입니다",
    lead:
      "AI를 바꾸지 않습니다. 프롬프트로 부탁하지도 않습니다. 도구가 무엇을 돌려줄지 적은 목록 하나를 사람이 정합니다.",
    note: "이 목록은 사람이 쓰고 사람이 검토합니다.",
  },
  {
    key: "protected",
    title: "같은 요청, 같은 AI — 결과만 달라집니다",
    lead: "요청은 글자 하나 바뀌지 않았습니다. 도구가 돌려주는 것만 달라졌습니다.",
    note: (d) =>
      `요청 인자 해시가 양쪽 모두 ${d.requestArgsSha256.slice(0, 12)}… 로 같습니다.`,
  },
];

let data = null;
let index = 0;
let root = null;
let lastFocused = null;

function fieldRows() {
  return data.fields
    .map((f) => {
      const cls = [
        "tut-field",
        f.sensitive ? "is-sensitive" : "",
        f.keptUnderPolicy ? "is-kept" : "is-cut",
      ]
        .filter(Boolean)
        .join(" ");
      const tag = f.sensitive
        ? `<i class="tut-tag">${esc(f.sensitiveLabel || "민감")}</i>`
        : "";
      return `<li class="${cls}"><b>${esc(f.field)}</b><span>${esc(f.value)}</span>${tag}<em class="tut-cutmark">차단됨</em></li>`;
    })
    .join("");
}

function allowList() {
  return data.allowedFieldPaths.map((p) => `<code>${esc(p)}</code>`).join("");
}

function render() {
  const step = steps[index];
  const value = (x) => (typeof x === "function" ? x(data) : x);

  root.querySelector(".tut-stage").dataset.step = step.key;
  root.querySelector(".tut-title").textContent = step.title;
  root.querySelector(".tut-lead").textContent = value(step.lead);
  root.querySelector(".tut-note").textContent = value(step.note);

  const shown = ["exposed", "policy", "protected"].includes(step.key);
  root.querySelector(".tut-counter").hidden = !shown;
  if (shown) {
    const n =
      step.key === "protected"
        ? data.counts.sensitiveWith
        : data.counts.sensitiveWithout;
    const numEl = root.querySelector(".tut-counter-num");
    numEl.textContent = String(n);
    numEl.classList.toggle("is-zero", n === 0);
  }

  root.querySelectorAll(".tut-dot").forEach((d, i) => {
    d.classList.toggle("is-on", i === index);
    d.classList.toggle("is-done", i < index);
  });

  root.querySelector(".tut-next").textContent =
    index === steps.length - 1 ? finalLabel() : "다음";
  root.querySelector(".tut-prev").hidden = index === 0;
  root.querySelector(".tut-final").hidden = index !== steps.length - 1;
}

/** 안내가 끝나면 탭을 옮기지 않는다.
 *
 *  자동으로 넘기면 안내만 보고 그 탭을 정작 못 둘러본다 — 설명을 들은 직후가
 *  직접 만져 보기 가장 좋은 때인데 그 기회를 뺏는 셈이다. 그래서 그 자리에서
 *  닫고, 다음 탭으로 가는 것은 화면 아래 "다음 · ..." 버튼과 탭바에 맡긴다. */
function finalLabel() {
  return "이 화면 둘러보기";
}

function close() {
  if (!root) return;
  root.remove();
  root = null;
  document.body.style.overflow = "";
  document.removeEventListener("keydown", onKey);
  if (lastFocused && lastFocused.focus) lastFocused.focus();
}

function step(delta) {
  const next = index + delta;
  if (next < 0) return;
  if (next >= steps.length) {
    close();
    return;
  }
  index = next;
  render();
}

function onKey(event) {
  if (event.key === "Escape") {
    close();
    return;
  }
  if (event.key === "ArrowRight") {
    step(1);
    return;
  }
  if (event.key === "ArrowLeft") {
    step(-1);
    return;
  }
  if (event.key !== "Tab" || !root) return;
  // 아주 단순한 포커스 트랩 — 오버레이 밖으로 탭이 새지 않게만 한다.
  const focusable = [...root.querySelectorAll("button")].filter((b) => !b.hidden);
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}

function build() {
  root = document.createElement("div");
  root.className = "tut-overlay";
  if (reduceMotion()) root.classList.add("no-motion");
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-modal", "true");
  root.setAttribute("aria-label", "시연 안내");
  root.innerHTML = `
    <div class="tut-card">
      <div class="tut-top">
        <div class="tut-dots">${steps.map(() => '<span class="tut-dot"></span>').join("")}</div>
        <button class="tut-skip" type="button">건너뛰기</button>
      </div>

      <h2 class="tut-title"></h2>
      <p class="tut-lead"></p>

      <div class="tut-stage" data-step="task">
        <div class="tut-tool">
          <span class="tut-toolname">${esc(data.tool)}</span>
          <span class="tut-toolhint">주소록 조회</span>
        </div>

        <div class="tut-policy">
          <span class="tut-policy-label">사람이 정한 허용 목록</span>
          <div class="tut-policy-list">${allowList()}</div>
        </div>

        <ul class="tut-fields">${fieldRows()}</ul>

        <div class="tut-counter" hidden>
          <span>AI에게 넘어간 민감정보</span>
          <strong class="tut-counter-num">0</strong>
          <span>건</span>
        </div>
      </div>

      <p class="tut-note"></p>

      <p class="tut-final" hidden>
        방금 본 건 예시가 아니라 커밋된 실험 로그입니다 —
        <code>${esc(data.provenance.runIdWithout)}</code>
        <code>${esc(data.provenance.runIdWith)}</code>
      </p>

      <div class="tut-actions">
        <button class="tut-prev" type="button" hidden>이전</button>
        <button class="tut-next button primary" type="button">다음</button>
      </div>
    </div>`;

  root.querySelector(".tut-skip").addEventListener("click", () => close());
  root.querySelector(".tut-next").addEventListener("click", () => step(1));
  root.querySelector(".tut-prev").addEventListener("click", () => step(-1));
  root.addEventListener("click", (event) => {
    if (event.target === root) close();
  });

  document.body.appendChild(root);
  document.body.style.overflow = "hidden";
  document.addEventListener("keydown", onKey);
  root.querySelector(".tut-next").focus();
}

async function load() {
  if (data) return data;
  const response = await fetch("./tutorial_data.json", { cache: "no-store" });
  if (!response.ok) throw new Error(`tutorial_data.json ${response.status}`);
  data = await response.json();
  return data;
}

let steps = STEPS;

export async function openTutorial(tab) {
  await load();
  if (root) close();
  steps = tab ? STEPS.filter((s) => TAB_OF_STEP[s.key] === tab) : STEPS;
  if (!steps.length) return;
  index = 0;
  lastFocused = document.activeElement;
  build();
  render();
}

/** 탭 셸이 부른다. 해당 탭에 배정된 비트를, 그 탭을 처음 열 때만 띄운다.
 *  두 번째부터는 탭 상단의 "안내 다시 보기" 로만 열린다 — 탭을 옮길 때마다
 *  모달이 뜨면 안내가 아니라 장애물이 된다. */
export function initTutorial() {
  for (const button of document.querySelectorAll("[data-tutorial]")) {
    button.addEventListener("click", () => {
      openTutorial(button.dataset.tutorial).catch((err) => console.warn("tutorial:", err));
    });
  }
}

/** 탭이 열릴 때마다 탭 셸이 부른다.
 *
 *  "봤음" 은 메모리에만 둔다(탭 셸의 first 플래그). localStorage 에 남기면
 *  한 번 본 기기에서는 새로고침해도 안내가 영영 다시 뜨지 않는다. 이 사이트는
 *  전시장에서 QR 로 건네는 화면이고, 새로 여는 것은 대개 새 사람이 새로
 *  시작한다는 뜻이다. 한 번의 방문 안에서 탭을 오갈 때만 다시 뜨지 않으면 된다. */
export async function tutorialForTab(tab, { first }) {
  if (!first) return;
  await openTutorial(tab);
}
