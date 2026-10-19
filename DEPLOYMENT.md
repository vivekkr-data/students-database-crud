# Render deployment

Live demo: https://students-database-crud.onrender.com/docs

Current deployment: free plan, Singapore, ephemeral SQLite storage, Ollama disabled. The free service has no persistent disk.

## Service settings

| Setting | Value |
|---|---|
| Repository | https://github.com/vivekkr-data/students-database-crud |
| Branch | main |
| Service type | Web Service |
| Runtime | Python 3 |
| Root directory | Repository root (blank setting) |
| Build command | python -m pip install -r students-database-crud/requirements-lock.txt |
| Start command | python -m uvicorn app.main:app --app-dir students-database-crud --host 0.0.0.0 --port $PORT |
| Platform health check | Default TCP check; /health is also available for manual verification |
| ENABLE_OLLAMA | false |
| PYTHON_VERSION | 3.12.11 |

The application directory includes `.python-version` selecting Python 3.12. Use one service instance with one Uvicorn worker for the SQLite deployment.

## Persistent SQLite deployment

A paid Render web service with a persistent disk is required to keep SQLite records across service restarts and deployments. Review current pricing before provisioning.

- Mount a persistent disk at `/var/data` (1 GB is sufficient for this demonstration).
- Set `STUDENT_DB_PATH=/var/data/students.db`.
- The app creates its schema on startup; no database server or migration command is needed.
- Do not put database initialization in the build step: the disk is only available at runtime.

## Free demonstration alternative

Free Render web services do not support persistent disks. For a temporary demo, omit the disk and leave `STUDENT_DB_PATH` unset. The API runs, but records may be lost on restart or redeployment. This alternative does not provide durable cloud persistence and should not be presented as doing so.

## Verify after deployment

1. Wait until the service is live; use the actual URL assigned by Render.
2. Open `/health` and check for `status: ok`.
3. Open `/docs`, create a fictional student, retrieve it, update it and delete it.
4. For the persistent option, create another test record, restart the service and confirm the record remains.
5. Submit the assigned HTTPS URL ending in `/docs` as the Live Link. Submit the GitHub repository URL separately.

To load fictional records from your local project environment after deployment:

```text
python -m scripts.seed --url https://students-database-crud.onrender.com
```

Run the sample loader from the inner project directory with its dependencies installed.

This public demonstration has no authentication. Use fictional data only. Ollama is disabled on the hosted service; core CRUD and the built-in database question responses work without a model.

References: https://render.com/docs/deploy-fastapi and https://render.com/docs/disks
