// v3 본 실험 run replay.
//
// 시뮬레이션이 아니다 — experiments/main-<model>/runs.jsonl 에 커밋된 실제 로그를 재생한다.
// 로그에는 원문 값이 없다(레코드 ID·필드 경로·해시·카운트만). 화면의 원문은 공개 합성
// 데이터(data/ 아래 JSON)를 로그의 delivered_record_ids × delivered_field_paths 와 조인해
// 재구성한 것이므로, 표시 내용 = 그 run 에서 모델에게 실제 전달된 도구 응답이다.

import { initPolicy, renderPolicy } from "./policy.js?v=6cd5dcc5";
import { revealStage } from "./stage_view.js?v=6cd5dcc5";
import { bareFieldLabel, toolLabel } from "./field_labels.js?v=6cd5dcc5";

/** 조건 코드는 실험 설계의 이름이지 방문자의 언어가 아니다. 코드만 노출하면
 *  처음 온 사람은 A 와 C 가 무엇인지 모른 채 숫자를 보게 된다. 이름을 앞에
 *  두고 코드는 괄호로 내린다 — 보고서·포스터와 대조는 그대로 가능하다. */
const CONDITION_NAME = {
  A: "무방어",
  B: "지시문만",
  C: "필드 최소권한",
  D: "최소권한+지시문",
};

const rq = (sel) => document.querySelector(sel);
const esc = (v) =>
  String(v)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

const state = {
  index: null,          // replay_index.json
  records: null,        // id -> record (contacts/emails/calendar 통합)
  runsCache: new Map(), // experiment dir -> parsed rows
};

