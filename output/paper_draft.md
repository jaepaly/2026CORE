# 업무를 돕는 AI는 어디까지 읽어야 하는가: 도구 인터페이스의 필드 단위 최소권한이 LLM 에이전트의 민감정보 전달에 미치는 효과 — 사전 등록 2×2 실험

**박재현 · 장승우 · 이예찬** (이예찬: 산업보안학과, 20216160)
지도교수: 미정 (확정 후 기재)

---

## 초록

도구(tool) 사용형 AI 에이전트가 이메일·주소록·캘린더에 접근해 업무를 수행할 때, 민감정보 노출 위험이 **모델의 판단**에서 오는지 **도구 인터페이스의 권한 설계**에서 오는지를 사전 등록 실험으로 측정하였다. 합성 워크스페이스(연락처 15·이메일 33·캘린더 7, 민감 PII와 인젝션 페이로드 포함)에서, **프롬프트 축**(중립 vs 최소화 지시)과 **projection 축**(없음 vs task-aware 필드 projection)을 독립으로 조작한 2×2 설계(조건 A/B/C/D)를 구성하였다. 시나리오 48건은 2인 독립 검토와 자동 게이트(prompt-echo·풀 수 없는 과제·모순 라벨 차단)를 거쳐 43건이 승인되었고, tool-call 형식 준수율 80% 미만 모델을 제외하는 파일럿 게이트를 통과한 4개 로컬 LLM(qwen2.5:3b/7b, qwen3:8b, llama3.1:8b)으로 **688 runs**(기술 실패 0)를 실행하였다. 결과를 전달·행동·엔드포인트 3계층으로 분리해 보고한다. (1) **전달 계층**: task-aware 필드 projection은 run당 실제 전달된 업무외 민감 필드를 A 0.50 / B 0.52에서 C·D **0.00**으로 제거하였다(A−C 차이 0.50, 95% CI 0.37~0.64; 4모델 전 계열 동일 방향). (2) **프롬프트 축**: 중립 조건과 최소화 지시 조건의 전달량이 사실상 같아(0.50 vs 0.52), 프롬프트 지시는 민감 전달을 줄이지 못했다. (3) **엔드포인트**: 민감 전달 없는 업무 완수(`safe_completion`)는 A 0.01 / B 0.00 / C 0.04 / D 0.03으로 방향은 projection에 유리했으나, 사전 등록한 primary 비교(A vs C)는 McNemar p=0.070으로 **유의하지 않았다**. 업무 성공률 자체가 3~6%로 낮아 엔드포인트 검정력이 부족했기 때문이다. 본 연구는 "모델에게 적게 읽으라고 지시"하는 방어가 전달 계층에서 효과가 없고, 인터페이스가 필드를 반환하지 않도록 설계하는 것이 모델과 무관하게 민감 전달을 제거함을 실증한다. 동시에, 안전한 완수라는 최종 효용에 대한 효과는 현 표본에서 입증되지 않았음을 명시한다.

---

## 1. 서론

AI 에이전트가 사용자의 이메일, 캘린더, 주소록 등 민감한 개인 데이터에 접근하며 자율적으로 업무를 수행하는 사례가 늘고 있다[1]. 이때 에이전트가 업무에 필요한 범위를 넘어 개인정보를 열람할 가능성과[2], 조작된 콘텐츠(프롬프트 인젝션)가 데이터 유출로 이어질 위험이 제기된다[7].

흔한 대응은 시스템 프롬프트에 "필요한 최소 정보만 읽어라"라고 지시하는 것이다. 그러나 이는 모델의 순응에 의존한다. 대안은 **인터페이스 수준의 집행** — 도구가 애초에 업무에 필요한 필드만 반환하도록 projection을 거는 것이다. 두 방어의 효과를 같은 환경에서 분리 비교한 실증 연구는 드물다.

본 연구는 두 축을 독립 조작하는 사전 등록 2×2 실험으로 이 질문에 답한다.

**연구 질문**
1. 프롬프트 최소화 지시는 실제로 전달되는 민감 필드를 줄이는가?
2. task-aware 필드 projection은 모델과 무관하게 민감 전달을 줄이는가?
3. 두 방어는 업무 완수, 그리고 "민감 전달 없는 업무 완수"에 어떤 영향을 주는가?

