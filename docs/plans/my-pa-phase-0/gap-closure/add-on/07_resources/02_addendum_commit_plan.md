# Addendum Commit Plan

Recommended branch:

```bash
git checkout -b remediation/addendum-final-corrections
```

Recommended commits:

1. `fix(security): clean sensitive scanner lint violations`
2. `fix(paths): harden application support permission handling`
3. `fix(store): add db readiness checks and structured runtime errors`
4. `test(graph): rerun delegated proof after local path repair`
5. `feat(mail): add bounded body mention detection beyond preview`
6. `chore(closeout): regenerate addendum acceptance evidence`

Version recommendation:

- Keep `1.3.0` until accepted.
- If final addendum closeout is accepted, bump patch to `1.3.1`.

Rationale: this is hardening/remediation of v1.3.0, not a new product feature release.
