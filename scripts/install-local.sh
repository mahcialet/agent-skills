#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 <skill-name> [--scope user|project] [--agent codex|github-copilot] [--link] [--force]" >&2
}

if [[ $# -lt 1 ]]; then
  usage
  exit 2
fi

skill_name="$1"
shift
scope="project"
agent="codex"
link_mode="false"
force="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      scope="$2"
      shift 2
      ;;
    --agent)
      [[ $# -ge 2 ]] || { usage; exit 2; }
      agent="$2"
      shift 2
      ;;
    --link) link_mode="true"; shift ;;
    --force) force="true"; shift ;;
    *) usage; exit 2 ;;
  esac
done

[[ "$skill_name" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]] || { echo "Invalid skill name" >&2; exit 2; }
[[ "$scope" == "user" || "$scope" == "project" ]] || { echo "Invalid scope" >&2; exit 2; }
[[ "$agent" == "codex" || "$agent" == "github-copilot" ]] || { echo "Invalid agent" >&2; exit 2; }

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"
source_dir="${repo_dir}/skills/${skill_name}"
[[ -f "${source_dir}/SKILL.md" ]] || { echo "Unknown skill: ${skill_name}" >&2; exit 1; }

if [[ "$scope" == "project" ]]; then
  target_root="${repo_dir}/.agents/skills"
else
  # ~/.agents/skills is the common user location supported by both initial hosts.
  target_root="${HOME}/.agents/skills"
fi
destination="${target_root}/${skill_name}"

if [[ -e "$destination" || -L "$destination" ]]; then
  if [[ "$force" != "true" ]]; then
    echo "Destination exists: ${destination}; pass --force to replace it safely" >&2
    exit 1
  fi
  backup="${destination}.backup.$(date +%Y%m%d%H%M%S)"
  mv -- "$destination" "$backup"
  echo "Moved previous installation to ${backup}"
fi

mkdir -p -- "$target_root"
if [[ "$link_mode" == "true" ]]; then
  ln -s -- "$source_dir" "$destination"
  echo "Linked ${skill_name} for ${agent} (${scope}) at ${destination}"
else
  cp -R -- "$source_dir" "$destination"
  echo "Copied ${skill_name} for ${agent} (${scope}) to ${destination}"
fi