### 1.1 탐색 단계(v2)와 재설계 경위

본 실험(v3) 이전의 탐색 실험(v2, 768 runs)에서는 세 가지 교란을 발견하였다: (i) 모든 조건의 기본 프롬프트에 최소화·인젝션 경고 문구가 포함되어 "무방어" 대조군이 없었고, (ii) 정책 조건이 필드 필터와 도구 차단을 함께 바꿔 기전이 분리되지 않았으며, (iii) 성공 판정이 과제 문구 복창만으로 통과 가능해 검색 능력을 측정하지 못했다. v3는 이를 각각 프롬프트 축 분리, projection 단일 조작, 데이터 유래 값을 요구하는 validator와 자동 게이트로 교정하고, 분석 전에 프로토콜을 동결하였다(사전 등록). v2 수치는 본 논문에서 인과 근거로 인용하지 않는다.

---

## 2. 관련 연구

LLM 에이전트의 tool use는 "과도한 권한(over-privilege)" 문제를 낳는다[5]. GDPR·개인정보보호법의 최소정보 원칙[6]은 규범적 기준을 제시하나, 에이전트 맥락에서 인터페이스 설계의 인과 효과를 측정한 연구는 드물다. 2026년 들어 tool-using 에이전트의 유출 경로와 공격 저항성을 평가하는 벤치마크가 등장하고 있으며[8,9], 본 연구는 벤치마크 점수가 아니라 **방어 기전(프롬프트 vs projection)의 분리 측정**에 초점을 둔다는 점에서 구별된다.

---

## 3. 방법론

### 3.1 데이터 환경

합성 워크스페이스는 연락처 15명, 이메일 33건, 캘린더 7일로 구성된다. 연락처 `notes`에 임신·병원 진료·알레르기 등 민감 PII가, 이메일 5건(`e17`·`e29`·`e31`·`e32`·`e33`)의 `body`에 인젝션 페이로드가 삽입되어 있다. 도구는 `search_contacts`/`get_contact`/`search_emails`/`get_email`/`search_calendar`/`create_event` 6종이다.

### 3.2 2×2 설계

| 조건 | 프롬프트 축 | projection 축 |
|---|---|---|
| A | 중립 | 없음 |
| B | 최소화 지시 | 없음 |
| C | 중립 | task-aware 필드 projection |
| D | 최소화 지시 | task-aware 필드 projection |

projection은 시나리오별로 사람이 승인한 `allowed_field_paths`만 도구가 반환하게 한다(예: 회의 조율 과제에서 `get_contact`은 `id`·`name`·`email`·`department`만 반환, `phone`·`notes`·이메일 `body` 제거). 프롬프트 해시를 조건별로 검증해 A==C, A≠B를 manifest에 고정하였다.

### 3.3 시나리오 라벨과 게이트

48개 업무 시나리오 각각에 대해 필요 레코드, 허용 필드, 성공 validator를 2인이 독립 라벨링하고 교차 검토하였다. 자동 게이트(`validate_review_v3.py`)는 (B1) 과제 문구 복창만으로 통과하는 validator, (B2) 허용 필드로 풀 수 없는 과제, (B4) 허용 필드를 금지하는 모순, (B5) 업무와 무관한 개인정보의 필수 지정, (B9) 상세조회만 허용되고 발견 경로가 없는 라벨 등을 차단한다. "도구 0회 호출 에이전트"의 통과율이 0%가 되어야 게이트를 통과한다. 승인 43건 / 폐기 5건(합성 데이터가 과제를 뒷받침하지 않음)이었다.

### 3.4 모델 파일럿 게이트

일부 모델은 도구를 호출하지 않고 "검색하겠습니다"라고 서술만 한다. 이 경우 "전달 0"은 프라이버시가 아니라 형식 미준수다. 중립 조건에서 valid tool-call 비율 ≥80%를 요구하여 `mistral:7b`(0%)·`qwen2.5:14b`(12%) 등을 제외하고, `qwen2.5:3b`·`qwen2.5:7b`·`qwen3:8b`·`llama3.1:8b` 4종(3계열)을 채택하였다.

### 3.5 실행과 사전 등록

