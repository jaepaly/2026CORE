# 핸드오프 — 다른 머신에서 이어받는 에이전트용

> 이 문서는 **대화 맥락 없이 이 저장소만 처음 보는 에이전트**가 읽고 바로 작업할 수 있도록 쓴 것이다.
> 마지막 갱신: 2026-07-31 / 기준 커밋: `1683c62`

## 0. 30초 요약

도구 사용형 AI 에이전트의 민감정보 노출이 **모델 성향**에서 오는지 **도구 인터페이스 권한 설계**에서 오는지를 가르는 실험이다. 사전 등록한 2×2(프롬프트 축 × 필드 projection 축)를 로컬 LLM으로 돌린다.

- 프로토콜: [`protocols/v3_protocol.json`](protocols/v3_protocol.json)
- 설계 문서: [`docs/experiment_design_v3.md`](docs/experiment_design_v3.md) ← **작업 전 반드시 읽을 것**
- primary endpoint: `safe_completion`, primary comparison: **A vs C만**

## 1. 지금 상태

| 항목 | 상태 |
|---|---|
| 시나리오 라벨 | ✅ 완료 — 승인 43 / 폐기 5, 게이트 exit 0 |
| 모델 파일럿 | ✅ 통과 — qwen2.5:3b 100%, qwen3:8b 80%, llama3.1:8b 100% |
| 계측 코드 | ✅ 완료 — 테스트 135개 통과 |
| **본 실험** | 🔄 4개 모델 중 **1개 완료** |

| 모델 | 담당 | 상태 |
|---|---|---|
| `qwen2.5:3b` | (완료) | ✅ 172/172, 기술 실패 0 |
| **`qwen3:8b`** | **이 머신** | ⬅ **당신이 할 일** |
| `qwen2.5:7b` | 장승우 | 대기 |
| `llama3.1:8b` | 이예찬 | 대기 |

## 2. 이 머신에서 할 일

```bash
git pull
pip install requests matplotlib
ollama pull qwen3:8b

python run_experiment_v3.py --experiment-dir experiments/main-qwen3-8b \
    --model qwen3:8b --max-turns 4 --git-commit $(git rev-parse --short HEAD)
```

172 runs(43시나리오 × 4조건). GPU면 2~3시간, CPU면 8시간 이상.
**중단해도 된다.** 완료된 run은 즉시 저장되고 같은 명령을 다시 실행하면 이어서 돌아간다.

완료 확인:

```bash
python -c "print(sum(1 for _ in open('experiments/main-qwen3-8b/runs.jsonl', encoding='utf-8')))"
# 172 가 나와야 한다
```

결과 공유:

```bash
git add experiments/main-qwen3-8b/
git commit -m "run: v3 main study qwen3:8b"
git push
```

`runs.jsonl`에는 원문 값이 없다 — 필드 경로·레코드 ID·해시·카운트만 저장되고 최종 답변과 도구 응답은 sha256으로만 남는다. 커밋해도 안전하다.

## 3. 절대 하면 안 되는 것 ⚠️

이 실험은 **사전 등록**된 것이다. 결과를 본 뒤 설계를 바꾸면 연구 전체가 무효가 된다.

1. **`--max-turns 4` 를 빼지 말 것.** 기본값은 6이지만 네 모델 모두 4로 돌린다. 이 값이 다르면 모델 간 비교가 성립하지 않는다.
2. **`--temperature`, `--num-predict`, `--seeds` 를 건드리지 말 것.** 기본값(0.0 / 1000 / 0) 그대로.
3. **`data/` 아래를 수정하지 말 것.** 합성 데이터와 시나리오 라벨은 2인 검토·조정을 거쳐 고정됐다.
4. **성공률이 낮다고 validator를 손보지 말 것.** 현재 `task_success`가 매우 낮다(qwen2.5:3b에서 A 1/43, C 3/43). 이것을 "고치려고" `success_validator`의 정규식을 완화하는 것은 **결과를 본 뒤 채점 기준을 바꾸는 행위**이며 사후 조작이다. 낮은 성공률 자체가 보고할 결과다.
5. **v2 수치를 이 연구의 발견으로 쓰지 말 것.** README의 "탐색 결과 (v2 · legacy)" 절은 교란된 설계에서 나온 값이다(조건 A가 중립이 아니었고, C/D가 필드 필터와 도구 차단을 함께 바꿨다). 인과적 근거로 인용 금지.
6. **`experiments/main-*` 디렉터리를 모델끼리 공유하지 말 것.** manifest가 모델마다 달라 동결 규칙이 거부한다. 모델당 하나씩 쓴다.

