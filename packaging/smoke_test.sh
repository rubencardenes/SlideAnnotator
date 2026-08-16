#!/usr/bin/env bash
# Verify a built macOS bundle is self-contained and actually runs.
#
# Usage: packaging/smoke_test.sh [path/to/SlideAnnotator.app]
set -uo pipefail

APP="${1:-dist/SlideAnnotator.app}"
BIN="$APP/Contents/MacOS/SlideAnnotator"
fail=0

step() { printf '\n== %s\n' "$1"; }
ok()   { printf '   ok: %s\n' "$1"; }
bad()  { printf '   FAIL: %s\n' "$1"; fail=1; }

[ -x "$BIN" ] || { echo "no executable at $BIN"; exit 1; }
printf 'bundle: %s (%s)\n' "$APP" "$(du -sh "$APP" | cut -f1)"

step "Host paths leaked into the bundle"
# Absolute paths to the build machine mean the bundle depends on it. Binary
# files are searched too: a dylib's install name is enough to break the app.
leaks=$(grep -rlI -e '/opt/homebrew' -e '/opt/local' -e "$HOME" "$APP" 2>/dev/null)
if [ -n "$leaks" ]; then bad "host paths in:"; echo "$leaks" | sed 's/^/     /'
else ok "no /opt/homebrew, /opt/local or \$HOME references"; fi

step "Non-system dynamic library dependencies"
# Everything must resolve through @loader_path/@rpath or the macOS system
# libraries. Anything else will be missing on the user's machine.
external=$(find "$APP" \( -name '*.dylib' -o -name '*.so' -o -perm +111 -type f \) -print0 2>/dev/null \
  | xargs -0 otool -L 2>/dev/null \
  | grep -E '^\s+/' \
  | grep -vE '^\s+(/usr/lib/|/System/)' \
  | sort -u)
if [ -n "$external" ]; then bad "external dependencies:"; echo "$external" | sed 's/^/     /'
else ok "all dependencies are @loader_path/@rpath or system"; fi

step "Code signature"
if codesign --verify --deep --strict "$APP" 2>&1; then
  ok "signature valid ($(codesign -dv "$APP" 2>&1 | grep -i 'Signature=' || echo 'ad-hoc'))"
else
  bad "codesign --verify failed"
fi

step "Bundled StarDist model"
model="$APP/Contents/Frameworks/slideannotator/resources/models/stardist-versatile-fluo_dynamic.onnx"
[ -f "$model" ] && ok "present ($(du -h "$model" | cut -f1))" || bad "missing at $model"

step "Runtime self-test"
# env -i: an empty environment proves the app does not lean on the developer's
# shell (DYLD_*, PATH to Homebrew, a dev virtualenv...).
if env -i HOME="$HOME" "$BIN" --self-test 2>&1 | grep -E '^  (ok|FAIL)|^self-test'; then
  ok "self-test completed"
else
  bad "self-test did not run"
fi
if ! env -i HOME="$HOME" "$BIN" --self-test >/dev/null 2>&1; then bad "self-test exit code non-zero"; fi

printf '\n'
[ "$fail" -eq 0 ] && echo "SMOKE TEST PASSED" || echo "SMOKE TEST FAILED"
exit "$fail"
