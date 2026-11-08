# Deployment verification — 8 November 2026

Live database integration is verified on native Windows processes. Docker configuration validation is verified; Docker image builds and container execution are not verified because this host has no engine.

| Check | Observed result |
|---|---|
| PostgreSQL | PostgreSQL 16.15, compiled by Visual C++ build 1944, 64-bit |
| Neo4j | 5.26.33 community |
| Database drivers | psycopg 3.2.10; neo4j 5.28.2 |
| Live integration suite | 3 passed, 0 failed, 0 skipped |
| Full backend suite with live databases | 24 passed, 0 failed, 0 skipped |
| Real HTTP workflow | passed; 1054 nodes, 1639 edges, 9 agents, 10 returned hypotheses |
| Application restart persistence | True |
| PostgreSQL process restart persistence | True |
| Neo4j process restart persistence | True |
| Deployment Compose validation | True |
| Test Compose validation | True |
| Docker engine accessible | False |
| Containers started | False |
| Container integration tests | not_run |
| postgres image registry Linux/amd64 manifest | True; metadata verification only |
| neo4j image registry Linux/amd64 manifest | True; metadata verification only |

The three integration tests verify idempotent graph seeding, complete edge JSON/provenance and Unicode round trips, SQL job/log persistence, nine-stage application execution using both services, and restoration after application restart. Every test uses its own unique namespace. Dedicated test records are cleaned up without deleting unrelated data.

The live HTTP verification used graph `424006a5efc2df196f73f0afb74a7db706dc9d4019a2324151ef6cd33cba9f38` and disease `MONDO_0008383`. It verified dashboard HTTP delivery, checkpoint reevaluation, a completed research analysis and saved results after server restart. This verifies integration and persistence, not clinical efficacy or statistical generalization.

The separate database restart probe stored synthetic markers, stopped only owned local processes, restarted them and checked the records. PostgreSQL was stopped with pg_ctl; Neo4j recovered from termination of its owned console process tree. Test markers were then removed. No data directories or Docker volumes were deleted.

Docker deployment attempt: `compose up --build --detach` failed before starting containers because `//./pipe/docker_engine` was absent. Docker CLI 29.9.3 and standalone Compose 5.7.0 were available. WSL was not installed; Docker Desktop was absent. No Windows restart or system-component installation was performed.

Both Compose files parse successfully. Registry pins are postgres:16.15-alpine and neo4j:5.26.32-community. Native Neo4j tests used 5.26.33; a matching Docker tag was not published, and the unavailable image pin was corrected to the published 5.26.32 Community tag. Registry manifest verification is not a container runtime test.

The separate test project has isolated temporary database services. The production Neo4j readiness check uses authenticated Bolt/Cypher; dependencies and image versions are pinned. These changes remain unverified in Linux containers until an engine is provided.

Machine-readable evidence is saved under `runtime/database-tests/`: `integration-tests.json`, `all-tests.json`, JUnit XML files, `live-http.json`, `database-restart.json` and `docker-verification.json`. Database credentials live separately in ignored runtime storage and are not copied into this report.

The database processes were left running on localhost 55432 (PostgreSQL), 17687 (Bolt) and 17474 (Neo4j HTTP). The temporary Uvicorn verification server was stopped. Use `python scripts/local_databases.py stop` to stop only these owned test instances.

See [setup, reproduction and Docker prerequisites](deployment.md).
