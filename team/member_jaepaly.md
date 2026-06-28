# 실험 실행 패킷 — 팀장 (데스크탑) + 집계

> 데스크탑(여유 있는 머신) 담당. **2~3개 모델** 실행 + 마지막 **집계/문서 갱신**.
> 담당 모델: `qwen2.5:3b`, `qwen2.5:14b` (VRAM 여유 시 `qwen2.5:32b` 추가).

## 1. 동기화 (이미 로컬 저장소 보유)
```bash
cd 2026_core
git pull
```

## 2. 모델 설치
```bash
ollama pull qwen3:8b       # ★ judge (이미 있음)
ollama pull qwen2.5:3b
ollama pull qwen2.5:14b
# 여유되면: ollama pull qwen2.5:32b   (~20GB VRAM)
```

## 3. 실행 (담당 모델)
```bash
python run_experiments_v2.py qwen2.5:3b  --seeds 1
python run_experiments_v2.py qwen2.5:14b --seeds 1
# 여유되면: python run_experiments_v2.py qwen2.5:32b --seeds 1
```
생성: `output/runs_qwen2.5_3b.jsonl`, `output/runs_qwen2.5_14b.jsonl` (+32b)

## 4. ★ 집계 전 정리 — 옛 20시나리오 런 치우기
당신 데스크탑에는 옛 20시나리오 런(`runs_qwen3.jsonl` 등)이 남아 있다. 새 40시나리오
데이터와 섞이지 않도록 집계 전에 치운다(`.gitignore`라 깃에는 없지만 로컬엔 있음):
```bash
mkdir -p output/_archive_20scn
mv output/runs_qwen3.jsonl output/runs_llama.jsonl output/runs_qwen2.jsonl output/_archive_20scn/ 2>/dev/null
```

## 5. 팀원 파일 수합
이예찬·장승우가 보낸 파일을 `output/` 에 넣는다. 최종적으로 `output/` 에 아래 6개가 있어야 함:
```
runs_qwen3_8b.jsonl      (이예찬)
runs_mistral_7b.jsonl    (이예찬)
runs_llama3.1_8b.jsonl   (장승우)
runs_qwen2.5_7b.jsonl    (장승우)
runs_qwen2.5_3b.jsonl    (팀장)
runs_qwen2.5_14b.jsonl   (팀장)
```

## 6. 집계 + 통계 + 그림
```bash
python analysis_experiment_v2.py    # 조건/모델 집계 + 그림 (runs_*.jsonl 자동 수합)
python interface_risk.py            # 노출 용량 vs 실제 접근
python stats_v2.py                  # (model×scenario) McNemar — n=240 기대
```
- 검정력 확인: `stats_v2.py` 출력의 A vs C/D p값이 유의(p<0.05)로 바뀌는지 확인.
- 이후 README/논문/포스터의 수치·그림 갱신 후 commit/push.

## 7. 가드레일
- [ ] 집계 전 옛 20시나리오 런을 반드시 archive (4단계).
- [ ] judge는 qwen3:8b 고정.
- [ ] 최종 6개 모델 파일이 모두 40시나리오 기준인지 확인 (각 파일 = 40시나리오 × 4조건 × 1seed = **160줄**).