async function fetchJsonStrict(path) {
  const res = await fetch(path, { cache: "no-store" });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

async function fetchRuns(dir) {
  if (state.runsCache.has(dir)) return state.runsCache.get(dir);
  const res = await fetch(`../${dir}/runs.jsonl`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${dir}/runs.jsonl: ${res.status}`);
  const text = await res.text();
  const rows = text
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line));
  state.runsCache.set(dir, rows);
  return rows;
}

async function loadRecords() {
  const [contacts, emails, calendar] = await Promise.all([
    fetchJsonStrict("../data/contacts.json"),
    fetchJsonStrict("../data/emails.json"),
    fetchJsonStrict("../data/calendar.json"),
  ]);
  const map = new Map();
  for (const r of [...contacts, ...emails, ...calendar]) map.set(r.id, r);
  return map;
}

/* ---------- field path 해석 ----------
 * search_*  : "[].field" / "[].events[].sub"
 * get_* 등  : "field"
 * "error"/"detail" 은 레코드 없는 오류·빈 응답 경로.
 */
const normPath = (p) => (p.startsWith("[].") ? p.slice(3) : p);

function fieldValue(record, path) {
  const p = normPath(path);
  if (p.includes("[].")) {
    const [container, sub] = p.split("[].", 2);
    const list = record[container];
    if (!Array.isArray(list)) return null;
    const parts = list.map((item) => item?.[sub]).filter((v) => v !== undefined);
    return parts.length ? parts : null;
  }
  const v = record[p];
  return v === undefined ? null : v;
}

const showValue = (v) => (Array.isArray(v) || typeof v === "object" ? JSON.stringify(v, null, 0) : String(v));

function fieldRow(label, value, kind) {
  // kind: "plain" | "sensitive" | "removed"
  if (kind === "removed") {
    return `<div class="rp-field removed"><b>${esc(label)}</b><span class="rp-strike">${esc(showValue(value))}</span><i>AI에게 안 감</i></div>`;
  }
  const cls = kind === "sensitive" ? "rp-field sensitive" : "rp-field";
  const tag = kind === "sensitive" ? "<i>민감정보 넘어감</i>" : "";
  return `<div class="${cls}"><b>${esc(label)}</b><span>${esc(showValue(value))}</span>${tag}</div>`;
}

function renderEventRecords(ev, records) {
  const delivered = ev.delivered_field_paths || [];
  const removed = ev.removed_field_paths || [];
  const sensitive = new Set(ev.delivered_sensitive_field_paths || []);
  const ids = ev.delivered_record_ids || [];

  if (ev.policy_decision && ev.policy_decision !== "allowed") {
    return `<div class="rp-denied">이 호출은 정책이 막았습니다: <code>${esc(ev.policy_decision)}</code></div>`;
  }
  if (delivered.includes("error") || delivered.includes("detail")) {
    return `<div class="rp-empty">빈 결과이거나 오류라 아무것도 오지 않았습니다</div>`;
  }
  if (!ids.length) {
    // create_event 등 — 레코드 조인 없이 응답 필드만 요약
    const names = delivered.map(normPath).join(", ") || "(없음)";
    return `<div class="rp-empty">반환 필드: <code>${esc(names)}</code></div>`;
  }

  return ids
    .map((id) => {
      const record = records.get(id);
      if (!record) {
        const names = delivered.map(normPath).join(", ") || "(없음)";
        return `<div class="rp-empty">생성 결과 <code>${esc(id)}</code> (sandbox) · 반환 필드: <code>${esc(names)}</code></div>`;
      }
      const rows = [];
      for (const path of delivered) {
        const v = fieldValue(record, path);
        if (v === null) continue;
        rows.push(fieldRow(normPath(path), v, sensitive.has(path) ? "sensitive" : "plain"));
      }
      for (const path of removed) {
        const v = fieldValue(record, path);
        if (v === null) continue;
        rows.push(fieldRow(normPath(path), v, "removed"));
      }
      return `<article class="rp-record"><header><strong>${esc(id)}</strong></header>${rows.join("")}</article>`;
    })
    .join("");
}

function runBadges(run) {
  if (!run) return "";
  const b = [];
  b.push(`<span class="rp-badge ${run.task_success ? "ok" : "no"}">업무 ${run.task_success ? "성공" : "실패"}</span>`);
  b.push(`<span class="rp-badge ${run.safe_completion ? "ok" : "no"}">안전 ${run.safe_completion ? "통과" : "미달"}</span>`);
  const n = run.excess_sensitive_field_count ?? 0;
  b.push(`<span class="rp-badge ${n > 0 ? "warn" : "ok"}">민감정보 ${n}건</span>`);
  return b.join("");
}

/* ---------- 전/후 병합 렌더 ----------
 * 폰에서는 두 카드가 세로로 쌓여 560px 짜리가 774px 떨어진다. 화면이 844px 이니
 * 두 조건을 동시에 볼 수 없다 — 나란히 놓고 비교하라는 화면인데 나란히 놓이지
 * 않는다. 그래서 카드를 둘 두지 않고 하나를 제자리에서 바꾼다.
 *
 * 핵심은 같은 DOM 을 유지하는 것이다. 단계마다 다시 그리면 "무엇이 사라졌는지"가
 * 보이지 않는다. 전·후 양쪽의 필드를 한 번에 깔아 두고 data-phase 로 상태만
 * 바꾼다 — 사라지는 그 동작이 곧 "인터페이스가 잘라냈다" 는 설명이다.
 */

const pathsOf = (ev, key) => new Set(ev ? ev[key] || [] : []);

function mergedFieldRows(evBefore, evAfter, record) {
  const bIn = pathsOf(evBefore, "delivered_field_paths");
  const aIn = pathsOf(evAfter, "delivered_field_paths");
  const sensitive = pathsOf(evBefore, "delivered_sensitive_field_paths");

  const all = [...new Set([...bIn, ...aIn])].sort();
  const rows = [];
  for (const path of all) {
    const value = fieldValue(record, path);
    if (value === null) continue;
    const cls = [
      "rp-f",
      bIn.has(path) ? "b-in" : "b-out",
      aIn.has(path) ? "a-in" : "a-out",
      sensitive.has(path) ? "is-sensitive" : "",
    ].filter(Boolean).join(" ");
    const tag = sensitive.has(path) ? '<i class="rp-f-tag">민감</i>' : "";
    rows.push(
      `<div class="${cls}" title="${esc(normPath(path))}"><b>${esc(bareFieldLabel(normPath(path), record.id || ""))}</b><span>${esc(showValue(value))}</span>${tag}</div>`
    );
  }
  return rows.join("");
}

function mergedEvent(evBefore, evAfter, records, turn) {
  const ev = evBefore || evAfter;
  if (!ev) return "";

  const toolBefore = evBefore ? evBefore.tool_name : null;
  const toolAfter = evAfter ? evAfter.tool_name : null;
  const sameTool = toolBefore && toolAfter && toolBefore === toolAfter;
  const name = (t) => (t ? `${toolLabel(t)}` : "호출 없음");
  const toolHtml = sameTool
    ? `<code title="${esc(toolBefore)}">${esc(name(toolBefore))}</code>`
    : `<code class="rp-tool b-only" title="${esc(toolBefore || "")}">${esc(name(toolBefore))}</code>` +
      `<code class="rp-tool a-only" title="${esc(toolAfter || "")}">${esc(name(toolAfter))}</code>`;

  const ids = [
    ...new Set([
      ...(evBefore ? evBefore.delivered_record_ids || [] : []),
      ...(evAfter ? evAfter.delivered_record_ids || [] : []),
    ]),
  ];

  let bodyHtml;
  if (!ids.length) {
    const names = (ev.delivered_field_paths || []).map(normPath).join(", ") || "(없음)";
    bodyHtml = `<div class="rp-empty">반환 필드: <code>${esc(names)}</code></div>`;
  } else {
    bodyHtml = ids
      .map((id) => {
        const record = records.get(id);
        if (!record) {
          return `<div class="rp-empty">생성 결과 <code>${esc(id)}</code> (sandbox)</div>`;
        }
        const rows = mergedFieldRows(evBefore, evAfter, record);
        if (!rows) return "";
        return `<article class="rp-record"><header><strong>${esc(id)}</strong></header>${rows}</article>`;
      })
      .join("");
  }

  return `
    <section class="rp-event">
      <header><span class="rp-turn">T${esc(turn)}</span>${toolHtml}</header>
      ${bodyHtml}
    </section>`;
}

function renderMergedStage(runBefore, runAfter, records) {
  const stage = rq("#rpStage");
  if (!stage) return { comparable: false };

  if (!runBefore && !runAfter) {
    stage.innerHTML = `<div class="rp-empty">이 조합은 실행 기록이 없습니다.</div>`;
    return { comparable: false };
  }

  const evB = (runBefore && runBefore.delivery_events) || [];
  const evA = (runAfter && runAfter.delivery_events) || [];
  const turns = Math.max(evB.length, evA.length);

  if (!turns) {
    stage.innerHTML = `<div class="rp-empty">도구를 한 번도 쓰지 않고 끝냈습니다.</div>`;
    return { comparable: false };
  }

  let html = "";
  for (let i = 0; i < turns; i += 1) {
    html += mergedEvent(evB[i] || null, evA[i] || null, records, i + 1);
  }
  // 최종 답변은 로그에 없다(sha256·글자수만). 지어내지 않는다.
  const sha = (run) => esc((run?.final_output_sha256 || "").slice(0, 12));
  html += `<div class="rp-empty rp-final">최종 답변은 남겨 두지 않았습니다 —
    전 <code>${sha(runBefore)}…</code> · 후 <code>${sha(runAfter)}…</code></div>`;
  stage.innerHTML = html;

  // "같은 요청, 결과만 다름" 이 어디까지 성립하는지 정확히 구분한다.
  // 도구가 갈린 것과 인자가 갈린 것은 원인이 다르다 — 전자는 모델의 선택이
  // 달라진 것이고, 후자는 앞 턴에서 받은 정보가 달라져 생긴 하류 효과다.
  const sameLength = evB.length === evA.length;
  const toolsSame = sameLength && evB.every((e, i) => e.tool_name === evA[i]?.tool_name);
  const argsSame = toolsSame && evB.every((e, i) => e.requested_args_sha256 === evA[i]?.requested_args_sha256);
  const firstTurnIdentical =
    evB[0] && evA[0] &&
    evB[0].tool_name === evA[0].tool_name &&
    evB[0].requested_args_sha256 === evA[0].requested_args_sha256;
  return { comparable: true, toolsSame, argsSame, firstTurnIdentical };
}

function findRun(rows, scenario, condition) {
  return rows.find((r) => r.scenario === scenario && r.condition === condition) || null;
}

function setPhase(phase) {
  const stage = rq("#rpStage");
  if (!stage) return;
  stage.dataset.phase = phase;
  for (const button of document.querySelectorAll(".rp-phase")) {
    button.classList.toggle("is-on", button.dataset.phase === phase);
  }
  const play = rq("#rpPlay");
  if (play) play.textContent = phase === "before" ? "▶ 변화 재생" : "↺ 처음부터";
}

async function renderReplay() {
  const dir = rq("#rpModel").value;
  const scenario = rq("#rpScenario").value;
  const before = rq("#rpBeforeCond").value;
  const after = rq("#rpAfterCond").value;
  const status = rq("#rpStatus");

  try {
    status.textContent = "실행 기록 불러오는 중…";
    const rows = await fetchRuns(dir);
    const runB = findRun(rows, scenario, before);
    const runA = findRun(rows, scenario, after);

    const meta = state.index.scenarios.find((s) => s.id === scenario);
    rq("#rpTask").textContent = meta ? meta.task : scenario;
    rq("#rpBeforeLabel").textContent = `${CONDITION_NAME[before]} (${before})`;
    rq("#rpAfterLabel").textContent = `${CONDITION_NAME[after]} (${after})`;
    rq("#rpBeforeBadges").innerHTML = runBadges(runB);
    rq("#rpAfterBadges").innerHTML = runBadges(runA);

    const cmp = renderMergedStage(runB, runA, state.records);
    setPhase("before");

    // 무엇이 같고 무엇이 달라졌는지 숨기지 않고 그대로 알린다 — 어긋난 경우도
    // 이 실험의 결과이고, 뭉뚱그리면 화면이 거짓을 말하게 된다.
    let note;
    if (!cmp.comparable) {
      note = "";
    } else if (cmp.argsSame) {
      note = "양쪽이 똑같은 요청을 보냈습니다. 달라진 건 돌아온 응답뿐입니다.";
    } else if (cmp.toolsSame) {
      note = cmp.firstTurnIdentical
        ? "첫 요청은 글자 하나까지 같습니다. 그다음부터 달라지는데, 앞에서 받은 정보가 달랐기 때문입니다."
        : "같은 도구를 썼지만 보낸 내용이 다릅니다.";
    } else {
      note = "이 경우는 AI가 서로 다른 도구를 골랐습니다. 응답 차이에 도구 선택 차이가 섞여 있습니다.";
    }
    rq("#rpPlayNote").textContent = note;

    // 두 실험이 같은 scenario_id 를 쓰므로 선택 하나로 함께 움직인다.
    rq("#polScenario").value = scenario;
    renderPolicy(scenario);

    const model = state.index.experiments.find((e) => e.dir === dir)?.model || dir;
    status.textContent = `${model} · ${scenario} · 커밋된 run 로그 (${runB?.run_id ?? "-"} / ${runA?.run_id ?? "-"})`;
  } catch (err) {
    status.textContent = `기록을 불러오지 못했습니다: ${err.message}`;
  }
}

function fillSelect(sel, items, toOption) {
  rq(sel).innerHTML = items.map(toOption).join("");
}

export async function initReplay() {
  state.index = await fetchJsonStrict("./replay_index.json");
  state.records = await loadRecords();
  initPolicy(state.index);

  fillSelect("#rpModel", state.index.experiments, (e) =>
    `<option value="${esc(e.dir)}">${esc(e.model)} (${e.runs} runs)</option>`);
  fillSelect("#rpScenario", state.index.scenarios, (s) =>
    `<option value="${esc(s.id)}">${esc(s.id)} · ${esc(s.name)}</option>`);
  const condOption = (c, selected) =>
    `<option value="${c}" ${c === selected ? "selected" : ""}>${c} · ${CONDITION_NAME[c]}</option>`;
  fillSelect("#rpBeforeCond", ["A", "B", "C", "D"], (c) => condOption(c, "A"));
  fillSelect("#rpAfterCond", ["A", "B", "C", "D"], (c) => condOption(c, "C"));

  // qwen3:8b 를 기본 모델로 (있으면)
  const preferred = state.index.experiments.find((e) => e.model === "qwen3:8b");
  if (preferred) rq("#rpModel").value = preferred.dir;

  fillSelect("#polScenario", state.index.scenarios, (s) =>
    `<option value="${esc(s.id)}">${esc(s.id)} · ${esc(s.name)}</option>`);

  // initReplay 가 두 번 불리면 토글 계열 리스너가 두 겹으로 붙어 "재생" 이
  // 두 번 뒤집혀 제자리로 돌아온다. 절대값을 세팅하는 리스너는 증상이 없어
  // 원인을 찾기도 어렵다. 바인딩은 한 번만 한다.
  if (!state.bound) {
    state.bound = true;
    bindControls();
  }

  await renderReplay();
}

function bindControls() {
  for (const sel of ["#rpModel", "#rpScenario", "#rpBeforeCond", "#rpAfterCond"]) {
    rq(sel).addEventListener("change", renderReplay);
  }

  // 연구 2 쪽 선택기는 위 선택기를 움직여 한 경로로만 렌더링한다.
  rq("#polScenario").addEventListener("change", () => {
    rq("#rpScenario").value = rq("#polScenario").value;
    renderReplay();
  });
  rq("#rpPlay").addEventListener("click", () => {
    const stage = rq("#rpStage");
    const next = stage.dataset.phase === "before" ? "after" : "before";
    // 무대를 먼저 화면에 앉히고 나서 바꾼다 — 바뀌는 걸 못 보면 재생이 아니다.
    revealStage(stage, () => setPhase(next));
  });
  for (const button of document.querySelectorAll(".rp-phase")) {
    button.addEventListener("click", () =>
      revealStage(rq("#rpStage"), () => setPhase(button.dataset.phase)));
  }
}
