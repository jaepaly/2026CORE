// 탭 셸.
//
// 전체를 한 장으로 늘어놓으면 폰에서 12.8화면이고, 연구 2 한 파트만 5.3화면이다.
// 한 번에 들어오는 정보량이 너무 많아 스크롤 자체가 부담이 된다. 파트별로
// 나눠 한 번에 한 파트만 보여준다.
//
// 주소는 기존 앵커를 그대로 쓴다(#replay, #policy, #evidence). QR·내비·튜토리얼
// 인계가 전부 이 앵커에 의존하므로, 탭을 넣으면서 주소 체계를 바꾸면 기존
// 링크가 전부 죽는다. 탭 키 = 섹션 id 로 맞춰 두면 링크가 그대로 산다.

const TABS = ["intro", "replay", "policy", "evidence"];
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

export function initTabs() {
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

  showTab(location.hash, { updateHash: false });
}
