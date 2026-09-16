# B4 single-summary sandbox ledger

The suspended reconciler demonstrates the side-effect boundary without contacting GitLab. It turns the latest stored analysis into the stable key `cluster-health/<cluster_id>`, creates one local row, updates that same row when the source changes, and makes identical replay a no-op. A closed row returns conflict and does not create a replacement.

`external_delivery` is hard-coded to `disabled_lab_ledger`, and the CronJob is suspended. This proves aggregation and lifecycle logic only. It is not evidence of GitLab permissions, API pagination, labels, rate limits, or ambiguous-write recovery.

An authorised workplace sandbox adapter must sit after this ledger and implement exact-label, all-state, fully paginated reconciliation plus durable operation reservations. Keep it disabled until that separate acceptance run is approved.
