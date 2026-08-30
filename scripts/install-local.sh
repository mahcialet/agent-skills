#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat >&2 <<'USAGE'
Usage: ./scripts/install-local.sh <skill-name> [--scope user|project] [--agent codex|github-copilot] [--link] [--force]
USAGE
}

scope="project"
agent="codex"
link_mode="false"
force="false"

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

skill_name="$1"
shift
if [[ ! "$skill_name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
  echo "Invalid Skill name: ${skill_name}" >&2
  exit 2
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      scope="${2:-}"
      shift 2
      ;;
    --agent)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      agent="${2:-}"
      shift 2
      ;;
    --link)
      link_mode="true"
      shift
      ;;
    --force)
      force="true"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage
      exit 2
      ;;
  esac
done

case "$scope" in
  user|project) ;;
  *) echo "Unsupported scope: $scope" >&2; exit 2 ;;
esac
case "$agent" in
  codex|github-copilot) ;;
  *) echo "Unsupported agent: $agent" >&2; exit 2 ;;
esac

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
repo_dir="$(cd -- "${script_dir}/.." && pwd -P)"
source_dir="${repo_dir}/skills/${skill_name}"
orchestrator="${script_dir}/install_local.py"

if [[ ! -f "${source_dir}/SKILL.md" ]]; then
  echo "Skill not found: ${source_dir}" >&2
  exit 1
fi
if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required to install a local Skill." >&2
  exit 1
fi
if [[ ! -f "$orchestrator" ]]; then
  echo "Install helper not found: ${orchestrator}" >&2
  exit 1
fi

if [[ "$scope" == "project" ]]; then
  agents_root="${repo_dir}/.agents"
else
  : "${HOME:?HOME must be set for user-scope installation}"
  agents_root="${HOME}/.agents"
fi

source_state="non-git"
source_oid=""

source_git() {
  (
    unset GIT_ALTERNATE_OBJECT_DIRECTORIES
    unset GIT_COMMON_DIR
    unset GIT_CONFIG
    unset GIT_CONFIG_COUNT
    unset GIT_CONFIG_PARAMETERS
    unset GIT_DIR
    unset GIT_DISCOVERY_ACROSS_FILESYSTEM
    unset GIT_GRAFT_FILE
    unset GIT_IMPLICIT_WORK_TREE
    unset GIT_INDEX_FILE
    unset GIT_INTERNAL_SUPER_PREFIX
    unset GIT_NAMESPACE
    unset GIT_OBJECT_DIRECTORY
    unset GIT_PREFIX
    unset GIT_REPLACE_REF_BASE
    unset GIT_SHALLOW_FILE
    unset GIT_WORK_TREE
    export GIT_NO_REPLACE_OBJECTS=1
    git -C "$repo_dir" "$@"
  )
}

if ! command -v git >/dev/null 2>&1; then
  source_state="git-unavailable"
elif [[ -e "${repo_dir}/.git" || -L "${repo_dir}/.git" ]]; then
  if ! repository_root="$(source_git rev-parse --show-toplevel 2>/dev/null)"; then
    echo "Unable to inspect Git metadata in ${repo_dir}. Installation stopped before replacing the active Skill." >&2
    exit 1
  fi
  repository_root_physical="$(cd -- "$repository_root" && pwd -P)"
  if [[ "$repository_root_physical" != "$repo_dir" ]]; then
    echo "Unexpected Git repository root: ${repository_root}. Installation stopped before replacing the active Skill." >&2
    exit 1
  fi
  if source_oid="$(source_git rev-parse --verify 'HEAD^{commit}' 2>/dev/null)"; then
    if [[ ! "$source_oid" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
      echo "Git returned an unsupported commit ID: ${source_oid}" >&2
      exit 1
    fi
    source_state="head"
  elif source_git symbolic-ref -q HEAD >/dev/null 2>&1; then
    source_state="unborn"
  else
    echo "Git metadata exists, but HEAD is not a readable commit. Installation stopped before replacing the active Skill." >&2
    exit 1
  fi
fi

arguments=(
  "$orchestrator"
  install
  "$source_dir"
  "$repo_dir"
  "$agents_root"
  "$skill_name"
  --source-state "$source_state"
  --scope "$scope"
  --agent "$agent"
)
if [[ -n "$source_oid" ]]; then
  arguments+=(--oid "$source_oid")
fi
if [[ "$link_mode" == "true" ]]; then
  arguments+=(--link)
fi
if [[ "$force" == "true" ]]; then
  arguments+=(--force)
fi

exec python3 "${arguments[@]}"
