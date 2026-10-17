#!/usr/bin/env bash
# PreToolUse guard: Claude must never see held-out evaluation data (eval/<W>/, W = "held"+"out"). Ported from the
# side-quest (plan 001).
#  - Read: deny paths under eval/W/ (docs like docs/HELDOUT.md and the sanctioned script stay readable).
#  - Grep/Glob: deny anything referencing W.
#  - Write/Edit/NotebookEdit: deny writing under eval/W/; CODE files mentioning W only in the sanctioned script (.md/.txt docs exempt).
#  - Bash: commands mentioning W allowed only as `python3 eval/run_W.py [simple args]` (no pipes/redirects/chaining).
# The sanctioned script prints aggregate metrics only (docs/HELDOUT.md).
W="held""out"
SANCTIONED_RE="eval/run_${W}\.py"
input="$(cat)"
tool="$(jq -r '.tool_name' <<<"$input")"
deny() {
  jq -n --arg r "$1" '{hookSpecificOutput: {hookEventName: "PreToolUse", permissionDecision: "deny", permissionDecisionReason: $r}}'
  exit 0
}
case "$tool" in
  Bash)
    cmd="$(jq -r '.tool_input.command // ""' <<<"$input")"
    grep -qi "$W" <<<"$cmd" || exit 0
    [[ "$cmd" =~ ^python3\ ${SANCTIONED_RE}(\ [A-Za-z0-9_./=:-]+)*$ ]] && exit 0
    deny "Held-out data is off-limits. Only eval/run_${W}.py may touch it, run as plain 'python3 eval/run_${W}.py <args>'." ;;
  Read)
    fp="$(jq -r '.tool_input.file_path // ""' <<<"$input")"
    grep -qi "eval/$W" <<<"$fp" && deny "Held-out data is off-limits to Claude (read blocked)."
    exit 0 ;;
  Grep|Glob)
    fields="$(jq -r '[.tool_input.path, .tool_input.pattern, .tool_input.glob] | map(select(. != null)) | join(" ")' <<<"$input")"
    grep -qi "$W" <<<"$fields" && deny "Held-out data is off-limits to Claude (search blocked)."
    exit 0 ;;
  Write|Edit|NotebookEdit)
    fp="$(jq -r '.tool_input.file_path // .tool_input.notebook_path // ""' <<<"$input")"
    grep -qi "eval/$W" <<<"$fp" && deny "Writing into held-out data is blocked."
    [[ "$fp" =~ \.(md|txt)$ ]] && exit 0   # docs may name the folder/script; they cannot access data
    body="$(jq -r '[.tool_input.content, .tool_input.new_string, .tool_input.new_source] | map(select(. != null)) | join(" ")' <<<"$input")"
    grep -qi "$W" <<<"$body$fp" || exit 0
    [[ "$fp" =~ ${SANCTIONED_RE}$ ]] && exit 0
    deny "Only eval/run_${W}.py may reference held-out data." ;;
esac
exit 0
