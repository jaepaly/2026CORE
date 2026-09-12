// 재생 버튼을 눌렀을 때 "무엇이 어떻게 바뀌는지" 가 화면 안에서 일어나게 한다.
//
// 버튼은 무대 아래에 있다. 폰에서 버튼이 보이는 위치까지 스크롤해 누르면
// 정작 바뀌는 부분은 화면 위쪽으로 밀려나 있을 수 있다. 게다가 항목이
// 접히면서 무대가 줄어들어 아래 내용이 위로 딸려 올라온다 — 누른 사람 입장에서는
// 무언가 움직이긴 했는데 무엇이 사라졌는지 못 보는 상태가 된다.
//
// 그래서 상태를 바꾸기 전에 무대를 먼저 화면에 앉히고, 스크롤이 끝난 뒤에
// 변화를 시작한다. 이미 다 보이는 상태라면 아무것도 하지 않는다 — 사용자가
// 맞춰 둔 위치를 이유 없이 뺏지 않는다.

const reduceMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** 상단에 붙어 있는 것들(헤더 + 탭바)이 가리는 높이. */
function stickyOffset() {
  let offset = 0;
  for (const selector of [".topbar", ".tabbar"]) {
    const el = document.querySelector(selector);
    if (el && getComputedStyle(el).position === "sticky") {
      offset += el.getBoundingClientRect().height;
    }
  }
  return offset;
}

/** 무대를 화면 안에 앉힌 뒤 `then()` 을 부른다. */
export function revealStage(stage, then) {
  const run = typeof then === "function" ? then : () => {};
  if (!stage) {
    run();
    return;
  }

  const sticky = stickyOffset();
  const viewportH = document.documentElement.clientHeight;
  const rect = stage.getBoundingClientRect();

  const fullyVisible = rect.top >= sticky - 1 && rect.bottom <= viewportH + 1;
  if (fullyVisible) {
    run();
    return;
  }

  // 무대가 화면보다 길면 아래를 맞출 수 없다. 그때는 위를 맞춘다 —
  // 첫 항목부터 사라지기 시작하므로 위쪽이 더 중요하다.
  const margin = 12;
  let target = rect.top + window.scrollY - sticky - margin;
  if (rect.height <= viewportH - sticky) {
    // 다 들어가면 가운데 가까이 두어 위아래 여백을 나눠 준다.
    const slack = viewportH - sticky - rect.height;
    target -= Math.min(slack / 2, 40);
  }

  const instant = reduceMotion();
  window.scrollTo({ top: Math.max(0, target), behavior: instant ? "auto" : "smooth" });

  // 스크롤이 끝나고 나서 바뀌어야 변화를 처음부터 볼 수 있다.
  // scrollend 는 아직 모든 브라우저에 없으므로 타이머를 함께 건다.
  if (instant) {
    run();
    return;
  }
  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    window.removeEventListener("scrollend", finish);
    run();
  };
  window.addEventListener("scrollend", finish, { once: true });
  window.setTimeout(finish, 420);
}
