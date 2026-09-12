// 탭 셸.
//
// 전체를 한 장으로 늘어놓으면 폰에서 12.8화면이고, 연구 2 한 파트만 5.3화면이다.
// 한 번에 들어오는 정보량이 너무 많아 스크롤 자체가 부담이 된다. 파트별로
// 나눠 한 번에 한 파트만 보여준다.
//
// 주소는 기존 앵커를 그대로 쓴다(#replay, #policy, #evidence). QR·내비·튜토리얼
// 인계가 전부 이 앵커에 의존하므로, 탭을 넣으면서 주소 체계를 바꾸면 기존
// 링크가 전부 죽는다. 탭 키 = 섹션 id 로 맞춰 두면 링크가 그대로 산다.

const TABS = ["intro", "replay", "policy", "evidence", "festival"];
const DEFAULT_TAB = "intro";

let current = null;
const listeners = [];

/** 탭이 바뀔 때마다 부른다. (key, {first}) — first 는 이 세션에서 처음 열렸는지. */
export function onTabChange(fn) {
  listeners.push(fn);
}

const openedOnce = new Set();

function panel(key) {
  return document.getElementById(`panel-${key}`);
}

function normalize(raw) {
  const key = (raw || "").replace(/^#/, "");
  return TABS.includes(key) ? key : DEFAULT_TAB;
}

export function showTab(key, { updateHash = true } = {}) {
  const next = normalize(key);
  if (next === current) return;

  for (const t of TABS) {
    const p = panel(t);
    if (p) p.hidden = t !== next;
  }
  for (const button of document.querySelectorAll(".tab")) {
    const on = button.dataset.tab === next;
    button.classList.toggle("is-on", on);
    button.setAttribute("aria-selected", on ? "true" : "false");
  }

  const previous = current;
  current = next;

  if (updateHash && location.hash.replace(/^#/, "") !== next) {
    // replaceState 로 두면 뒤로가기가 사이트를 떠나 버린다. 탭 이동은
    // 사용자에게 '페이지 이동'처럼 느껴지므로 히스토리에 쌓는다.
    history.pushState({ tab: next }, "", `#${next}`);
  }

  // 파트를 바꾸면 읽던 위치가 아니라 새 파트의 처음부터 보여야 한다.
  if (previous !== null) {
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  const first = !openedOnce.has(next);
  openedOnce.add(next);
  for (const fn of listeners) {
    try {
      fn(next, { first });
    } catch (err) {
      console.warn("tab listener:", err);
    }
  }
}

export function currentTab() {
  return current;
}

/** 이전 버전이 "안내 봤음" 을 localStorage 에 영구 저장했다. 지금은 아무도
 *  읽지 않지만, 그때 방문한 기기에는 키가 그대로 남는다. 우리가 심은 것이므로
 *  우리가 지운다 — 나중에 같은 접두어를 다시 쓸 때 옛 값에 물리는 것도 막는다. */
function clearLegacyState() {
  try {
    for (const key of Object.keys(localStorage)) {
      if (key.startsWith("core2026.tutorial.seen")) localStorage.removeItem(key);
    }
  } catch (err) {
    // 저장소 접근이 막힌 환경 — 지울 것도 없다.
  }
}

export function initTabs() {
  clearLegacyState();

  document.addEventListener("click", (event) => {
    const tab = event.target.closest("[data-tab]");
    if (tab) {
      showTab(tab.dataset.tab);
      return;
    }
    const advance = event.target.closest("[data-goto]");
    if (advance) {
      showTab(advance.dataset.goto);
      return;
    }
    // 페이지 안 앵커 링크(#replay 등)는 탭 전환으로 처리한다.
    const link = event.target.closest('a[href^="#"]');
    if (link) {
      const key = link.getAttribute("href").slice(1);
      if (TABS.includes(key)) {
        event.preventDefault();
        showTab(key);
      }
    }
  });

  window.addEventListener("popstate", () => {
    showTab(location.hash, { updateHash: false });
  });

  showTab(startingTab(), { updateHash: false });
}

/** 어느 탭으로 열 것인가.
 *
 *  새로고침과 딥링크는 페이지 입장에서 똑같이 "해시를 단 로드" 라 구분이
 *  필요하다. navigation type 이 그 구분을 준다.
 *
 *  - reload   : 처음부터 다시 본다는 뜻이다. 1번 탭으로 되돌리고 해시도 지운다.
 *               전시장에서 새로 여는 것은 대개 새 사람이 새로 시작한다는 뜻이다.
 *  - navigate : 주소를 눌러 들어온 것이다. 목적지가 있으므로 해시를 존중한다.
 *               QR 이나 공유 링크로 #policy 를 찍어 온 사람을 1번으로 되돌리면 안 된다.
 */
function startingTab() {
  let type = "navigate";
  try {
    const nav = performance.getEntriesByType("navigation")[0];
    if (nav && nav.type) type = nav.type;
  } catch (err) {
    // 구형 브라우저 — 해시를 존중하는 쪽으로 둔다(딥링크가 더 중요하다).
  }
  if (type !== "reload") return location.hash;

  if (location.hash) {
    history.replaceState({ tab: DEFAULT_TAB }, "", location.pathname + location.search);
  }
  return DEFAULT_TAB;
}
