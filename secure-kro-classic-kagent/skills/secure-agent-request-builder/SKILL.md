---
name: secure-agent-request-builder
description: Turn a natural-language agent request into one ClassicSecureAgent YAML using the platform's approved model, skill and read-only tool catalog.
---

Read `../../demo/catalog.json`, `../../examples/agent-template.yaml` and the
receiving platform's resolved catalog. The bundled catalog contains adapter
examples; it is not proof that those integrations are installed at work.

Turn the user's description into a concise system prompt and select only
approved model, skill and tool IDs that satisfy it. Ask for missing task scope
only when it changes the prompt or permissions. Preserve this demo's approved
`classic-agents/demo` identity. Use `demo.kagent.dev/v1alpha1`, not a native
Agent resource or the 1.x API. Keep prompt length within 4,096 characters.

Return one customer YAML file with `modelConfig`, `systemPrompt`, `skills`
and `tools`. Keep credentials, JWTs and repository URLs out of this file.
The matching platform RGD resolves IDs and adds security resources. A
skills-enabled profile currently requires one or more approved skills; the
model-only profile uses empty skill and tool lists.

Make the prompt permit the Golden request to return exactly PONG without tools.
For a read-only agent, prohibit resource changes and fabricated tool results.
Do not silently add write-capable tools to satisfy a request to post to GitLab.
Name the missing approved operation and project scope instead. Publishing a
post or changing a backend is a separate action with its own authorization.

The requested deliverable is the YAML. Deploy it only if deployment is part
of the user's current instructions. Explain which scenario checks are needed
without describing an untested backend as working.
