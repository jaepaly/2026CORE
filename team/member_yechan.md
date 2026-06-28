# 실험 실행 패킷 — 이예찬 (노트북)

> 이 파일을 에이전트(Claude Code 등)에게 그대로 주고 "이대로 실행해줘"라고 하면 됩니다.
> 배경: 도구 인터페이스 권한 설계가 LLM의 개인정보 노출에 미치는 영향 실험.
> 당신은 **2개 모델**을 담당합니다: `qwen3:8b`, `mistral:7b`.

## 0. 사전 점검
- Ollama 설치되어 있어야 함 (https://ollama.com). 노트북이면 8B급까지 권장.
- Python 3.10+ 와 저장소(`2026CORE`)가 로컬에 있어야 함.

## 1. 저장소 동기화
```bash
cd 2026CORE        # 저장소 루트 (없으면: git clone https://github.com/jaepaly/2026CORE.git)
git pull
pip install requests matplotlib   # (없다면)
```

## 2. 모델 설치 (judge 포함 — ★중요)
```bash
ollama pull qwen3:8b      # ★ 채점자(judge). 전원 공통 필수. (당신은 이게 담당 모델이기도 함)
ollama pull mistral:7b    # 담당 모델 2
ollama show mistral:7b    # 출력에 'tools' capability가 있는지 확인 (없으면 알려주세요)
```

## 3. 실행 (한 모델씩, 각각 끝까지)
```bash
python run_experiments_v2.py qwen3:8b --seeds 1
python run_experiments_v2.py mistral:7b --seeds 1
```
- 각 명령은 40시나리오 × 4조건 × 1seed = **160런**. 모델당 약 30~60분.
- 중간에 끊기면 **같은 명령 다시** 실행 → 이어서 진행(재개됨).
- 끝나면 `output/runs_qwen3_8b.jsonl`, `output/runs_mistral_7b.jsonl` 두 파일 생성.

> 참고: mistral 실행 중에는 매 런마다 judge(qwen3:8b)로 잠깐 바뀌어 느릴 수 있음 — 정상.

## 4. 제출 (팀장에게 전달)
- `output/runs_qwen3_8b.jsonl`, `output/runs_mistral_7b.jsonl` 2개 파일
- 환경 1줄: OS / `ollama --version` / 각 모델 `ollama show <model>`의 digest

## 5. 가드레일 (꼭 지켜주세요)
- [ ] 코드·`data/`·`scenarios_v2.json` **수정 금지**. 실행만.
- [ ] `JUDGE_MODEL` 환경변수 건드리지 않기 (judge는 qwen3:8b 고정).
- [ ] `--seeds 1` 그대로.
- [ ] 본인 담당 모델 파일만 제출.
