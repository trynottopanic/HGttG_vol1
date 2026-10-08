#!/bin/sh
set -eu
test_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
policy_dir=$(dirname -- "$test_dir")/src
test_output=$(mktemp -d "${TMPDIR:-/tmp}/guide-resource-policy.XXXXXXXX")
trap 'rm -rf -- "$test_output"' EXIT HUP INT TERM
"${CC:-cc}" -std=c11 -O2 -Wall -Wextra -Werror -pedantic \
    -I"$policy_dir" "$policy_dir/guide_resource_policy.c" \
    "$test_dir/test_resource_policy.c" -o "$test_output/resource-policy-test"
"$test_output/resource-policy-test"
