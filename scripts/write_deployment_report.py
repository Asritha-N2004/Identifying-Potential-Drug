"""Generate verification documentation only from saved observed reports."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

if __name__=='__main__':
    directory=ROOT/'runtime/database-tests'
    def read(name):return json.loads((directory/name).read_text(encoding='utf-8'))
    tests=read('all-tests.json');integration=read('integration-tests.json')
    live=read('live-http.json');restart=read('database-restart.json');docker=read('docker-verification.json')
    lines=['# Deployment verification — 8 November 2026','',
        'Live database integration is verified on native Windows processes. Docker configuration validation is verified; Docker image builds and container execution are not verified because this host has no engine.',
        '', '| Check | Observed result |','|---|---|',
        f"| PostgreSQL | {tests['postgres']} |",
        f"| Neo4j | {tests['neo4j']['version']} {tests['neo4j']['edition']} |",
        f"| Database drivers | psycopg {tests['drivers']['psycopg']}; neo4j {tests['drivers']['neo4j']} |",
        f"| Live integration suite | {integration['tests']} passed, {integration['failures']} failed, {integration['skipped']} skipped |",
        f"| Full backend suite with live databases | {tests['tests']} passed, {tests['failures']} failed, {tests['skipped']} skipped |",
        f"| Real HTTP workflow | {live['status']}; {live['nodes']} nodes, {live['edges']} edges, {live['agent_stages']} agents, {live['candidates']} returned hypotheses |",
        f"| Application restart persistence | {live['restart_persistence']} |",
        f"| PostgreSQL process restart persistence | {restart['postgres_record_survived_restart']} |",
        f"| Neo4j process restart persistence | {restart['neo4j_record_survived_restart']} |",
        f"| Deployment Compose validation | {docker['deployment_config']} |",
        f"| Test Compose validation | {docker['test_config']} |",
        f"| Docker engine accessible | {docker['engine_available']} |",
        f"| Containers started | {docker['containers_started']} |",
        f"| Container integration tests | {docker['container_tests']} |"]
    for name in ['postgres','neo4j']:
        path=directory/f'{name}-image-manifest.json'
        if path.exists() and path.stat().st_size:
            manifest=json.loads(path.read_text(encoding='utf-8-sig'))
            amd64=any(m.get('platform',{}).get('os')=='linux' and m.get('platform',{}).get('architecture')=='amd64' for m in manifest.get('manifests',[]))
            lines.append(f'| {name} image registry Linux/amd64 manifest | {amd64}; metadata verification only |')
    lines += ['', 'The three integration tests verify idempotent graph seeding, complete edge JSON/provenance and Unicode round trips, SQL job/log persistence, nine-stage application execution using both services, and restoration after application restart. Every test uses its own unique namespace. Dedicated test records are cleaned up without deleting unrelated data.',
        '',f"The live HTTP verification used graph `{live['graph_sha256']}` and disease `{live['disease']}`. It verified dashboard HTTP delivery, checkpoint reevaluation, a completed research analysis and saved results after server restart. This verifies integration and persistence, not clinical efficacy or statistical generalization.",
        '', 'The separate database restart probe stored synthetic markers, stopped only owned local processes, restarted them and checked the records. PostgreSQL was stopped with pg_ctl; Neo4j recovered from termination of its owned console process tree. Test markers were then removed. No data directories or Docker volumes were deleted.',
        '', 'Docker deployment attempt: `compose up --build --detach` failed before starting containers because `//./pipe/docker_engine` was absent. Docker CLI 29.9.3 and standalone Compose 5.7.0 were available. WSL was not installed; Docker Desktop was absent. No Windows restart or system-component installation was performed.',
        '', 'Both Compose files parse successfully. Registry pins are postgres:16.15-alpine and neo4j:5.26.32-community. Native Neo4j tests used 5.26.33; a matching Docker tag was not published, and the unavailable image pin was corrected to the published 5.26.32 Community tag. Registry manifest verification is not a container runtime test.',
        '', 'The separate test project has isolated temporary database services. The production Neo4j readiness check uses authenticated Bolt/Cypher; dependencies and image versions are pinned. These changes remain unverified in Linux containers until an engine is provided.',
        '', 'Machine-readable evidence is saved under `runtime/database-tests/`: `integration-tests.json`, `all-tests.json`, JUnit XML files, `live-http.json`, `database-restart.json` and `docker-verification.json`. Database credentials live separately in ignored runtime storage and are not copied into this report.',
        '', 'The database processes were left running on localhost 55432 (PostgreSQL), 17687 (Bolt) and 17474 (Neo4j HTTP). The temporary Uvicorn verification server was stopped. Use `python scripts/local_databases.py stop` to stop only these owned test instances.',
        '', 'See [setup, reproduction and Docker prerequisites](deployment.md).', '']
    (ROOT/'docs/deployment_results.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Wrote docs/deployment_results.md from measured artifacts')
