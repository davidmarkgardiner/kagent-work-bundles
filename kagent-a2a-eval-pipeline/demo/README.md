# Live demo

`run-demo.sh` shows each product on a real cluster: lights, a healthy agent, a rogue agent blocked at the gateway, and a broken agent fixed by switching to a fallback model. Full walkthrough, setup and what it proves: `../docs/demo.md`.

```sh
cp demo.env.example demo.env      # fill it: explicit context, URLs, caller identity, fallback
./run-demo.sh forward             # lab port-forwards
./run-demo.sh all                 # or: lights | healthy | rogue | release | broken | reset
```
