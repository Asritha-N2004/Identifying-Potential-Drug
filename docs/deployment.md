# Deployment and live database verification

On 8 November 2026 the application was verified with native PostgreSQL 16.15 and Neo4j Community 5.26.33 on Windows. All three live integration tests passed, and the complete backend suite passed with both integrations enabled. A real Uvicorn HTTP analysis using the real biomedical snapshot and both databases completed all nine agents. Stored records survived application and database process restarts. See [measured deployment results](deployment_results.md).

Docker container startup is still pending. This Windows 11 Home host has Docker CLI but no Docker engine or installed WSL. Compose configuration validation succeeds; `compose up --build --detach` fails because `//./pipe/docker_engine` does not exist. That is an engine prerequisite failure, not a successful container build or runtime test. Installing WSL/Docker Desktop may require a Windows restart; no restart was performed.

## Reproduce native Windows integration

The scripts download official runtime archives into ignored workspace storage. They do not install Windows services or change PATH. Neo4j and PostgreSQL bind only to localhost on dedicated test ports. Generated credentials are saved under `runtime/local-databases/credentials.json` and are never printed by the runners. Keep this ignored file private.

```powershell
python scripts/download_integration_tools.py
python -m pip install --target runtime/integration-python -r backend/requirements-integration.txt
python scripts/local_databases.py start
python scripts/run_database_tests.py
python scripts/run_database_tests.py --all
python scripts/verify_live_databases.py
python scripts/verify_database_restart.py
```

The native helper uses PostgreSQL at `127.0.0.1:55432`, database `research_integration`, user `research`; Neo4j uses Bolt `127.0.0.1:17687` and HTTP `127.0.0.1:17474`, user `neo4j`. It reads the generated passwords internally. `verify_live_databases.py` starts a temporary Uvicorn server on port 18000, verifies actual HTTP requests and persisted results after restart, then stops that temporary server. The database processes remain available for further work.

Stop only the owned test servers with:

```powershell
python scripts/local_databases.py stop
```

PostgreSQL stops with `pg_ctl -m fast`; the known Neo4j console process tree is terminated after validating its PID command line. Neo4j transaction-log recovery was verified on restart. No database directories are removed. Test cases use unique namespaces and clean up only their own entities, edges and jobs. Use dedicated test databases for external URLs: the application restart test includes normal startup job recovery.

For independently provisioned services, install the integration drivers and set `TEST_POSTGRES_URL`, `TEST_NEO4J_URI`, `TEST_NEO4J_USERNAME` and `TEST_NEO4J_PASSWORD`, then run `python -m pytest backend/tests/test_external_databases.py -q`. The local runner supplies its own generated credentials; it intentionally does not target an arbitrary production database.

## Docker deployment once an engine is available

Install and start a Linux-container Docker engine. On this Windows Home host, see [Docker Desktop Windows prerequisites](https://docs.docker.com/desktop/setup/install/windows-install/). WSL configuration and any host reboot are separate from the verified native database processes.

```powershell
Copy-Item .env.example .env
# Configure deployment passwords and ADMIN_API_KEY in .env.
docker compose config --quiet
docker compose up --build --detach --wait
```

Open the dashboard at [localhost:8080](http://localhost:8080). The backend binds the host API to `127.0.0.1:8000`. Database ports are not published. PostgreSQL, Neo4j, model checkpoints, runtime jobs and acquired source snapshots have persistent volumes. Fresh deployments start from the included synthetic dataset; use Data sources to ingest and activate a real graph, then train a matching model.

The checked-in frontend Dockerfile now installs from `pnpm-lock.yaml` with pinned pnpm 11.25.0. The backend installs the observed core dependency pins and the tested database-driver pins. Those are direct dependency pins, not a complete transitive, platform-independent lock. Linux image builds remain unverified on this engine-less host. Use URI-safe database password characters in this Compose DSN configuration; for native DSNs, URL-encode reserved password characters.

The Neo4j health check now authenticates over Bolt with Cypher `RETURN 1`, rather than assuming `wget` exists or treating HTTP availability as authenticated database readiness. A startup grace period and bounded heap/page-cache settings are configured.

The registry-verified image pins are `postgres:16.15-alpine` and `neo4j:5.26.32-community`. The native Windows Neo4j tests used 5.26.33; its matching Docker tag was not published when checked. An initial 5.26.33 image pin failed manifest lookup and was corrected. Registry availability verifies image metadata, not container behavior or parity with the native 5.26.33 test run.

## Isolated container tests and deployment verifier

```powershell
New-Item -ItemType Directory -Force runtime/container-tests
docker compose -p atlas-integration -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
docker compose -p atlas-integration -f docker-compose.test.yml down
```

This separate Compose project uses dedicated test PostgreSQL/Neo4j services, temporary database filesystems and no published database ports or production volumes. It writes JUnit output to `runtime/container-tests/container-tests.xml`. These container tests are implemented but have not run here.

Alternatively, `python scripts/verify_docker_deployment.py` validates both Compose files, checks engine availability, deploys the main stack when possible, verifies the dashboard/proxied health endpoint, and runs the isolated container suite. It leaves the main application running and stops the temporary test project. Its machine-readable report explicitly distinguishes configuration validation, engine availability and actual container execution. If the Compose plugin is missing, it can use the downloaded standalone executable under `runtime/integration-tools`.

The normal shutdown is `docker compose down`; named volumes remain. Do not remove volumes containing wanted jobs or source snapshots. PostgreSQL migrations, deletion reconciliation between graph versions, distributed transactions and multi-user authorization remain outside this verification.

## Verified runtime fixes

The Windows launcher redirects startup output to files because inherited server pipe handles can otherwise keep `pg_ctl` startup waiting for EOF. This host also rejects Java AF_UNIX selector connections. The local Neo4j configuration uses an unavailable relative Unix-socket directory to invoke OpenJDK's existing TCP-loopback fallback. No Java binaries are modified; the setting is confined to the owned native test runtime. This workaround is not added to Linux container configuration. Reference: [OpenJDK Windows Pipe implementation](https://github.com/openjdk/jdk21u/blob/master/src/java.base/windows/classes/sun/nio/ch/PipeImpl.java).
