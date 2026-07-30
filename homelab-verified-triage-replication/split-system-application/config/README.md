# Staged policy folders

`kustomization.yaml` remains the stable two-lane deployment definition.
The three folders below are the copy source for a controlled policy promotion;
they are intentionally not Kustomize resources.

1. Start with `CONFIG_TIER1/` — system lane critical-only; application lane is
   disabled.
2. Copy `CONFIG_TIER2/` values when Tier 1 has clean Alloy queue and Kafka
   delivery evidence — both lanes critical-only.
3. Copy `CONFIG_TIER3/` values only after Tier 2 is healthy — both lanes admit
   the priority error/event set.

For each lane, swap its `alloy`, `vector`, and `argo` values together. The
namespace lists remain non-overlapping in every tier.
