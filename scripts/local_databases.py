"""Workspace-only Windows PostgreSQL/Neo4j test instances; no Windows services."""
import argparse
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import time
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/integration-python'))
BASE=ROOT/'runtime/local-databases'
TOOLS=ROOT/'runtime/integration-tools'
HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)


def run(args,env=None):
    # Windows background servers may inherit pipe handles, preventing communicate()
    # from reaching EOF after pg_ctl exits. A file avoids that startup deadlock.
    with tempfile.TemporaryFile(mode='w+',encoding='utf-8',dir=BASE) as output:
        result=subprocess.run([str(a) for a in args],env=env,stdout=output,stderr=subprocess.STDOUT,creationflags=HIDDEN)
        output.seek(0);text=output.read()
    if result.returncode:
        raise RuntimeError(f'{Path(str(args[0])).name} failed: {text}')
    return text


def open_port(port):
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(('127.0.0.1',port))==0


def start():
    BASE.mkdir(parents=True,exist_ok=True)
    path=BASE/'credentials.json'
    if path.exists():credentials=json.loads(path.read_text(encoding='utf-8'))
    else:
        if open_port(55432) or open_port(17687):raise RuntimeError('Test port already in use; refusing to reuse unknown service')
        credentials={'postgres_password':secrets.token_urlsafe(24),'neo4j_password':secrets.token_urlsafe(24)}
        path.write_text(json.dumps(credentials),encoding='utf-8')
    pg=TOOLS/'postgresql-16.15-windows/pgsql/bin'
    neo=TOOLS/'neo4j-5.26.33-windows/neo4j-community-5.26.33'
    java=next((TOOLS/'java21').glob('*/bin/java.exe')).parents[1]
    pgdata=BASE/'postgres-data'
    env=os.environ.copy();env['PGPASSWORD']=credentials['postgres_password']
    if not (pgdata/'PG_VERSION').exists():
        pw=BASE/'postgres-pw.tmp';pw.write_text(credentials['postgres_password'],encoding='utf-8')
        try:run([pg/'initdb.exe','-D',pgdata,'-U','research','--pwfile',pw,'--auth-host=scram-sha-256','--auth-local=trust','--encoding=UTF8','--no-locale'],env)
        finally:pw.unlink(missing_ok=True)
    if not open_port(55432):
        run([pg/'pg_ctl.exe','-D',pgdata,'-l',BASE/'postgres.log','-o','-p 55432 -h 127.0.0.1','-w','start'],env)
    args=[pg/'psql.exe','-h','127.0.0.1','-p','55432','-U','research','-d','postgres','-tAc']
    if '1' not in run(args+["SELECT 1 FROM pg_database WHERE datname='research_integration'"],env):
        run([pg/'createdb.exe','-h','127.0.0.1','-p','55432','-U','research','research_integration'],env)
    print('PostgreSQL ready on 127.0.0.1:55432',flush=True)
    env['JAVA_HOME']=str(java);env['NEO4J_HOME']=str(neo)
    env['NEO4J_CONF']=str(neo/'conf')
    if not open_port(17687):
        config='\n'.join(['server.default_listen_address=127.0.0.1',
            'server.bolt.enabled=true','server.bolt.listen_address=127.0.0.1:17687',
            'server.bolt.advertised_address=127.0.0.1:17687','server.http.enabled=true',
            'server.http.listen_address=127.0.0.1:17474','server.memory.heap.initial_size=128m',
            'server.http.advertised_address=127.0.0.1:17474',
            'server.memory.heap.max_size=256m','server.memory.pagecache.size=64m',
            'server.jvm.additional=-XX:ActiveProcessorCount=2',
            # AF_UNIX connect fails on this Windows host even with a short temp path.
            # A deliberately unavailable socket directory makes OpenJDK's selector
            # use its built-in TCP-loopback fallback, without modifying Java binaries.
            'server.jvm.additional=-Djdk.net.unixdomain.tmpdir=.atlas-tcp-loopback-fallback',
            'dbms.usage_report.enabled=false'])+'\n'
        (neo/'conf/neo4j.conf').write_text(config,encoding='utf-8')
        marker=BASE/'neo4j-initialized'
        if not marker.exists():
            run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',neo/'bin/neo4j-admin.ps1','dbms','set-initial-password',credentials['neo4j_password']],env)
            marker.write_text('initialized',encoding='utf-8')
        with (BASE/'neo4j-console.log').open('ab') as log:
            process=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(neo/'bin/neo4j.ps1'),'console'],env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=HIDDEN)
        (BASE/'neo4j-process.json').write_text(json.dumps({'pid':process.pid}),encoding='utf-8')
        for _ in range(60):
            if open_port(17687):break
            if process.poll() is not None:raise RuntimeError('Neo4j exited; inspect runtime/local-databases/neo4j-console.log')
            time.sleep(.5)
        else:raise RuntimeError('Neo4j startup timed out; inspect local log')
    from neo4j import GraphDatabase
    with GraphDatabase.driver('bolt://127.0.0.1:17687',auth=('neo4j',credentials['neo4j_password'])) as driver:
        driver.verify_connectivity()
    print('Neo4j ready on 127.0.0.1:17687 (HTTP 17474)',flush=True)
    print('Credentials saved only to runtime/local-databases/credentials.json',flush=True)


def stop():
    """Stop only the PostgreSQL data directory and Neo4j process we created."""
    pg=TOOLS/'postgresql-16.15-windows/pgsql/bin'
    if (BASE/'postgres-data/postmaster.pid').exists():
        run([pg/'pg_ctl.exe','-D',BASE/'postgres-data','-m','fast','-w','stop'])
        print('Stopped workspace PostgreSQL',flush=True)
    marker=BASE/'neo4j-process.json'
    if marker.exists():
        pid=int(json.loads(marker.read_text(encoding='utf-8'))['pid'])
        owned=str(TOOLS/'neo4j-5.26.33-windows/neo4j-community-5.26.33/bin/neo4j.ps1').replace("'","''")
        # Refuse to kill a reused PID or any process outside the known launcher.
        command=f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}'; if ($p) {{ if (-not $p.CommandLine.Contains('{owned}')) {{ throw 'PID no longer belongs to workspace Neo4j' }}; & taskkill.exe /PID {pid} /T /F; if ($LASTEXITCODE -ne 0) {{ exit $LASTEXITCODE }} }}"
        run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command])
        print('Stopped workspace Neo4j process tree',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','stop'])
    args=parser.parse_args()
    start() if args.action=='start' else stop()
