#!/usr/bin/env bash
set -euo pipefail

if (( $# < 1 )); then
  printf '用法: %s <domain> [profile.yaml ...]\n' "$(basename "$0")" >&2
  exit 2
fi

domain="${1#http://}"
domain="${domain#https://}"
domain="${domain%%/*}"
shift

fail=0
printf 'domain=%s\n' "$domain"

dns="$(dig +short "$domain" A 2>/dev/null | awk '/^[0-9.]+$/ {print; exit}')"
if [[ -z "$dns" ]]; then
  printf 'dns=missing\n'
  fail=1
elif [[ "$dns" == 198.18.* || "$dns" == 198.19.* ]]; then
  printf 'dns=%s fake_ip=true\n' "$dns"
  fail=1
else
  printf 'dns=%s fake_ip=false\n' "$dns"
fi

result="$(curl -sS -o /dev/null \
  -w 'http=%{http_code} remote=%{remote_ip} ssl=%{ssl_verify_result} time=%{time_total}' \
  --max-time 20 "https://$domain/" 2>&1)" || fail=1
printf '%s\n' "$result"

for config in "$@"; do
  if [[ ! -f "$config" ]]; then
    printf 'config=%s missing=true\n' "$config"
    fail=1
    continue
  fi
  filter_ref=false
  direct_ref=false
  grep -Fq -- "$domain" "$config" && filter_ref=true
  grep -Fq -- "DOMAIN-SUFFIX,$domain,DIRECT" "$config" && direct_ref=true
  printf 'config=%s contains_domain=%s contains_direct=%s\n' \
    "$config" "$filter_ref" "$direct_ref"
done

exit "$fail"
