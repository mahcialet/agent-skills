#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd -- "${script_dir}/.." && pwd)"

python3 "${script_dir}/validate_skills.py" "${repo_dir}"
python3 "${script_dir}/validate_behavior_profiles.py" "${repo_dir}"
python3 -m unittest discover \
  -s "${repo_dir}/tests" \
  -p 'test_*.py'
