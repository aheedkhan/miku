---
name: teaching-lab
description: >-
  Teaching / spoon-feed mode — explain, one command at a time, wait for output.
  Use when the user says spoon-feed, hold my hand, teach me, or wants a small lab.
---

# Teaching lab (+ spoon-feed)

## Modes
| User signal | Behavior |
|-------------|----------|
| `spoon-feed` / `hold my hand` / `step by step` | **One** action per turn; exact copy-paste command; wait for their paste-back |
| `teach me` / default teaching | Concept → demo → short exercise → debrief |
| `just do it` | You run tools; still explain briefly after |

## Spoon-feed pattern (mandatory when asked)
1. **Goal this step** — one sentence  
2. **Why** — one sentence  
3. **Do this** — fenced command block only (or one GUI click path)  
4. **What to paste back** — e.g. exit code + stderr, or Defender Event ID  
5. **Stop** — do not run ahead until they reply  

If they paste an error: classify → next single fix command (skills `lab-build` / `debug-triage` / `lab-iterate`).

## Normal teaching pattern
1. **Goal** — what they’ll be able to do  
2. **Concept** — ≤10 lines  
3. **Demo** — in *their* env (WSL paths, their VM)  
4. **Lab** — 5–15 min, clear success check  
5. **Debrief** — what to watch next; optional stretch  

## WSL → Windows labs
- Daily workflow: `docs/wsl-windows-lab-guide.md`
- **Full Win11 env A→Z:** `docs/windows11-lab-setup-atoz.md` (letter by letter)
- PE loop: `wsl-windows-exe` + `lab-iterate`

## Rules
- Don’t solve the entire lab unless they ask (`just do it`)  
- Security labs stay in VMs / own repos  
- Never skip waiting in spoon-feed mode  
- Adjust depth to their comfort; offer “want the why or just the command?”
