# Run it

Offline, no cluster needed:

```sh
pip install -r requirements.txt
python -m unittest discover -s tests          # 216 tests
python tests/lint_cases.py cases
./verify-bundle.sh                            # all offline checks plus a safety scan
```

Live (read `HUMAN-PREREQUISITES.md` first; every value below is a placeholder):

```sh
export AGW_BASE_URL=https://{{AGW_HOST}} AGW_TOKEN={{TOKEN}} EVAL_AGENT={{AGENT}} EVAL_NAMESPACE=eval-local EVAL_MODEL_LABEL={{MODEL}}
kubectl create ns $EVAL_NAMESPACE && kubectl -n $EVAL_NAMESPACE apply -f fixtures/cluster/
python a2a_capture.py --cases-dir cases --tier smoke --repeat 1 --out out/smoke
python score_and_gate.py --capture-dirs out/smoke --repeat 1 --out out/smoke/report
python a2a_capture.py --cases-dir cases --tier full --repeat 3 --out out/full
python score_and_gate.py --capture-dirs out/full --repeat 3 --contracts-dir completion-gate/contracts --out out/full/report
```

Warden on one real run:

```sh
python verify_completion.py --contract completion-gate/contracts/sentinel-investigator.yaml \
  --receipt response.json --agent-crd agent.yaml          # route says what the receiver does
python verify_completion.py --contract ... --receipt response.json --readback issue.json   # after the receiver wrote the issue
```

On 1.x set `AGW_A2A_URL_TEMPLATE` to the `/agents/{agent_ns}/{agent}` path and read [the version differences](kagent-versions.md): the request shape changed.
Raw receipts hold prompts and answers: keep `out/` out of git.