## 4. 이미 나온 결과 (해석 주의)

`qwen2.5:3b` 172 runs 기준. **단일 모델 결과이므로 확정적으로 말하지 말 것.**

**전달 계층 — projection은 설계대로 작동한다**

| 조건 | run당 민감 필드 |
|---|---|
| A | 0.40 |
| B | 0.30 |
| C / D | **0.00** |

A−C 차이 0.40, paired bootstrap 95% CI 0.16~0.67 (0을 포함하지 않음).

**엔드포인트 — primary는 유의하지 않다**

`safe_completion` A 0.02 / C 0.07, 불일치 4쌍, McNemar **p = 0.625**.
민감 전달은 확실히 줄지만 `safe_completion = task_success AND 민감전달 0` 이라, 업무 성공 자체가 드물면 차이가 드러나지 않는다.

**secondary — 최소화 프롬프트가 오히려 방해하는 것으로 보인다**

| | task_success | 턴 소진 |
|---|---|---|
| A·C (지시 없음) | 4/86 | 1 |
| B·D (최소화 지시) | **0/86** | 7 |

v2에서는 조건 A에 이미 최소화 문구가 있어 이 대조가 불가능했다. v3의 중립 A 덕분에 처음 측정되는 축이다. **단, 단일 모델·소표본이므로 관찰일 뿐이다.**

## 5. 네 모델이 다 모인 뒤

```bash
python analysis_experiment_v3.py \
    --experiment-dir experiments/main-qwen2.5-3b \
    --experiment-dir experiments/main-qwen3-8b \
    --experiment-dir experiments/main-장승우 \
    --experiment-dir experiments/main-이예찬

python figures_v3.py --experiment-dir ... (동일하게 반복)
```

`--experiment-dir`를 반복하면 여러 머신 결과를 합친다(같은 run 키는 중복 제거).
모델이 2개 이상이면 모델별 비교 그림이 자동으로 추가된다.

그 다음 순서: 공격 실험(clean/poisoned, secondary) → 논문·포스터 재작성.
현재 논문(`output/paper_draft.md`)과 포스터(`poster_outline.md`)는 v2 기준이라 **폐기 배너가 붙어 있다.** 결과가 나온 뒤 새로 쓴다.

## 6. 문제 대처

| 증상 | 원인 / 대처 |
|---|---|
| `no approved scenarios` | `git pull`이 안 됨. 최신 master인지 확인 |
| `manifest 거부: ...` | 다른 설정으로 같은 폴더에 실행. 폴더 이름을 바꿀 것 |
| `technical_failure` 반복 | ollama가 죽었거나 모델이 없음. `ollama list` 확인 |
| 테스트 실패 | `python -m pytest tests/ -q` 로 재현. 135개가 통과해야 정상 |

## 7. 더 읽을 것

- [`README.md`](README.md) — 연구 현황, 팀원 실행 매뉴얼, v2 legacy 결과와 그 한계
- [`docs/experiment_design_v3.md`](docs/experiment_design_v3.md) — 사전 등록 설계, 3계층 분리, **완료 전 금지 주장 목록**
- `data/scenario_review_v3.csv` 의 `review_notes` — 각 라벨의 판단 근거가 1차 → 2차 → 조정 순으로 남아 있다
