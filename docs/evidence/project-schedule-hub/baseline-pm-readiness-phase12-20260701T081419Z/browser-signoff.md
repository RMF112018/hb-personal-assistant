# Browser Sign-Off

**STAMP:** 20260701T081419Z  
**Proof type:** live browser (Playwright Chromium with loaded-state gates)  
**Method:** Playwright — see `screenshot-wait-gates.md` and `screenshot-proof.json`

## Stack

| Service | URL | Status |
|---------|-----|--------|
| Backend | http://127.0.0.1:8000 | 200 |
| Frontend | http://127.0.0.1:5173 | 200 |
| DB | tropical named baselines (TWNU07/18/14) | real local DB |

## Post-fix walkthrough (re-captured)

| Step | Result | Screenshot | Loaded proof |
|------|--------|------------|--------------|
| Baseline Anchors — three selected Tropical baselines | PASS | `post-fix/01-schedule-hub-baseline-anchors.png` | TWNU07/18/14 visible in anchor cards |
| Schedule Controls — CCB + comparison context | PASS | `post-fix/02-controls-named-baseline.png` | `Comparing against Current Contract Baseline · 2025-08-07 · TWNU07.zip` |
| Named Workbench — read-only banner + review cues | PASS | `post-fix/03-workbench-named-baseline.png` | Banner + `Candidate change driver` cards |
| Driver detail FAB/DEL-10 | PASS | `post-fix/04-driver-detail-slash-activity.png` | Activity H3 + `Side-by-Side Movement` |
| Back navigation preserves context | PASS | `post-fix/05-back-to-workbench.png` | URL `…/workbench?comparison_basis=current_contract_baseline&as_of=2026-07-01` |
| Missing baseline state | PASS (fixture) | `post-fix/06-missing-baseline-controls.png` | Mocked controls API; actionable copy |

## Sign-off answers

| Question | Answer |
|----------|--------|
| PM workflow understandable? | Yes |
| Selected named baselines visible? | Yes — three anchor cards with date · zip labels |
| Active comparison basis clear? | Yes — context line on controls, workbench, driver |
| Read-only named preview explained? | Yes — amber banner |
| Links preserve context? | Yes — verified on shot 05 |
| Raw IDs demoted? | Yes — activity name is primary on driver |
| Advisory posture visible? | Yes |
| Before broader PM rollout? | Named-baseline disposition persistence |

## Prior capture correction

Initial post-fix screenshots were captured before loaded-state gates were enforced. This package supersedes them with explicit wait gates; no loading-state screenshots are included.
