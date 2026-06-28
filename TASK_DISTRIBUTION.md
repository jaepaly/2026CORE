# 2026CORE 실험 분산 실행 계획 (interface-risk, 40시나리오 × 6모델)

> 목적: 시나리오를 20→40으로 확장하고 모델을 3→6개로 늘려, 분석 단위 (model×scenario)
> 표본을 60→240으로 키워 통계 검정력을 확보한다. 실행은 모델별로 병렬화한다.
> (결정적 실행이라 seed 1개로 충분 — 자세한 배경은 README/`stats_v2.py` 참고.)

---

## 0. 왜 병렬화가 되는가

각 모델은 `output/runs_<model>.jsonl` **별도 파일**에 기록한다. 따라서 팀원들이 서로 다른
모델을 동시에 돌려도 파일 충돌이 없다. 마지막에 한 명이 모든 `runs_*.jsonl`을 모아 분석한다.

---

## 1. 코디네이터(팀장)가 먼저 — 모두 시작 전 (BLOCKING)

1. **시나리오 40개 확정**: `data/scenarios_v2.json`을 s1~s40으로 확장(각 `task`/`minimum`/`success_criteria`). → 별도 작성 중.
2. **코드 동기화 + base commit**: 아래가 반영된 상태로 commit/push. 모두 이 커밋을 pull한다.
   - `llm_agent_v2.py`: `options.seed` 전달, `AGENT_TEMP`, `JUDGE_MODEL` 분리, `read_all`/정책 미들웨어
   - `run_experiments_v2.py`: 임의 모델명 허용 + `--seeds N`(기본 1)
   - 분석 스크립트들: `runs_*.jsonl` 자동 glob
   - **base commit 해시: `__________` (push 후 기입)**
3. **옛 런 백업**: 기존 20시나리오 데이터가 섞이지 않도록 코디네이터가 한 번만:
   ```bash
   mkdir -p output/_archive_20scn
   mv output/runs_qwen3.jsonl output/runs_llama.jsonl output/runs_qwen2.jsonl output/_archive_20scn/ 2>/dev/null
   ```
   (각 팀원은 자기 머신에서 자기 모델 파일만 새로 생성하므로 별도 백업 불필요.)

---

## 2. 모든 팀원 공통 준비

```bash
git pull                          # base commit 으로 동기화
ollama pull qwen3:8b              # ★ 채점자(judge) — 전원 필수
ollama pull <할당받은 모델>        # 예: qwen2.5:14b
ollama show <할당받은 모델>        # 출력에 'tools' capability 있는지 확인 (없으면 작동 안 함)
```

> ★ `task_success` 채점은 모든 런에서 **동일한 judge(`qwen3:8b`)**로 한다. 그래야 모델 간
> 성공률 비교가 공정하다. 따라서 전원이 `qwen3:8b`를 깔아야 한다(자기 모델 + qwen3:8b).

---

## 3. 모델 할당표 (확정) — 각자 자기 패킷 파일을 에이전트에 넘기면 됨

| 담당 | 머신 | 모델 | ~VRAM | 패킷 |
|---|---|---|---|---|
| 이예찬 | 노트북 | `qwen3:8b`, `mistral:7b` | 5GB | [team/member_yechan.md](team/member_yechan.md) |
| 장승우 | 노트북 | `llama3.1:8b`, `qwen2.5:7b` | 5GB | [team/member_seungwoo.md](team/member_seungwoo.md) |
| 팀장 | 데스크탑 | `qwen2.5:3b`, `qwen2.5:14b` (+32b) | 2.5~20GB | [team/member_jaepaly.md](team/member_jaepaly.md) |

- 6모델 × 160런 = 960런. 3명 병렬이면 각 ~320런(약 1~2시간).
- judge(`qwen3:8b`)는 전원 필수 — 모델 간 성공률 비교를 공정하게 하기 위함.
- 새 모델은 반드시 `ollama show`로 `tools` 지원 확인. 미지원 예: `gemma2`, `phi3`, `deepseek-r1`.

---

## 4. 각 팀원이 실행 (자기 모델만)

```bash
cd 2026_core
python run_experiments_v2.py <모델> --seeds 1
# 예: python run_experiments_v2.py qwen2.5:14b --seeds 1
```

- 중간에 끊겨도 **다시 같은 명령** 실행하면 이어서 진행된다(재개 가능).
- 끝나면 `output/runs_<모델>.jsonl` 1개 생성됨(예: `runs_qwen2.5_14b.jsonl`).

### 제출물 (코디네이터에게 전달)
1. `output/runs_<모델>.jsonl` (본인 파일 1개)
2. 환경 보고 1줄: OS / Ollama 버전 / judge 모델(`qwen3:8b` 확인) / 모델 digest(`ollama show <모델>`의 digest)

---

## 5. 가드레일 (전원 준수)

- [ ] **공유 코드·`data/`·`scenarios_v2.json`를 수정하지 않는다.** 오직 실행만.
- [ ] judge는 `qwen3:8b`로 통일 (`JUDGE_MODEL` 환경변수 건드리지 않기).
- [ ] `--seeds 1` 사용 (임의로 늘리지 않기).
- [ ] 본인 모델의 `runs_<모델>.jsonl`만 제출 (남의 파일 덮어쓰지 않기).
- [ ] `ollama show`로 `tools` 지원을 실행 전에 확인.

---

## 6. 코디네이터가 마지막에 — 집계

```bash
# 팀원들이 보낸 runs_<model>.jsonl 들을 전부 output/ 에 모은 뒤:
python analysis_experiment_v2.py    # 조건/모델 집계 + 그림 (runs_*.jsonl 자동 glob)
python interface_risk.py            # 노출 용량 vs 실제 접근
python stats_v2.py                  # (model×scenario) 단위 McNemar — n=240 기대
```

- 출력: `multi_model_results_v2.json`, `analysis_summary_v2.json`,
  `interface_risk_summary.json`, `stats_summary_v2.json`, `docs/figures/*`
- 이후 README/논문/포스터 수치 갱신.

---

## 7. 의존 관계 요약

```
[코디네이터] 40시나리오 확정 + 코드 commit/push + 옛런 백업
        │ (모두 pull)
        ▼
[팀원 병렬] 각자 모델 1~2개 실행 → runs_<model>.jsonl 제출
        │ (전부 수합)
        ▼
[코디네이터] 분석 3종 실행 → 문서 수치 갱신
```
