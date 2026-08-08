#!/usr/bin/env bash
# GMTKN55 참조 데이터를 받는다. 저장소에 커밋하지 않는 이유는 170 MB이고 공개 데이터이기 때문.
# 사용: bash scripts/fetch_reference.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEST="$ROOT/data/reference/gmtkn55"

if [ -d "$DEST/.git" ]; then
  echo "이미 존재: $DEST"
  exit 0
fi

mkdir -p "$(dirname "$DEST")"
echo "GMTKN55 클론 중 (약 170 MB)..."
git clone --depth 1 https://github.com/grimme-lab/GMTKN55.git "$DEST"

echo
echo "확인:"
echo "  서브셋 수: $(find "$DEST" -maxdepth 1 -mindepth 1 -type d ! -name '.*' | wc -l | tr -d ' ')"
echo "  용량:      $(du -sh "$DEST" | cut -f1)"
echo
echo "라이선스: CC-BY-4.0 (grimme-lab/GMTKN55)"
echo "인용: Goerigk, Hansen, Bauer, Ehrlich, Najibi, Grimme, PCCP 19, 32184 (2017)"
