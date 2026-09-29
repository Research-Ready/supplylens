# Scania demo — status (2026-08-24)

## Goal
Seed and view the Scania supply-chain demo (per `CLAUDE.md` / `scripts/seed_scania.sh`).

## Steps taken (on chris's laptop)

1. Opened the local artifact that already existed: `graphify-out/graph.html`
   (button demo graph — worked fine, no infra needed).
2. Checked `scripts/seed_scania.sh` — it uploads
   `example_outputs/sample_graph.cypher` to Neo4j on CT114 (`10.0.1.114`) via
   bastion `10.0.0.16`, reading the Neo4j password out of `passwords.kdbx`
   (KeePass, master password `SupplyChainBaby100!`, entry titled "Neo4j").
3. Confirmed `10.0.0.16:22` was unreachable with no VPN up.
4. Brought up VPN via
   `nmcli connection up "fw1dc1-TCP4-443-chris-config"` — activated
   successfully, `tun0` got `10.0.201.3/24`, routing table correctly picked up
   `10.0.0.0/8 via 10.0.201.1 dev tun0`.
5. Re-tested: `10.0.0.16` and `10.0.1.114` still don't respond to TCP:22 or
   ICMP ping even through the tunnel — VPN itself is fine, but the far end
   (bastion / Proxmox cluster) isn't answering.

## Not yet run

- `bash scripts/seed_scania.sh` — blocked on the above.
- Neo4j Browser / NeoDash SSH tunnel + `xdg-open` steps from `COMMANDS.md`.

## Other discrepancies noticed in the repo (worth checking whenever)

- This directory is not a git repo (`git status` → "not a git repository"),
  yet `PLAN.md` cites specific commits (e.g. `b2c0978`) for dashboards it
  marks "BUILT" — none of those HTML files (supplier deep dive, carbon
  tracker, dual sourcing, 3D graph, etc.) exist anywhere in the repo. Only
  `graphify-out/graph.html` actually exists.
- `CLAUDE.md`'s pre-flight step calls `scripts/vpn-connect.sh`, which doesn't
  exist in `scripts/`.

## Next step

Once the cluster is confirmed reachable (check Proxmox host power/boot state,
or try the other VPN profile `fw1dc1-UDP4-1194-chris-config`), resume from
step 5: run `scripts/seed_scania.sh`, then the Neo4j Browser / NeoDash tunnel
+ open steps in `COMMANDS.md`.
