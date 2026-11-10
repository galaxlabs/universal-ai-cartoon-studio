# Public source publication boundary

The owner explicitly requested a public GitHub repository. The local repository
already contained historical agent transcripts and operational reports, so its
private-history branch must not be uploaded wholesale to the public remote.

## Source snapshot

- Local development history remains on local `main`, unchanged.
- `public-source` is a separate source snapshot branch. Its initial commit has
  no parents and therefore does not expose earlier private-history commits.
- Only `public-source` is pushed to remote `main`. Do not push `--all`, mirror,
  or force-push the local development branch to the public repository.
- Future public snapshots should use the previous `public-source` commit as
  their parent so public history remains a normal fast-forward chain.

## Excluded from the public tree

- `ref/`: local agent memory and transcripts.
- `.agents/`: local installed skill copies, not required to run the manager.
- `storage/80_REPORTS/` operational traces, apart from an empty `.gitkeep`.
- Environments, `.env` secrets, databases, backups, `.blend` and other production
  binaries, using the existing ignore rules and explicit publication review.

Files remain on disk; exclusion does not authorize deletion of originals.
The application source, migrations, tests, dependency manifests/lock, launch/setup
files, and public documentation are included. Report-import tests generate a
synthetic fixture instead of requiring a private operational report.

GitHub Actions workflows remain included. Uploading them still requires the
GitHub OAuth `workflow` scope; this separation is for privacy, not a way around
GitHub permissions. Never remove authentication requirements or claim an upload
succeeded when GitHub rejects it.

The public `PROJECT_STATUS_UR.md` describes the implemented/planned boundaries.
Production assets, verified backups and integrations must be restored separately.
