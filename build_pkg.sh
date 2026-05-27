#!/bin/bash
# YT Music Downloader — .pkg 인스톨러 빌드
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/dist/yt-music"
VERSION="1.0.0"
IDENTIFIER="com.ytmusic.downloader"
OUTPUT="$SCRIPT_DIR/yt-music.pkg"

echo "══════════════════════════════════════════════"
echo "  ♪  YT Music Downloader — PKG 빌드"
echo "══════════════════════════════════════════════"
echo ""

# ── 바이너리 확인 ─────────────────────────────────
if [ ! -f "$BINARY" ]; then
  echo "❌  dist/yt-music 바이너리가 없습니다."
  echo "    먼저 ./build_app.sh 를 실행하세요."
  exit 1
fi

# ── 임시 디렉터리 정리 ────────────────────────────
WORKDIR="$(mktemp -d)"
trap "rm -rf $WORKDIR" EXIT

# ── 1. 페이로드 구성 ─────────────────────────────
echo "▶  [1/3] 페이로드 구성 중..."
PAYLOAD="$WORKDIR/payload"
mkdir -p "$PAYLOAD/usr/local/bin"
cp "$BINARY" "$PAYLOAD/usr/local/bin/yt-music"
chmod +x "$PAYLOAD/usr/local/bin/yt-music"
echo "✓  /usr/local/bin/yt-music 에 설치되도록 구성"

# ── 2. 설치 후 스크립트 ───────────────────────────
echo "▶  [2/3] 설치 후 스크립트 작성 중..."
SCRIPTS="$WORKDIR/scripts"
mkdir -p "$SCRIPTS"

cat > "$SCRIPTS/postinstall" << 'EOF'
#!/bin/bash
# MugicDownload 폴더 생성
TARGET_USER=$(stat -f "%Su" /dev/console 2>/dev/null || echo "$USER")
TARGET_HOME=$(eval echo "~$TARGET_USER")
DOWNLOAD_DIR="$TARGET_HOME/Documents/MugicDownload"
mkdir -p "$DOWNLOAD_DIR"
echo "✓  다운로드 폴더 생성: $DOWNLOAD_DIR"
exit 0
EOF
chmod +x "$SCRIPTS/postinstall"
echo "✓  postinstall 스크립트 작성 완료"

# ── 3. pkg 빌드 ──────────────────────────────────
echo "▶  [3/3] pkg 빌드 중..."
[ -f "$OUTPUT" ] && rm -f "$OUTPUT"

pkgbuild \
  --root "$PAYLOAD" \
  --scripts "$SCRIPTS" \
  --identifier "$IDENTIFIER" \
  --version "$VERSION" \
  --install-location "/" \
  "$OUTPUT"

echo ""
echo "══════════════════════════════════════════════"
echo "  ✅  빌드 완료!"
echo ""
echo "  파일: $OUTPUT"
SIZE=$(du -sh "$OUTPUT" | cut -f1)
echo "  크기: $SIZE"
echo ""
echo "  설치 후 실행 방법:"
echo "    yt-music"
echo ""
echo "  ⚠️  미서명 패키지 — 받는 사람이 처음 설치 시:"
echo "    시스템 설정 → 개인 정보 보호 및 보안 → 어쨌든 열기"
echo "══════════════════════════════════════════════"
