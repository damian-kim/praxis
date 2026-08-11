# CI evaluation

Start the local Praxis API and worker with `npm run dev`, then run a paired experiment from another PowerShell window:

```powershell
praxis evaluate `
  --candidate python:my_agent.policy:Policy `
  --baseline baseline_safe `
  --engine mujoco_v1 `
  --seeds 1..10 `
  --json artifacts/experiment.json `
  --csv artifacts/per-seed.csv `
  --junit artifacts/junit.xml
```

Seeds accept comma-separated integers, inclusive ranges, or both, such as `1..5,10,20..22`. Use `--no-wait` to create the durable experiment without polling.

The command returns:

- `0` when the complete experiment passes every gate.
- `1` when it completes and at least one gate fails.
- `2` for API, polling, argument, or export errors.

Run `praxis evaluate --help` for gate overrides and API options. The generated JSON preserves the complete experiment contract, CSV is one row per paired seed, and JUnit can be published by common CI systems.
