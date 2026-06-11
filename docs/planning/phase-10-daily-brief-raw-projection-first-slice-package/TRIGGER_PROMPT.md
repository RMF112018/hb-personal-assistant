# Trigger Prompt

Use this exact prompt to launch the local code agent after copying this package into the repo:

```text
You are working in `/Users/bobbyfetting/hb-personal-assistant` on the `RMF112018/hb-personal-assistant` repository.

Execute the objective defined at:

`docs/planning/phase-10-daily-brief-raw-projection-first-slice-package/README.md`

Follow the README and every prompt file in numeric order. This is a one-shot implementation package. Modify code, tests, docs, and evidence as required. Do not mutate production DB during validation; use copied DBs only. Do not perform external writeback. Do not expose raw private content. Stop only if a stop condition in `STOP_CONDITIONS.md` is triggered.

Final response must use `FINAL_HANDOFF_TEMPLATE.md`.
```
