#!/bin/bash
# YT Music Downloader — macOS 앱 빌드 스크립트
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_NAME="YT Music Downloader"
DIST_BIN="$SCRIPT_DIR/dist/yt-music"
LAUNCHER="$HOME/Desktop/$APP_NAME.app"

echo "══════════════════════════════════════════════"
echo "  ♪  YT Music Downloader — 앱 빌드"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. PyInstaller 빌드 ───────────────────────────
echo "▶  [1/4] PyInstaller 단독 실행 파일 생성 중..."
cd "$SCRIPT_DIR"
pyinstaller \
  --onefile \
  --name yt-music \
  --clean \
  --noconfirm \
  app.py

echo "✓  바이너리 생성: $DIST_BIN"
echo ""

# ── 2. AppleScript 런처 작성 ─────────────────────
echo "▶  [2/4] AppleScript 런처 작성 중..."
APPLESCRIPT=$(cat <<'APPLESCRIPT'
set binPath to (POSIX path of (path to home folder)) & "Documents/yt-music/dist/yt-music"

-- 이미 실행 중인 세션이 있으면 새 탭, 없으면 새 창
tell application "Terminal"
    activate
    if (count of windows) > 0 then
        tell application "System Events" to keystroke "t" using command down
        delay 0.3
        do script binPath in front window
    else
        do script binPath
    end if
end tell
APPLESCRIPT
)

TMPSCRIPT="/tmp/yt_music_launcher.applescript"
echo "$APPLESCRIPT" > "$TMPSCRIPT"
echo "✓  스크립트 작성 완료"
echo ""

# ── 3. .app 컴파일 ────────────────────────────────
echo "▶  [3/4] .app 번들 컴파일 중..."
[ -d "$LAUNCHER" ] && rm -rf "$LAUNCHER"
osacompile -o "$LAUNCHER" "$TMPSCRIPT"
echo "✓  런처 생성: $LAUNCHER"
echo ""

# ── 4. 아이콘 설정 ────────────────────────────────
echo "▶  [4/4] 아이콘 설정 중..."
# 시스템 Music.app 아이콘을 복사해서 사용
MUSIC_ICON="/Applications/Music.app/Contents/Resources/ApplicationIcon.icns"
APP_ICON="$LAUNCHER/Contents/Resources/applet.icns"

if [ -f "$MUSIC_ICON" ]; then
    cp "$MUSIC_ICON" "$APP_ICON"
    # Finder 캐시 갱신
    touch "$LAUNCHER"
    echo "✓  아이콘 설정 완료 (Music.app 아이콘 사용)"
else
    echo "⚠  Music.app 아이콘을 찾을 수 없어 기본 아이콘을 사용합니다"
fi

# ── 완료 ──────────────────────────────────────────
echo ""
echo "══════════════════════════════════════════════"
echo "  ✅  빌드 완료!"
echo ""
echo "  앱 위치: ~/Desktop/$APP_NAME.app"
echo ""
echo "  Dock 추가 방법:"
echo "    앱을 Dock으로 드래그 앤 드롭"
echo ""
echo "  Applications 폴더로 이동:"
echo "    mv ~/Desktop/\"$APP_NAME.app\" /Applications/"
echo "══════════════════════════════════════════════"
