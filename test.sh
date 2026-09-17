#!/usr/bin/env bash

set -euo pipefail

readonly SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly SCRIPT_DIRECTORY2="$(dirname -- "${BASH_SOURCE[0]}")"

echo "$(cd -- ${SCRIPT_DIRECTORY}/../../ && pwd)"
echo "${SCRIPT_DIRECTORY2}"