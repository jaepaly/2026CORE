#!/usr/bin/env python3
"""학술제 제출용 최종 파이프라인: 실험 실행 + 논문 초안 생성."""
import shutil
from pathlib import Path

BASE = Path(__file__).parent
OUTPUT = BASE / "output"
OUTPUT.mkdir(exist_ok=True)

def run_experiment():
    import subprocess, sys
    print("[1/4] 실험 실행 중...")
    res = subprocess.run([sys.executable, "experiment.py"], cwd=BASE, capture_output=True, text=True)
    print(res.stdout)
    if res.returncode != 0:
        print(res.stderr)
        raise RuntimeError("experiment.py 실행 실패")

def collect_figures():
    print("[2/4] 그림 정리 중...")
    figures_dir = OUTPUT / "figures"
    figures_dir.mkdir(exist_ok=True)
    mapping = {
        "fig1_exposure_area.png": "fig1_exposure_area.png",
        "fig2_Condition_A_dist.png": "fig2_condition_a_dist.png",
        "fig2_Condition_B_dist.png": "fig3_condition_b_dist.png",
        "fig3_sensitivity.png": "fig4_sensitivity_curve.png",
    }
    for src_name, dst_name in mapping.items():
        src = OUTPUT / src_name
        dst = figures_dir / dst_name
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  copied {src_name} -> figures/{dst_name}")
        else:
            print(f"  [WARN] {src_name} not found")

def write_paper_copy():
    print("[3/4] 논문 초안 복사 중...")
    paper_src = OUTPUT / "paper_draft.md"
    if not paper_src.exists():
        raise FileNotFoundError("output/paper_draft.md 가 없습니다.")
    dst = BASE / "PAPER.md"
    shutil.copy2(paper_src, dst)
    print(f"  copied to {dst}")

def write_poster():
    print("[4/4] 포스터 초안 템플릿 생성...")
    poster_src = BASE / "poster_outline.md"
    if not poster_src.exists():
        raise FileNotFoundError("poster_outline.md 가 없습니다.")
    dst = OUTPUT / "poster_outline.md"
    shutil.copy2(poster_src, dst)
    print(f"  copied to {dst}")

if __name__ == "__main__":
    run_experiment()
    collect_figures()
    write_paper_copy()
    write_poster()
    print("\n=== 파이프라인 완료 ===")
    print(f"- 논문 초안: {BASE / 'PAPER.md'}")
    print(f"- 포스터 초안: {OUTPUT / 'poster_outline.md'}")
    print(f"- 그림 폴더: {OUTPUT / 'figures'}")
