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

const STORAGE_KEY = "core2026.tutorial.seen.v1";

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
  const step = STEPS[index];
  const value = (x) => (typeof x === "function" ? x(data) : x);

  root.querySelector(".tut-stage").dataset.step = step.key;
  root.querySelector(".tut-title").textContent = step.title;
  root.querySelector(".tut-lead").textContent = value(step.lead);
  root.querySelector(".tut-note").textContent = value(step.note);

  const shown = index >= 2;
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
    index === STEPS.length - 1 ? "실제 로그 보러 가기" : "다음";
  root.querySelector(".tut-prev").hidden = index === 0;
  root.querySelector(".tut-final").hidden = index !== STEPS.length - 1;
}

function close(goToReplay) {
  if (!root) return;
  try {
    localStorage.setItem(STORAGE_KEY, "1");
  } catch (err) {
    // 사생활 보호 모드 등에서 저장이 막힐 수 있다. 안내는 그대로 동작해야 한다.
  }
  root.remove();
  root = null;
  document.body.style.overflow = "";
  document.removeEventListener("keydown", onKey);
  if (lastFocused && lastFocused.focus) lastFocused.focus();
  if (goToReplay) {
    const target = document.getElementById("replay");
    if (target) {
      target.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth" });
    }
  }
}

function step(delta) {
  const next = index + delta;
  if (next < 0) return;
  if (next >= STEPS.length) {
    close(true);
    return;
  }
  index = next;
  render();
}

function onKey(event) {
  if (event.key === "Escape") {
    close(false);
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
        <div class="tut-dots">${STEPS.map(() => '<span class="tut-dot"></span>').join("")}</div>
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

  root.querySelector(".tut-skip").addEventListener("click", () => close(false));
  root.querySelector(".tut-next").addEventListener("click", () => step(1));
  root.querySelector(".tut-prev").addEventListener("click", () => step(-1));
  root.addEventListener("click", (event) => {
    if (event.target === root) close(false);
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

export async function openTutorial() {
  await load();
  if (root) close(false);
  index = 0;
  lastFocused = document.activeElement;
  build();
  render();
}

export async function initTutorial() {
  const button = document.querySelector("#tutorialReplayBtn");
  if (button) {
    button.addEventListener("click", () => {
      openTutorial().catch((err) => console.warn("tutorial:", err));
    });
  }

  let seen = false;
  try {
    seen = localStorage.getItem(STORAGE_KEY) === "1";
  } catch (err) {
    seen = false;
  }
  // 앵커를 달고 들어온 사람은 이미 목적지가 있다. 가로막지 않는다.
  if (seen || location.hash) return;
  await openTutorial();
}
