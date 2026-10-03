#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -n "${ROC_BIN:-}" ] && [ -x "$ROC_BIN" ]; then
    :
elif command -v roc >/dev/null 2>&1; then
    ROC_BIN="$(command -v roc)"
elif [ -x "$HOME/.local/bin/roc" ]; then
    ROC_BIN="$HOME/.local/bin/roc"
elif [ -x "$HOME/roc/roc" ]; then
    ROC_BIN="$HOME/roc/roc"
else
    echo "Error: Roc compiler not found!" >&2
    exit 1
fi

echo "========================================="
echo " Dynamic Island (Roc) - Test Suite"
echo " Compiler: $("$ROC_BIN" version)"
echo " Directory: $SCRIPT_DIR"
echo "========================================="

TOTAL_FILES=0
CHECK_SUCCESS=0
TEST_SUCCESS=0

ROC_FILES=()
while IFS= read -r -d $'\0' file; do
    ROC_FILES+=("$file")
done < <(find "$SCRIPT_DIR" -maxdepth 1 -name "*.roc" -print0 | sort -z)

if [ ${#ROC_FILES[@]} -eq 0 ]; then
    echo "Error: No .roc files found in $SCRIPT_DIR!" >&2
    exit 1
fi

for roc_file in "${ROC_FILES[@]}"; do
    filename="$(basename "$roc_file")"
    TOTAL_FILES=$((TOTAL_FILES + 1))
    echo -n "Checking $filename ... "

    if ! check_output="$("$ROC_BIN" check "$roc_file" 2>&1)"; then
        echo "FAILED"
        echo "$check_output" >&2
        exit 1
    fi
    CHECK_SUCCESS=$((CHECK_SUCCESS + 1))
    echo -n "OK | Testing ... "

    if ! test_output="$("$ROC_BIN" test "$roc_file" 2>&1)"; then
        echo "FAILED"
        echo "$test_output" >&2
        exit 1
    fi
    TEST_SUCCESS=$((TEST_SUCCESS + 1))

    pass_info="$(echo "$test_output" | grep -oE '[0-9]+ passed' || echo 'passed')"
    echo "OK ($pass_info)"
done

echo "========================================="
echo " All $TOTAL_FILES modules checked & tested successfully!"
echo " Modules compiled: $CHECK_SUCCESS/$TOTAL_FILES"
echo " Modules passed:   $TEST_SUCCESS/$TOTAL_FILES"
echo " Status: PASSED (0 errors)"
echo "========================================="

exit 0
