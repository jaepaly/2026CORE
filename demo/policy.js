// 연구 2(정책 작성) 패널.
//
// replay 패널과 같은 원칙이다 — 시뮬레이션이 아니라 커밋된
// experiments/policy-authoring/policies.jsonl 의 실제 응답을 보여준다. 채점은
// demo/build_replay_index.py 에서 끝나 있고 여기서는 표시만 한다.
//
// 두 실험이 같은 scenario_id 를 쓰므로 위쪽 시나리오 선택 하나로 replay 패널과
// 함께 움직인다. 같은 업무에 대해 "인터페이스가 무엇을 넘겼나"(연구 1)와
// "모델이 무엇을 넘기라고 썼을까"(연구 2)를 같은 화면에서 비교하기 위한 것이다.

const pq = (sel) => document.querySelector(sel);
const pesc = (v) =>
  String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

let policyIndex = null;

function chip(path, kind) {
  // kind: "match" | "over" | "over-sensitive" | "under" | "unknown"
  const label = {
    "over-sensitive": "검토자가 금지한 민감 필드",
    over: "검토자가 뺀 필드",
    under: "검토자가 필요하다고 한 필드",
    unknown: "존재하지 않는 경로",
    match: "일치",
  }[kind];
  return `<span class="pol-chip ${kind}" title="${pesc(label)}">${pesc(path)}</span>`;
}

function modelCard(entry, reviewer) {
  const reviewerSet = new Set(reviewer);
  const overSet = new Set(entry.over);
  const sensitiveSet = new Set(entry.sensitive_over);

  // 모델이 쓴 정책을 그대로 보여주되, 각 경로가 어떻게 채점됐는지 색으로 구분한다.
  const written = entry.allowed.map((p) => {
    if (sensitiveSet.has(p)) return chip(p, "over-sensitive");
    if (overSet.has(p)) return chip(p, "over");
    return chip(p, reviewerSet.has(p) ? "match" : "over");
  });
  const missing = entry.under.map((p) => chip(p, "under"));
  const invented = entry.unknown.map((p) => chip(p, "unknown"));

  const verdict = entry.sensitive_over.length
    ? `<span class="pol-verdict bad">민감 필드 ${entry.sensitive_over.length}개 허용</span>`
    : `<span class="pol-verdict ok">민감 필드 허용 없음</span>`;

  return `
    <article class="pol-card">
      <header>
        <strong>${pesc(entry.model)}</strong>
        ${verdict}
        <span class="pol-counts">허용 ${entry.allowed.length} · 과잉 ${entry.over.length} · 누락 ${entry.under.length}</span>
      </header>
      <div class="pol-row">
        <span class="pol-rowlabel">모델이 쓴 정책</span>
        <div class="pol-chips">${written.join("") || '<em class="pol-none">(없음)</em>'}</div>
      </div>
      <div class="pol-row">
        <span class="pol-rowlabel">빠뜨린 필드</span>
        <div class="pol-chips">${missing.join("") || '<em class="pol-none">없음</em>'}</div>
      </div>
      ${invented.length ? `
      <div class="pol-row">
        <span class="pol-rowlabel">존재하지 않는 경로</span>
        <div class="pol-chips">${invented.join("")}</div>
      </div>` : ""}
      <footer><code>${pesc(entry.run_id)}</code></footer>
    </article>`;
}

export function renderPolicy(scenarioId) {
  const host = pq("#polBody");
  if (!host || !policyIndex) return;
  const entry = policyIndex.policies?.[scenarioId];
  if (!entry) {
    host.innerHTML = `<div class="rp-empty">이 시나리오의 정책 작성 기록이 없습니다.</div>`;
    return;
  }

  const reviewerChips = entry.reviewer.map((p) => chip(p, "match")).join("");
  const forbiddenChips = entry.forbidden
    .map((p) => `<span class="pol-chip over-sensitive">${pesc(p)}</span>`)
    .join("");

  host.innerHTML = `
    <div class="pol-standard">
      <div class="pol-row">
        <span class="pol-rowlabel">인간 검토자 (기준)</span>
        <div class="pol-chips">${reviewerChips}</div>
      </div>
      <div class="pol-row">
        <span class="pol-rowlabel">검토자가 금지한 민감 필드</span>
        <div class="pol-chips">${forbiddenChips || '<em class="pol-none">없음</em>'}</div>
      </div>
    </div>
    <div class="pol-grid">${entry.models.map((m) => modelCard(m, entry.reviewer)).join("")}</div>`;
}

export function initPolicy(index) {
  policyIndex = index;
  const summary = index.policy_summary;
  const host = pq("#polSummary");
  if (host && summary && summary.calls) {
    host.innerHTML = `
      <span><b>${summary.calls}</b>콜 · 4모델</span>
      <span>정확 일치 <b>${(summary.exact_match * 100).toFixed(0)}%</b></span>
      <span>검토자 <b>${summary.mean_reviewer_fields}</b> vs 모델 <b>${summary.mean_model_fields}</b> 필드</span>
      <span class="warn">과잉 허용 <b>${summary.mean_over}</b> · 과잉 차단 <b>${summary.mean_under}</b></span>
      <span class="warn">민감 필드 허용 <b>${(summary.any_sensitive_rate * 100).toFixed(0)}%</b></span>`;
  }
}
