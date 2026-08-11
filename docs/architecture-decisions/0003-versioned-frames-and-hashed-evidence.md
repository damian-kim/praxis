# ADR 0003 — Version frames and hash evidence bundles

Status: accepted

## Decision

Replay frames use explicit schema version 2.0 and additive nullable telemetry fields. Local SQLite schemas migrate forward in place. Completed artifact directories contain a SHA-256 manifest covering every evidence file except the manifest itself.

## Rationale

Frame contracts will expand as simulators add joints and sensors. Additive nullable fields preserve historical replay while explicit versions let future consumers reject incompatible changes. Hash manifests provide portable integrity checks without requiring a cloud signing service during local development.

## Consequences

- Old runs return `null` for telemetry they never recorded.
- New engine adapters must populate physically meaningful fields or leave them null.
- Hash validity proves artifact integrity, not scientific validity; calibration and engine capability metadata remain separate concerns.
- A future hosted product can sign the manifest without changing the bundle layout.

