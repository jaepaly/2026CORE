// v3 본 실험 run replay.
//
// 시뮬레이션이 아니다 — experiments/main-<model>/runs.jsonl 에 커밋된 실제 로그를 재생한다.
// 로그에는 원문 값이 없다(레코드 ID·필드 경로·해시·카운트만). 화면의 원문은 공개 합성
// 데이터(data/ 아래 JSON)를 로그의 delivered_record_ids × delivered_field_paths 와 조인해
// 재구성한 것이므로, 표시 내용 = 그 run 에서 모델에게 실제 전달된 도구 응답이다.

import { initPolicy, renderPolicy } from "./policy.js";

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
    return `<div class="rp-field removed"><b>${esc(label)}</b><span class="rp-strike">${esc(showValue(value))}</span><i>모델에 전달 안 됨</i></div>`;
  }
  const cls = kind === "sensitive" ? "rp-field sensitive" : "rp-field";
  const tag = kind === "sensitive" ? "<i>민감 필드 전달됨</i>" : "";
  return `<div class="${cls}"><b>${esc(label)}</b><span>${esc(showValue(value))}</span>${tag}</div>`;
}

function renderEventRecords(ev, records) {
  const delivered = ev.delivered_field_paths || [];
  const removed = ev.removed_field_paths || [];
  const sensitive = new Set(ev.delivered_sensitive_field_paths || []);
  const ids = ev.delivered_record_ids || [];

  if (ev.policy_decision && ev.policy_decision !== "allowed") {
    return `<div class="rp-denied">정책이 이 호출을 거부: <code>${esc(ev.policy_decision)}</code></div>`;
  }
  if (delivered.includes("error") || delivered.includes("detail")) {
    return `<div class="rp-empty">빈 결과 또는 오류 응답 (레코드 미전달)</div>`;
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
  b.push(`<span class="rp-badge ${run.task_success ? "ok" : "no"}">task ${run.task_success ? "성공" : "실패"}</span>`);
  b.push(`<span class="rp-badge ${run.safe_completion ? "ok" : "no"}">safe ${run.safe_completion ? "달성" : "미달"}</span>`);
  const n = run.excess_sensitive_field_count ?? 0;
  b.push(`<span class="rp-badge ${n > 0 ? "warn" : "ok"}">민감 전달 ${n}</span>`);
  return b.join("");
}

function renderRunColumn(targetSel, badgeSel, run, records) {
  const target = rq(targetSel);
  const badge = rq(badgeSel);
  if (!target) return;
  if (!run) {
    target.innerHTML = `<div class="rp-empty">이 조합의 run이 없습니다.</div>`;
    if (badge) badge.innerHTML = "";
    return;
  }
  if (badge) badge.innerHTML = runBadges(run);
  const events = run.delivery_events || [];
  if (!events.length) {
    target.innerHTML = `<div class="rp-empty">도구 호출 없음 — 모델이 도구를 부르지 않고 종료했습니다.</div>`;
    return;
  }
  const eventsHtml = events
    .map((ev) => {
      const args = (ev.requested_arg_keys || []).join(", ");
      const proj = ev.projection_source && ev.projection_source !== "none"
        ? `<span class="rp-proj">projection: ${esc(ev.projection_source)}</span>` : "";
      return `
        <section class="rp-event">
          <header>
            <span class="rp-turn">T${esc(ev.turn)}</span>
            <code>${esc(ev.tool_name)}(${esc(args)})</code>
            ${proj}
          </header>
          ${renderEventRecords(ev, records)}
        </section>`;
    })
    .join("");
  // 모델 최종 답변은 로그에 보관하지 않는다(sha256·글자수만) — 지어내 표시하지 않는다.
  const finalNote = `
    <div class="rp-empty rp-final">최종 답변: 미보관 — sha256 <code>${esc((run.final_output_sha256 || "").slice(0, 12))}…</code> · ${esc(run.final_output_char_count ?? "?")}자</div>`;
  target.innerHTML = eventsHtml + finalNote;
}

function findRun(rows, scenario, condition) {
  return rows.find((r) => r.scenario === scenario && r.condition === condition) || null;
}

async function renderReplay() {
  const dir = rq("#rpModel").value;
  const scenario = rq("#rpScenario").value;
  const left = rq("#rpLeftCond").value;
  const right = rq("#rpRightCond").value;
  const status = rq("#rpStatus");

  try {
    status.textContent = "runs.jsonl 로드 중…";
    const rows = await fetchRuns(dir);
    const runL = findRun(rows, scenario, left);
    const runR = findRun(rows, scenario, right);

    const meta = state.index.scenarios.find((s) => s.id === scenario);
    rq("#rpTask").textContent = meta ? meta.task : scenario;
    rq("#rpLeftLabel").textContent = `조건 ${left}`;
    rq("#rpRightLabel").textContent = `조건 ${right}`;

    renderRunColumn("#rpLeftEvents", "#rpLeftBadges", runL, state.records);
    renderRunColumn("#rpRightEvents", "#rpRightBadges", runR, state.records);

    // 두 실험이 같은 scenario_id 를 쓰므로 선택 하나로 함께 움직인다.
    // 연구 2 패널은 replay 패널에서 약 1,900px 아래에 있어 폰에서는 두세 화면
    // 떨어진다. 거기에도 같은 선택기를 두고, 어느 쪽을 만지든 양쪽이 같은
    // 시나리오를 가리키도록 값을 맞춘다.
    rq("#polScenario").value = scenario;
    renderPolicy(scenario);

    const model = state.index.experiments.find((e) => e.dir === dir)?.model || dir;
    status.textContent = `${model} · ${scenario} · 커밋된 run 로그 재생 (run_id: ${runL?.run_id ?? "-"} / ${runR?.run_id ?? "-"})`;
  } catch (err) {
    status.textContent = `로드 실패: ${err.message} — 저장소 루트에서 python -m http.server 8080 으로 실행했는지 확인하세요.`;
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
  const condOption = (c, selected) => `<option value="${c}" ${c === selected ? "selected" : ""}>${c}</option>`;
  fillSelect("#rpLeftCond", ["A", "B", "C", "D"], (c) => condOption(c, "A"));
  fillSelect("#rpRightCond", ["A", "B", "C", "D"], (c) => condOption(c, "C"));

  // qwen3:8b 를 기본 모델로 (있으면)
  const preferred = state.index.experiments.find((e) => e.model === "qwen3:8b");
  if (preferred) rq("#rpModel").value = preferred.dir;

  fillSelect("#polScenario", state.index.scenarios, (s) =>
    `<option value="${esc(s.id)}">${esc(s.id)} · ${esc(s.name)}</option>`);

  for (const sel of ["#rpModel", "#rpScenario", "#rpLeftCond", "#rpRightCond"]) {
    rq(sel).addEventListener("change", renderReplay);
  }

  // 연구 2 쪽 선택기는 위 선택기를 움직여 한 경로로만 렌더링한다.
  rq("#polScenario").addEventListener("change", () => {
    rq("#rpScenario").value = rq("#polScenario").value;
    renderReplay();
  });
  rq("#rpReload").addEventListener("click", renderReplay);

  await renderReplay();
}
