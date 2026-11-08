"""Run opt-in live tests with local credentials without printing secrets."""
import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'runtime/integration-python'))


def configure():
    credentials=json.loads((ROOT/'runtime/local-databases/credentials.json').read_text(encoding='utf-8'))
    os.environ['TEST_POSTGRES_URL']='postgresql+psycopg://research:'+credentials['postgres_password']+'@127.0.0.1:55432/research_integration'
    os.environ['TEST_NEO4J_URI']='bolt://127.0.0.1:17687'
    os.environ['TEST_NEO4J_PASSWORD']=credentials['neo4j_password']
    os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
    return credentials


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--all',action='store_true');args=parser.parse_args()
    configure()
    import psycopg
    from neo4j import GraphDatabase
    with psycopg.connect(os.environ['TEST_POSTGRES_URL'].replace('postgresql+psycopg://','postgresql://')) as connection:
        pgversion=connection.execute('SELECT version()').fetchone()[0]
    with GraphDatabase.driver(os.environ['TEST_NEO4J_URI'],auth=('neo4j',os.environ['TEST_NEO4J_PASSWORD'])) as driver:
        with driver.session() as session:
            neoversion=session.run('CALL dbms.components() YIELD versions,edition RETURN versions[0] AS version,edition').single().data()
    import pytest
    output=ROOT/'runtime/database-tests';output.mkdir(exist_ok=True)
    xml=output/('all-tests.xml' if args.all else 'integration-tests.xml')
    code=pytest.main(['-q',str(ROOT/'backend/tests' if args.all else ROOT/'backend/tests/test_external_databases.py'),'--junitxml='+str(xml)])
    suite=ET.parse(xml).getroot().find('testsuite')
    result={'exit_code':int(code),'tests':int(suite.attrib['tests']),'failures':int(suite.attrib['failures']),
            'errors':int(suite.attrib['errors']),'skipped':int(suite.attrib['skipped']),
            'postgres':pgversion,'neo4j':neoversion,'drivers':{name:importlib.metadata.version(name) for name in ['psycopg','neo4j']},
            'deployment':'Native workspace-only processes on Windows; not containers'}
    (output/('all-tests.json' if args.all else 'integration-tests.json')).write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result,indent=2))
    raise SystemExit(code)
