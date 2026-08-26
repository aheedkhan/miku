# Running Hermes across Qubes VMs

A natural Qubes layout for Hermes is **Ollama in its own qube** (so a GPU passthrough, a large
model cache, and a big attack surface of C++ inference code stay quarantined from anything
else) and **Hermes running in whatever client qube you're actually working in** — your Android
RE qube, your CTF qube, your dev qube — talking to that Ollama qube over the network instead of
running the model locally in each one.

This document is the concrete, already-decided plan for that layout. It assumes you have a
qube dedicated to Ollama (call it `ollama-vm` below — substitute your real qube name) and one or
more client qubes that should be allowed to reach it.

## 1. Bind Ollama to more than localhost

By default Ollama only listens on `127.0.0.1`, which is useless across a VM boundary. Override
it with a systemd drop-in inside `ollama-vm`:

```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d
sudo tee /etc/systemd/system/ollama.service.d/override.conf >/dev/null <<'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
EOF

sudo systemctl daemon-reload
sudo systemctl restart ollama
```

`0.0.0.0:11434` here just means "listen on every interface *inside this qube*" — it does not by
itself expose Ollama to anything outside the qube. That's governed entirely by Qubes networking,
covered next.

## 2. The Qubes networking reality: this is not a firewall-rules problem

The instinct is to reach for `qvm-firewall` to lock this down. That's the wrong tool here:
**`qvm-firewall` governs outbound traffic only** — rules attached to a qube control what *that
qube* may connect out to, not who may connect *into* it. It has nothing to say about inbound
connections from a sibling qube.

The other relevant fact: **sibling qubes have no route to each other by default.** Two AppVMs
sitting behind the same NetVM (e.g. both behind `sys-firewall`) cannot reach each other's IP
addresses at all under a stock Qubes network topology — traffic from an AppVM only ever goes
"up" toward its NetVM, never sideways to another AppVM. So without doing anything else,
`client-vm` already cannot reach `ollama-vm`, firewall rules or not.

### The correct pattern: make `ollama-vm` a NetVM for its clients

The way to grant exactly the client qubes you choose a route to `ordinary-vm`, and *only* those,
is to make `ollama-vm` itself act as a NetVM and chain your client qubes behind it:

```bash
# Let ollama-vm act as a NetVM for other qubes
qvm-prefs ollama-vm provides_network true

# Point each client qube's network at ollama-vm instead of sys-firewall
qvm-prefs client-vm netvm ollama-vm
```

(The GUI equivalent: Qube Settings → Advanced → "Provides network" on `ollama-vm`, then set
`client-vm`'s NetVM to `ollama-vm` in its own settings.)

This chaining **is** the access control: only a qube explicitly set to route through
`ollama-vm` gets a network path to it at all. A qube you never re-point stays exactly as
isolated from `ollama-vm` as it was before — there's no separate ACL to configure, the
topology itself is the ACL. Repeat the `netvm` step for every client qube that should reach
Ollama; leave everything else alone.

### Optional belt-and-suspenders: nftables on the Ollama qube

Chaining is sufficient on its own, but if you want defense in depth inside `ollama-vm` itself,
add an explicit `nftables` rule restricting port 11434 to the expected Qubes-internal address
range (`10.137.x.x`) rather than trusting "nothing else can route here anyway":

```bash
sudo nft add rule inet filter input tcp dport 11434 ip saddr != 10.137.0.0/16 drop
```

Adjust the CIDR to match what your client qubes actually get assigned (`qvm-prefs client-vm ip`
will tell you). This is genuinely optional — it protects you if the topology ever changes out
from under you (a qube's NetVM gets reassigned by mistake, etc.) — not something you need to get
right for the base setup to be secure.

## 3. Find the Ollama qube's address for the client's config

Once `ollama-vm` is providing network to `client-vm`, get its internal IP:

```bash
qvm-prefs ollama-vm ip
```

Put that address in the client qube's Hermes config — either `.env`:

```bash
OLLAMA_HOST=http://10.137.0.15:11434
```

or the `ollama_host:` key in `~/.config/hermes/config.yaml` (the `.env`/real-env-var value wins
if both are set — see the comments in `config.example.yaml`).

## 4. Isolating the Ollama qube between uses

`ollama-vm` needs a real NetVM (e.g. `sys-firewall`) the *first* time you `ollama pull` a model —
pulling requires actual internet egress. Once your models are pulled, you can cut `ollama-vm`
off from the outside internet entirely while still serving your client qubes, since the
provides-network chain to clients is independent of `ollama-vm`'s own upstream NetVM:

```bash
# Fully isolate ollama-vm from the outside world
qvm-prefs ollama-vm netvm ''
```

Flip it back to `sys-firewall` (or whatever) temporarily whenever you need to pull new/updated
models, then set it back to `''` afterward.

**Known edge case — verify, don't trust the UI:** Qubes 4.3 has a known issue
([QubesOS/qubes-issues#10459](https://github.com/QubesOS/qubes-issues/issues/10459)) where
setting `netvm` to `''` does not always fully cut connectivity for every qube type — the Qube
Manager can show "no NetVM" while some path still lets traffic out. Don't take the UI's word for
it. After isolating, actually test it from inside `ollama-vm`:

```bash
curl -m 3 -sf https://1.1.1.1 && echo "STILL ONLINE — isolation did not take" || echo "isolated, good"
```

If it reports still-online, check for a stale qrexec network policy or a leftover `sys-net`-style
service qube in the chain before trusting the isolation.

## 5. Realistic performance expectations

GPU passthrough to a single Qubes VM is possible but fragile and genuinely advanced — VFIO IOMMU
group splitting, a device you can no longer use from dom0 or any other qube while it's attached,
and driver/firmware quirks that vary by GPU vendor and generation. Unless you've already got
passthrough working and tested, assume `ollama-vm` will run models **CPU-only**, which is
materially slower than a bare-metal box with a GPU. Size your model choice in `config.yaml`
accordingly (favor `fast`-role smaller models for interactive use; reserve larger ones for
work where you can wait).
