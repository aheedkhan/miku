# Windows 11 lab setup (index)

**Full A→Z steps (spoon-feed this):**  
`docs/windows11-lab-setup-atoz.md`

When user says “setup Windows lab”, “from zero”, “Hyper-V”, “spoon-feed Windows”:
1. `use_skill` → `teaching-lab` + `env-bootstrap`
2. `read_file` → `docs/windows11-lab-setup-atoz.md`
3. Walk **letter by letter** (A→T), one step per turn

## Done when
- Win11 lab VM + snapshot `win11-clean`
- Guest reaches host C2 IP:8080
- Can copy `labrat.exe` in (e.g. `\\wsl$`)
- Defender status commands known
- Optional WinDbg/Procmon in guest

## After setup
Daily loop: `docs/wsl-windows-lab-guide.md` · skills `wsl-windows-exe`, `lab-iterate`, `windows-rat-dev`
