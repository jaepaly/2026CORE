// Evidence 탭의 지표 4개.
//
// 이전에는 app.js 가 합성 '개념 시연' 과 이 지표를 함께 들고 있었다. 시연
// 섹션을 들어내면서 지표만 남긴다. 값은 커밋된 산출물에서만 오고, 못 읽으면
// 마크업에 적힌 값을 그대로 둔다 — 화면에 없는 숫자를 지어내지 않는다.
//
//   설계 용량 : output/interface_risk_summary.json (정책 정의에서 계산)
//   실측 전달 : demo/replay_index.json (v3 본 실험 688 runs 집계)

const $ = (selector) => document.querySelector(selector);

/** Evidence 는 '무방어(A)' 를 기준으로 읽는다. 보고서의 1차 비교가 A vs C 이고,
 *  이 숫자들은 "아무 조치도 하지 않으면 얼마나 새는가" 를 말하기 때문이다. */
const BASELINE = "A";

const state = {
  capacity: null,
  malicious: null,
  realized: null,
  safe: null,
};

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Number(value).toFixed(2);
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-store" });
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

async function load() {
  const [risk, v3] = await Promise.allSettled([
    fetchJson("../output/interface_risk_summary.json"),
    fetchJson("./replay_index.json"),
  ]);

  if (risk.status === "fulfilled") {
    for (const row of risk.value.exposure_capacity || []) {
      if (row.policy !== BASELINE) continue;
      state.capacity = row.sensitive_field_score;
      state.malicious = row.malicious_payloads_deliverable;
    }
  }

  if (v3.status === "fulfilled") {
    const row = (v3.value.summary || {})[BASELINE];
    if (row) {
      state.realized = row.delivered_sensitive_per_run;
      state.safe = row.safe_completion_rate;
    }
  }
}

function render() {
  const set = (selector, value) => {
    const el = $(selector);
    if (el && value !== null && value !== undefined) el.textContent = value;
  };
  set("#capacityMetric", formatNumber(state.capacity));
  set("#realizedMetric", formatNumber(state.realized));
  set("#malMetric", state.malicious);
  set("#successMetric", formatNumber(state.safe));
}

export async function initMetrics() {
  await load();
  render();
}
