# Production deployment

The production service is a Render Docker web service linked to `main`.
The image applies the idempotent SQL files in `database/migrations/` before
starting Uvicorn, so a deploy also applies schema changes without a separate
manual migration step. The service must have a reachable PostgreSQL
`DATABASE_URL`.

## Initial Render setup (one time)

1. Create a Render Web Service for this repository, runtime **Docker**,
   Dockerfile `./Dockerfile`, branch `main`.
2. Set the health check path to `/health`.
3. Configure the production `DATABASE_URL`, usage limits, and other required
   environment variables from `.env.example` in Render. Set `APP_ENV=production`
   and a private `INSPECTION_API_KEY`; optionally constrain identities with
   `AUTHORIZED_USER_IDS`. For model integration, keep `GEMINI_ENABLED=false`
   unless a valid `GEMINI_API_KEY` is configured.
4. In the service's **Settings → Auto-Deploy**, select **Off**. GitHub Actions
   is the only deploy trigger; leaving Render auto-deploy on causes duplicate
   builds/deploys.
5. In **Settings → Deploy Hook**, create/copy the hook URL. Add it as the GitHub
   Actions repository secret `RENDER_DEPLOY_HOOK_URL`. The URL is a secret and
   must not be added to files, logs, or command output.
6. Confirm the configured service URL is
   `https://uborochka-xd8j.onrender.com` or update the health-check URL in
   `.github/workflows/deploy.yml` if the service name changes.

The Render deploy-hook documentation confirms that a hook accepts a `ref`
query parameter for a specific commit when the service deploys from a Git
repository: <https://render.com/docs/deploy-hooks>. The rollback script uses
this documented behavior.

## Автодеплой

`.github/workflows/deploy.yml` runs only on pushes to `main`. It installs the
pinned requirements, runs Ruff, Black, and pytest, then builds the Docker
image. Only after those jobs succeed does it call the Render Deploy Hook.
Finally, it polls `/health` up to 30 times with a 10-second curl timeout and
10-second intervals (about ten minutes total), which allows a free instance
to wake up. Each successful response must report the deployed commit in
`commit`, supplied by Render's `RENDER_GIT_COMMIT`; this prevents an old,
already-healthy deployment from passing the smoke check. A missing or
mismatched commit after the retries fails the workflow. The hook response body
is discarded so the secret URL is not printed.

Required repository secret:

| Secret | Purpose |
|---|---|
| `RENDER_DEPLOY_HOOK_URL` | Render Deploy Hook URL used by deploy and rollback workflows |

Render's **Auto-Deploy must be Off**, as described in the initial setup, to
avoid a second deploy triggered directly by the same `main` push.

## Откат

Local one-command rollback to a commit known to exist in the linked repository:

```bash
RENDER_DEPLOY_HOOK_URL='(set privately in your shell)' \
  scripts/rollback.sh <git-sha>
```

Or open **Actions → Roll back production → Run workflow** and enter the SHA.
The SHA is validated and sent as the URL-encoded `ref` query parameter. The
script discards the hook response body and prints no hook URL. The rollback
workflow waits until `/health` reports a commit beginning with the requested
SHA; if the SHA never becomes healthy, the workflow fails.

**Не проверено, нужна проверка человеком:** Render secrets/service settings,
live production deployment, and an actual rollback rehearsal are not available
from this repository environment. Verify them before relying on the procedure.
