# Private GitLab Feedback Loop Prompt

Deploy and prove the bounded GitLab feedback loop only in the approved private
environment. Use an internal ingress or VirtualService, not a public tunnel.
Do not expose other routes, commit credentials, grant agent write tools, or
claim success until reject, accept, replay, and one Issue-response tests have
all been captured.
