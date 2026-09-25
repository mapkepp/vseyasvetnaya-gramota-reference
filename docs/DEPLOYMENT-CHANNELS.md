# Deployment channels

The project uses three logical states:

- `dev` — autonomous agent development and validation.
- `main` — production source branch after verification/merge.
- `backup` — immutable recovery snapshot branch/tag strategy.

Agents must never write research results directly to production without the project's verification gate.

Recommended promotion:

`agents -> dev -> verify -> production(main) -> backup snapshot`

The backup is a recovery point, not a second development branch.
