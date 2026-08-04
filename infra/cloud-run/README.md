# Cloud Run API and private worker

Deploy the same backend image as two services. The API command is
`lunar-forge-web-api`; the private worker command is
`lunar-forge-web-worker`. Build from the directory containing both repositories
so `backend/Dockerfile` can install the recorded core source without modifying
it:

```powershell
docker build -f lunar-forge-web/backend/Dockerfile -t REGION-docker.pkg.dev/PROJECT/lfw/backend:CORE-eb0ddb5 .
```

The committed Knative manifests show the required service split. Supply all
database, Redis, Supabase, E2B, model-pricing, template, and service URLs as
ordinary server settings. Supply these values from Secret Manager:

- both services: `LUNAR_FORGE_WEB_WORKER_SHARED_SECRET`;
- worker only: `LUNAR_FORGE_WEB_OWNER_FUNDED_API_KEY` and
  `LUNAR_FORGE_WEB_E2B_API_KEY`;
- API and worker: Neon and Upstash credentials as required by their repositories.

Do not configure the owner-funded model secret on the API service. BYOK is not
a deployment secret and must never be configured as an environment variable.

The worker must be deployed with unauthenticated invocation disabled,
request timeout `960`, and container concurrency `1`:

```powershell
gcloud run deploy lunar-forge-web-worker --image WORKER_IMAGE --command lunar-forge-web-worker --concurrency 1 --timeout 960 --no-allow-unauthenticated --service-account WORKER_SERVICE_ACCOUNT --region REGION
gcloud run services add-iam-policy-binding lunar-forge-web-worker --member serviceAccount:API_SERVICE_ACCOUNT --role roles/run.invoker --region REGION
```

Deploy the API with its own service account. That account obtains a Google ID
token from the metadata server for the exact worker URL audience. The client
sends it in `X-Serverless-Authorization`; the separate Secret Manager value is
sent in `Authorization`. Cloud Run validates the Google token before the worker
application validates the shared secret.

Cloud Run request logs contain method/status metadata, not application request
bodies or authorization-header values. Application access logs are also
disabled for the worker, and its middleware logs neither headers nor bodies.

See [the deployed smoke procedure](../../docs/cloud-run-worker.md).
