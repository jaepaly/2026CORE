#!/usr/bin/env python3
"""데모 자산 URL 에 내용 해시를 박는다.

GitHub Pages 는 `Cache-Control: max-age=600` 을 보낸다. 그래서 한 번 방문한
브라우저는 10분 동안 옛 .js/.css 를 계속 쓴다. 배포는 정상인데 화면만 옛것인
상태가 되어, 고친 것이 반영되지 않은 것처럼 보인다. 실제로 이 저장소에서
여러 번 오진의 원인이 됐다 — 심지어 탭 하나가 통째로 동작하지 않는 것처럼
보이기도 했다(캐시된 tabs.js 가 새 탭 키를 모르는 값으로 취급).

파일 내용이 바뀌면 URL 도 바뀌게 만들면 이 문제가 사라진다. 해시가 같으면
URL 도 같으므로 안 바뀐 파일은 캐시를 그대로 쓴다.

    python demo/stamp_assets.py

- index.html 의 <link href="./x.css">, import ... from "./x.js"
- 각 모듈 안의 import ... from "./y.js" (모듈 그래프 전체)
둘 다 ?v=<해시> 로 바꾼다. 이미 붙어 있으면 먼저 떼고 다시 계산하므로
몇 번을 돌려도 결과가 같다.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

DEMO = Path(__file__).resolve().parent
INDEX = DEMO / "index.html"

#: 해시 대상. 순서를 고정해야 같은 내용에서 같은 해시가 나온다.
ASSETS = sorted([p.name for p in DEMO.glob("*.js") if not p.name.startswith("_")] +
                [p.name for p in DEMO.glob("*.css")])

STAMP = re.compile(r"\?v=[0-9a-f]{8}")


def strip(text: str) -> str:
    return STAMP.sub("", text)


def content_hash() -> str:
    """자산 전체의 내용 해시. 스탬프를 뗀 상태로 계산해야 안정적이다."""
    digest = hashlib.sha256()
    for name in ASSETS:
        digest.update(name.encode("utf-8"))
        digest.update(strip((DEMO / name).read_text(encoding="utf-8")).encode("utf-8"))
    return digest.hexdigest()[:8]


def stamp_imports(text: str, version: str) -> str:
    """모듈 사이의 import 경로에 스탬프를 박는다."""
    def repl(match: re.Match) -> str:
        return f'{match.group(1)}"./{match.group(2)}.js?v={version}"'

    return re.sub(r'(from |import\()"\./(\w+)\.js"', repl, text)


def main() -> None:
    version = content_hash()

    for name in ASSETS:
        if not name.endswith(".js"):
            continue
        path = DEMO / name
        original = path.read_text(encoding="utf-8")
        updated = stamp_imports(strip(original), version)
        if updated != original:
            path.write_text(updated, encoding="utf-8")

    html = strip(INDEX.read_text(encoding="utf-8"))
    html = stamp_imports(html, version)
    html = re.sub(r'href="\./(\w+)\.css"', rf'href="./\1.css?v={version}"', html)
    INDEX.write_text(html, encoding="utf-8")

    print(f"stamped {len(ASSETS)} assets with v={version}")


if __name__ == "__main__":
    main()
