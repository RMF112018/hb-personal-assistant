# Evidence Manifest — <candidate-name>

Candidate: `<candidate-slug>`  
Prompt: `<prompt-file>`  
Branch: `<branch>`  
Baseline SHA: `<baseline-sha>`  
Candidate start SHA: `<start-sha>`  
Candidate end SHA: `<end-sha>`  
Commit: `<commit-sha-or-none>`  
Generated: `<timestamp>`

## Scope

Describe what was implemented and what was intentionally not implemented.

## Repo state

Include:

```bash
git rev-parse --abbrev-ref HEAD
git rev-parse HEAD
git status --short
git diff --stat HEAD~1..HEAD
```

## Final output artifacts

Link or list the final output artifacts generated for this candidate. Include paths and a one-line description of what each artifact represents.

## Validation commands

List every validation command run.

## Validation results

Summarize pass/fail results. If broad tests fail for pre-existing reasons, explain why the candidate is still considered locally validated.

## Safety checks

Confirm:

- no raw bodies
- no raw model prompts
- no raw model responses
- no signed/download URLs
- no join links
- no tokens/secrets
- no external writeback
- no cloud LLM fallback
- no unexpected production DB mutation

## Limitations

List any remaining limitations, deferred work, or data-blocked paths.

## Merge readiness

State whether this candidate is merge-ready by itself.
