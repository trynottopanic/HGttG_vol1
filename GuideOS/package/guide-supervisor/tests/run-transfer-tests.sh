#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
policy_dir=$(dirname -- "$test_dir")/src
test_output=$(mktemp -d "${TMPDIR:-/tmp}/guide-transfer-policy.XXXXXXXX")
trap 'rm -rf -- "$test_output"' EXIT HUP INT TERM
"${CC:-cc}" -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
    -I"$policy_dir" "$policy_dir/guide_resource_policy.c" \
    "$policy_dir/guide-network-plan.c" -o "$test_output/guide-network-plan"
GUIDE_NETWORK_PLANNER="$test_output/guide-network-plan" PYTHONDONTWRITEBYTECODE=1 \
    python3 "$test_dir/test_transfers.py"
GUIDE_NETWORK_PLANNER="$test_output/guide-network-plan" PYTHONDONTWRITEBYTECODE=1 \
    python3 "$test_dir/test_transfer_session.py"