4모델 × 43시나리오 × 4조건 × seed 1 = **688 runs**. 전 모델 동일 설정(`max_turns=4`, `temperature=0.0`, `num_predict=1000`, `think=false`)이며 protocol·scenario 해시를 manifest에 동결하였다. primary endpoint는 `safe_completion`(업무 성공 ∧ 업무외 민감 필드 전달 0), primary 비교는 **A vs C만**으로 사전 등록하였다. `runs.jsonl`에는 원문 값 없이 필드 경로·ID·해시·카운트만 기록된다.

### 3.6 3계층 보고

- **전달(delivery)**: 도구 경계에서 모델에게 실제 반환된 업무외 민감 필드 수(run당 평균)
- **행동(behavior)**: validator 기준 업무 성공률
- **엔드포인트**: `safe_completion` — 민감 전달 없이 업무를 완수한 비율

---

## 4. 결과

전체 688 runs, 기술 실패 0, 조건 균형 172×4.

### 4.1 전달 계층 — projection이 민감 전달을 제거한다

| 조건 | run당 민감 전달 |
|---|---:|
| A (중립·projection 없음) | 0.50 |
| B (지시·projection 없음) | 0.52 |
| C (중립·projection) | **0.00** |
| D (지시·projection) | **0.00** |

A−C 차이 **0.50 (95% CI 0.37~0.64)**. 모델별로도 방향이 일치한다:

| 모델 | A | B | C | D |
|---|---:|---:|---:|---:|
| qwen2.5:3b | 0.40 | 0.30 | 0.00 | 0.00 |
| qwen2.5:7b | 0.56 | 0.53 | 0.00 | 0.00 |
| qwen3:8b | 0.47 | 0.51 | 0.00 | 0.00 |
| llama3.1:8b | 0.58 | **0.72** | 0.00 | 0.00 |

### 4.2 프롬프트 축 — 지시는 전달을 줄이지 못했다 (secondary)

중립 A(0.50)와 최소화 지시 B(0.52)의 전달량이 사실상 같다. v2와 달리 이번에는 진짜 "지시 유무" 대조이며, 지시가 민감 전달을 줄인다는 증거는 없었다. llama3.1:8b에서는 지시 조건의 전달이 오히려 높았다(0.58→0.72).

### 4.3 행동 계층 — 업무 성공률은 전반적으로 낮다

task 성공률은 A 0.06 / B 0.05 / C 0.04 / D 0.03. 모델별로는 llama3.1:8b가 A/B에서 0.12로 가장 높았으나 C/D에서 0.02로 떨어졌고, qwen3:8b는 조건과 무관하게 ~0.05였다. projection의 효용 비용이 모델에 따라 다르게 나타날 가능성이 있으나, 낮은 기저 성공률 때문에 확정할 수 없다.

### 4.4 엔드포인트 — primary는 유의하지 않았다

| 조건 | `safe_completion` |
|---|---:|
| A | 0.01 |
| B | 0.00 |
| C | **0.04** |
| D | 0.03 |

A/B에서는 업무에 성공한 run조차 민감 필드가 함께 전달되어 safe로 인정되지 않았다. 사전 등록한 primary 비교 A vs C는 McNemar **p = 0.070**(risk diff −0.035) — 방향은 C 우세지만 α=0.05 기준 유의하지 않다. **"projection이 안전한 완수를 늘린다"는 이 표본에서 입증되지 않았다.**

---

## 5. 고찰

### 5.1 확정된 것

전달 계층의 결과는 명확하다. 필드 projection은 4개 모델 전 계열에서 업무외 민감 전달을 0으로 만들었고(CI가 0을 배제), 프롬프트 지시는 그러지 못했다. 민감정보 통제를 모델의 순응에 맡기는 설계와 인터페이스에서 집행하는 설계의 차이가 실측으로 갈렸다.

### 5.2 입증되지 않은 것과 그 이유

primary endpoint가 유의하지 않은 직접 원인은 **기저 업무 성공률(3~6%)**이다. 성공 자체가 드물면 "안전한 성공"의 조건 간 차이를 검출할 표본이 부족하다. 낮은 성공률의 원인은 (i) 소형 로컬 모델의 능력 한계, (ii) 데이터 유래 값을 요구하는 엄격한 validator, 두 가지가 겹쳐 있으며 본 실험 설계로는 분리되지 않는다. 이는 결함이라기보다 정직하게 보고해야 할 한계다 — validator를 느슨하게 하면 성공률은 오르지만 v2에서 확인했듯 측정 자체가 무의미해진다.

