# Live demo

`run-demo.sh` shows each product on a real cluster: lights, a healthy agent, a rogue agent blocked at the gateway, and a broken agent fixed by switching to a fallback model. Full walkthrough, setup and what it proves: `../docs/demo.md`. A step-by-step sheet to run yourself: `../docs/walkthrough.md`.

```sh
cp demo.env.example demo.env      # fill it: explicit context, URLs, caller identity, fallback
./run-demo.sh forward             # lab port-forwards
./run-demo.sh all                 # or: lights | assay | warden | healthy | rogue | release | broken | reset
LOOKOUT_HARNESS=<harness> LOOKOUT_MODEL_CONFIG=<model-config> ./run-demo.sh lookout   # optional: a merge-request security review (mock GitLab), not part of `all`
```
