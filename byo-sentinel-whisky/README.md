# BYO Sentinel · Whisky work bundle

Copy this folder into the receiving repository. It contains the team launch, a browser rehearsal with sample data, and the workplace onboarding and acceptance handoff.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m mkdocs build --strict
```

Open `site/index.html` for the documentation or `site/sentinel/index.html` for the browser launch. Keep the generated site together when moving the preview so its relative links and assets resolve.

The launch, onboarding and rehearsal files are a dated portable copy from `work-agent-bundles/agent-platform-mkdocs/docs/` in the source repository. Refresh those files from the maintained handbook when updating this bundle. The implementation handoff belongs to this bundle.

The browser rehearsal uses synthetic data. Workplace implementation starts with the existing scanner job, KRO contract and Whisky application. The included Dramface bottle photo is credited in the rehearsal. Use the app's approved bottle asset for the workplace presentation.