### 5.3 한계

- **인젝션은 행동으로 시험되지 않았다.** 승인 시나리오에서 모델이 악성 본문에 도달한 사례가 없어, projection의 인젝션 차단은 설계 수준(전달 가능 5→0건)에서만 성립한다. clean/poisoned 공격쌍 실험이 별도로 필요하다.
- 소형 로컬 모델 4종·합성 데이터·한국어 업무에 한정된다. tool-eager한 상용 대형 모델에서 과잉 접근이 출현하는지는 미검증이다.
- `safe_completion`의 민감성 판정은 사람이 승인한 필드 라벨에 의존하며, 라벨 자체의 타당성은 2인 검토와 게이트로만 보증된다.
- seed 1개의 결정적 실행이므로 반복 분산은 시나리오 축으로만 확보된다.

### 5.4 실무 함의

에이전트에 데이터 도구를 연결할 때 "적게 읽어라"라는 시스템 프롬프트는 전달 계층에서 측정 가능한 효과가 없었다. 업무 유형별로 반환 필드를 제한하는 projection은 구현이 단순하고(도구 응답 필터), 모델 교체와 무관하게 유지되며, 민감 전달을 제거했다. 최소권한을 프롬프트가 아니라 **인터페이스 계약**으로 두는 것이 방어의 기본값이 되어야 한다.

---

## 6. 결론

사전 등록 2×2 실험(4모델, 688 runs)에서 task-aware 필드 projection은 실제 전달되는 업무외 민감 필드를 완전히 제거했고(A−C 0.50, 95% CI 0.37~0.64), 프롬프트 최소화 지시는 전달을 줄이지 못했다. 민감 전달 없는 업무 완수라는 최종 엔드포인트에서는 방향상 projection이 우세했으나 통계적으로 유의하지 않았다(p=0.070). AI 에이전트의 민감정보 통제는 모델에게 부탁하는 것이 아니라 인터페이스가 무엇을 반환할지 설계하는 문제이며, 그 효용 비용의 정밀한 측정은 업무 성공률을 끌어올린 후속 실험의 과제다.

---

## 참고문헌

[1] Parisi, A., et al. (2022). "The State of AI Agent Evaluation." *arXiv:2203.05675*.
[2] Ruan, Y., et al. (2024). "Identifying the Risks of LM Agents with an LM-Emulated Sandbox." *ICLR*.
[3] Carlini, N., et al. (2022). "Extracting Training Data from Large Language Models." *USENIX Security*.
[4] Shin, J., et al. (2023). "Privacy Risks of Generative AI in Personal Assistant Agents." *AsiaCCS*.
[5] OpenAI. (2023). "Function Calling." *OpenAI API Documentation*.
[6] European Commission. (2016). "General Data Protection Regulation (GDPR)." *EU 2016/679*.
[7] Perez, F., & Ribeiro, M. T. (2022). "Ignore This Title and HackAPrompt." *NeurIPS Workshop*.
[8] "An Evaluation of Data Leakage Risks in Tool-Using LLM Agents in Realistic Scenarios." (2026). *arXiv:2606.17114*.
[9] "TRAP: Benchmark for Task-completion and Resistance to Active Privacy-extraction." (2026). *arXiv:2606.18996*.

---

## 부록 A. 재현

```bash
python -m pytest tests/ -q
python validate_review_v3.py data/scenario_review_v3.csv     # exit 0
python run_experiment_v3.py --experiment-dir experiments/main-<model> --model <model> --max-turns 4
python analysis_experiment_v3.py --experiment-dir experiments/main-qwen2.5-3b \
  --experiment-dir experiments/main-qwen2.5-7b --experiment-dir experiments/main-qwen3-8b \
  --experiment-dir experiments/main-llama3.1-8b
```

프로토콜: [`protocols/v3_protocol.json`](../protocols/v3_protocol.json) · 설계: [`docs/experiment_design_v3.md`](../docs/experiment_design_v3.md) · 원시 실행 기록: `experiments/main-*/runs.jsonl` (원문 값 없음, 해시·카운트만).
