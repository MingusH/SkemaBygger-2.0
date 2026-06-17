# Deploying SkemaBygger to Render

The app deploys as three pieces (all on Render's free tier):

| Piece | Render type | What it is |
|-------|-------------|-----------|
| `skemabygger-db` | Postgres | the database |
| `skemabygger-api` | Web service (Docker) | FastAPI **+ MCP server + OAuth** — the URL users point Claude Desktop at |
| `skemabygger-web` | Static site | the React management UI |

[`render.yaml`](render.yaml) is a Blueprint that creates all three.

## First deploy

1. Push this repo to GitHub (already done).
2. In Render: **New → Blueprint**, pick this repo. Render reads `render.yaml` and creates the DB, API, and static site.
3. The build runs `alembic upgrade head` on start, so the schema is created automatically.

## Fill in the URL env vars (after the first deploy)

Render assigns the `*.onrender.com` hostnames during the first deploy, so three env vars are left blank (`sync: false`) and must be set once the URLs exist. In the dashboard:

**`skemabygger-api` → Environment:**
- `PUBLIC_BASE_URL` = the API's own URL, e.g. `https://skemabygger-api.onrender.com`
- `CORS_ORIGINS` = the web URL, e.g. `https://skemabygger-web.onrender.com`

**`skemabygger-web` → Environment:**
- `VITE_API_BASE_URL` = the API URL + `/api`, e.g. `https://skemabygger-api.onrender.com/api`

Then **redeploy both services** (the static site must rebuild to bake in `VITE_API_BASE_URL`).

`SECRET_KEY` is generated automatically; `DATABASE_URL` is wired from the database.

## Create your first user

There's no public sign-up UI. Register the first user via the API, then promote to superadmin in the DB (or add school memberships):

```bash
curl -X POST https://skemabygger-api.onrender.com/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"...","full_name":"You"}'
```

## Connect Claude Desktop (OAuth)

In Claude Desktop: **Settings → Connectors → Add custom connector**, URL:

```
https://skemabygger-api.onrender.com/mcp
```

No token needed — it opens the SkemaBygger login page, you sign in, and it connects.
(Personal access tokens from the **Adgangstokens** page still work as an alternative.)

## Free-tier notes
- The API web service **sleeps after ~15 min idle** (cold start on next request). Static sites and the DB don't sleep, but free Postgres has its own retention limits — check Render's current terms.
- Schedule generation runs in-process with `SOLVER_NUM_WORKERS=1`; large solves are the most likely thing to strain the 512 MB instance.
