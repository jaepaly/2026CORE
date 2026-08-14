# 연구 기록 — 설계 경위 · 게이트 · 재현 · legacy

README는 **무엇을 묻고 무엇이 나왔는지**만 담습니다. 이 문서는 그 뒤의 과정 기록입니다 —
왜 실험을 다시 설계했는지, 품질 게이트가 무엇을 막는지, 어떻게 재현하는지, 그리고
인과 근거로 쓰지 않는 v2 탐색 결과.

- 설계서: [`experiment_design_v3.md`](experiment_design_v3.md) (연구 1) · [`policy_authoring_v3.md`](policy_authoring_v3.md) (연구 2)
- 결과 전문: [`policy_authoring_results_v3.md`](policy_authoring_results_v3.md)
- 데이터 근거: [`data_provenance_v3.md`](data_provenance_v3.md)

---

## 1. 어떻게 여기까지 왔나 — v2 탐색에서 v3 사전 등록으로

처음 설계(v2, 768 runs)를 감사하다가 **세 가지 교란**을 발견해 실험 전체를 재설계했습니다. 이 이력 자체가 연구의 일부입니다.

| v2에서 발견한 교란 | v3에서의 교정 |
|---|---|
| **조건 A가 무방어가 아니었다** — [`llm_agent_v2.py:184`](../llm_agent_v2.py#L184)의 기본 프롬프트가 *모든 조건*에 "최대한 적은 개인정보로", "불필요한 전체 열람은 피하세요"를 넣고 있었다 | 프롬프트 축을 분리해 **진짜 중립 조건 A**를 만들었다. "지시 유무" 대조가 v3에서 처음 성립 |
| **C/D가 필드 필터와 도구 차단을 함께 바꿨다** — 어느 기전의 효과인지 분리 불가 | v3는 **projection 축만** 조작한다. 네 조건 모두 `tool_denial: none` |
| **성공 판정이 과제 문구 복창만으로 통과** — 검색 능력을 측정하지 못함 | 데이터에서만 얻을 수 있는 값을 요구하도록 validator를 재작성하고 **자동 게이트**로 강제 |

그래서 v2 수치는 인과 근거로 인용하지 않습니다(부록 A에 보존). v3는 분석 전에 프로토콜·시나리오 해시를 manifest에 동결한 **사전 등록** 실험입니다.

---

## 2. 품질 게이트 (방법론 기여)

1. **시나리오 라벨** — 2인 독립 검토 + 자동 게이트([`validate_review_v3.py`](../validate_review_v3.py), B1~B9). "도구 0회 호출 에이전트" 통과율 **0%** 강제. 승인 43 / 폐기 5.
2. **모델 파일럿** — tool-call 형식 준수 ≥80%만 채택(`mistral:7b` 0%, `qwen2.5:14b` 12% 제외). **"전달 0"이 프라이버시가 아니라 형식 미준수**인 오염을 차단.
3. **연구 2 공정성 조건** — 검토자가 허용한 모든 경로가 모델에게 제시된 어휘 안에 있을 것(아니면 낼 수 없는 답을 오답 처리하게 됨), 프롬프트에 검토자의 정답이 없을 것. 둘 다 자동 테스트로 강제.
4. **값 없는 산출물** — 필드 경로·레코드 ID·해시·카운트만 기록. 합성 데이터 문자열 174개 중 산출물 등장 **0건** 확인.

## 3. 재현 방법

```bash
python -m pytest tests/ -q                                  # 154 tests
python validate_review_v3.py data/scenario_review_v3.csv    # 라벨 게이트 (exit 0 이어야 진행)
```

```bash
# 연구 1 — 모델 파일럿 → 스모크 → 본 실험 (모델별 분산 가능, 중단 시 재개)
python run_model_pilot_v3.py --experiment-dir experiments/pilot \
    --model qwen3:8b --model llama3.1:8b --model qwen2.5:7b --model qwen2.5:3b
python run_experiment_v3.py --experiment-dir experiments/smoke --model qwen3:8b --limit 3
python run_experiment_v3.py --experiment-dir experiments/main-qwen3-8b \
    --model qwen3:8b --max-turns 4 --git-commit $(git rev-parse --short HEAD)

# 연구 1 집계 (--experiment-dir 반복으로 모델 합산)
python analysis_experiment_v3.py --experiment-dir experiments/main-qwen2.5-3b \
    --experiment-dir experiments/main-qwen2.5-7b \
    --experiment-dir experiments/main-llama3.1-8b \
    --experiment-dir experiments/main-qwen3-8b
python figures_v3.py --experiment-dir ... (동일하게 반복)

# 연구 2 — 정책 작성 (172콜, 도구 없는 단발 호출이라 훨씬 빠름)
python run_policy_authoring_v3.py --experiment-dir experiments/policy-authoring \
    --model qwen2.5:3b --model qwen2.5:7b --model llama3.1:8b --model qwen3:8b
python analysis_policy_authoring_v3.py --experiment-dir experiments/policy-authoring
python figures_policy_authoring_v3.py --experiment-dir experiments/policy-authoring
```

manifest는 첫 실행에 동결되며 설정이 다른 채로 같은 디렉터리에 쓰려 하면 거부합니다. 부트스트랩 신뢰구간은 리샘플링 전 정렬하므로 **명령줄 인자 순서와 무관**합니다. 그림은 산출물에서 바로 그리므로 **포스터의 숫자를 항상 원본까지 추적**할 수 있습니다.

---

# 부록

## A. v2 탐색 결과 (legacy · 인과 근거로 인용하지 않음)

v2는 4모델 × 48시나리오 × 4조건 × 1seed = **768 runs**로, 2절의 세 가지 교란 때문에 인과 해석이 성립하지 않습니다. 다만 **교란과 무관하게 유효한 두 가지**가 있어 남겨 둡니다.

- **설계 수준 노출 용량 계산** — 필드 필터 없음 151.5 / 악성 전달 5건, 필드 최소권한 10.5 / 0건 (정책 정의에서 계산되므로 실행과 무관).
- **필드 제거 기전이 실제로 작동함** — 같은 데이터에서 필드 필터 없는 조건의 도구 반환 로그에 연락처 `notes`의 민감 건강정보가 **69건**(A 35 / B 34) 전달됐고, 필드 최소권한 조건에서는 **0건**이었다. [`legacy_delivery_scan_v2.py`](../legacy_delivery_scan_v2.py)로 재현.

그 외 v2의 접근량·성공률·trade-off 수치는 조건 A가 이미 최소화 지시를 포함했다는 사실 때문에 해석할 수 없습니다. 재현 명령:

```bash
python run_experiments_v2.py <model> --seeds 1
python analysis_experiment_v2.py ; python interface_risk.py ; python interface_realized.py ; python stats_v2.py
```

> `experiment.py`, `llm_agent.py`, `run_experiments_v3.py`, `run_paper_pipeline.py`는 v1/초기 탐색 코드입니다. 특히 **`run_experiments_v3.py`는 이름과 달리 v3 프로토콜과 무관한 옛 러너**이므로 본 실험에 쓰지 않습니다.

## B. 본 실험 실행 기록

| 모델 | 담당 | 결과 |
|---|---|---|
| `qwen2.5:3b` | 박재현 | ✅ 172/172, 기술 실패 0 |
| `qwen2.5:7b` | 장승우 | ✅ 172/172, 기술 실패 0 |
| `qwen3:8b` | 박재현 (GPU, 62분) | ✅ 172/172, 기술 실패 0 |
| `llama3.1:8b` | 이예찬 | ✅ 172/172, 기술 실패 0 |

동일 protocol·scenario 해시로 실행됐음을 manifest로 검증했습니다.

**연구 2 (정책 작성)** — `experiments/policy-authoring`, 4모델 × 43시나리오 = 172콜, 파싱 실패 0 / 기술 실패 0.
실행 중 프롬프트 문구 결함(필드 목록을 "아래"로 지칭하나 실제로는 위)을 원문 응답 검수에서 발견해, 20% 지점에서 기존 33건을 버리고 전체를 재시작했습니다. **결과를 보고 고친 것이 아니라 계측 검증 중 발견한 것**이며, 프롬프트가 섞인 데이터셋을 남기지 않기 위한 조치입니다.

> manifest 간 `protocol_sha256`이 두 값으로 갈리는 것은 Windows `core.autocrlf`의 줄바꿈 변환 탓이며 프로토콜 *내용*은 네 모델이 동일합니다(각 manifest에 박힌 `protocol` 객체가 현재 파일과 일치). 상세는 [`HANDOFF.md`](../HANDOFF.md).

## C. 시나리오 라벨 상세

결과는 [`data/scenario_review_v3.csv`](../data/scenario_review_v3.csv)에 있습니다. 각 행의 판단 근거는 `review_notes`에 1차 근거 → `[2차/이름]` → `[조정/박재현]` 순으로 남아 있습니다. 게이트는 언제든 재검증할 수 있습니다(현재 exit 0):

```bash
python validate_review_v3.py data/scenario_review_v3.csv
```
