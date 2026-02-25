# Architecture Review (v0.3.0)

## Major findings

### High

1. Runtime build dependency still happens in production path.
- `xcaddy` + `go` build at startup is operationally heavy.
- Risk: slower startup, external network dependency on module downloads.

2. Dashboard service checks are browser best-effort only.
- `no-cors` fetch cannot provide definitive HTTP/TLS semantics.
- Displayed "cert check" should be treated as reachability hint, not cryptographic validation.

3. Update check depends on GitHub API availability/rate limits.
- If offline/rate-limited, recommendation becomes unknown.

### Medium

4. `dnsmasq` is a separate service consuming host port 53.
- Can conflict with host/local DNS daemons.
- Requires explicit operational ownership.

5. Caddy version parsing is semver regex-based.
- Non-standard version output can reduce recommendation accuracy.

### Low

6. Local override file (`Caddyfile.overwrite`) bypasses generated config.
- Useful for emergency overrides, but can create drift if left in place.

## Recommended next hardening steps

1. Optionally prebuild Caddy binary at image build for pinned versions.
2. Add a server-side health endpoint aggregator for authoritative checks.
3. Add integration test that boots compose and validates generated artifacts.
4. Add warning banner in dashboard when `Caddyfile.overwrite` is active.
