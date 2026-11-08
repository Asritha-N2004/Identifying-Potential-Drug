"""Validate Compose, deploy when an engine exists, and run isolated tests."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import httpx

ROOT=Path(__file__).resolve().parents[1]


if __name__=='__main__':
    directory=ROOT/'runtime/database-tests';directory.mkdir(parents=True,exist_ok=True)
    docker=shutil.which('docker')
    if not docker:raise SystemExit('Docker CLI not found; install Docker Desktop/Engine first')
    plugin=subprocess.run([docker,'compose','version'],capture_output=True,text=True)
    standalone=ROOT/'runtime/integration-tools/docker-compose.exe'
    compose=[docker,'compose'] if plugin.returncode==0 else ([str(standalone)] if standalone.exists() else None)
    if compose is None:raise SystemExit('Compose missing. Install the plugin or run scripts/download_integration_tools.py')
    results={'deployment_config':False,'test_config':False,'engine_available':False,'containers_started':False,
             'container_tests':'not_run','registry_images':{},'limitations':[]}
    def save():
        (directory/'docker-verification.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
    for key,file in [('deployment_config','docker-compose.yml'),('test_config','docker-compose.test.yml')]:
        response=subprocess.run(compose+['-f',file,'config','--quiet'],cwd=ROOT,capture_output=True,text=True)
        results[key]=response.returncode==0
        if response.returncode:
            save();raise SystemExit(f'{file} failed Compose validation')
    for name,image in [('postgres','postgres:16.15-alpine'),('neo4j','neo4j:5.26.32-community')]:
        response=subprocess.run([docker,'manifest','inspect',image],capture_output=True,text=True)
        results['registry_images'][image]=response.returncode==0
        if response.returncode:
            save();raise SystemExit('Image tag unavailable: '+image)
        (directory/f'{name}-image-manifest.json').write_text(response.stdout,encoding='utf-8')
    engine=subprocess.run([docker,'info','--format','{{.ServerVersion}}'],capture_output=True,text=True)
    if engine.returncode:
        results['limitations'].append('Docker engine unavailable: '+engine.stderr.strip())
        save();print(json.dumps(results,indent=2));raise SystemExit(2)
    results['engine_available']=True;results['engine_version']=engine.stdout.strip();save()
    with (directory/'docker-deployment.log').open('w',encoding='utf-8') as log:
        deploy=subprocess.run(compose+['-f','docker-compose.yml','up','--build','--detach','--wait','--wait-timeout','300'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    if deploy.returncode:
        results['limitations'].append('Deployment failed; inspect docker-deployment.log');save();raise SystemExit(1)
    results['containers_started']=True
    with httpx.Client(base_url='http://127.0.0.1:8080',timeout=30) as client:
        response=client.get('/');response.raise_for_status()
        health=client.get('/api/health');health.raise_for_status()
        results['health']=health.json()
        assert results['health']['database']=='postgresql' and results['health']['neo4j']
    save()
    (ROOT/'runtime/container-tests').mkdir(parents=True,exist_ok=True)
    isolated=compose+['-p','atlas-integration','-f','docker-compose.test.yml']
    try:
        with (directory/'docker-tests.log').open('w',encoding='utf-8') as log:
            tested=subprocess.run(isolated+['up','--build','--abort-on-container-exit','--exit-code-from','tests'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        results['container_tests']='passed' if tested.returncode==0 else 'failed'
        save()
    finally:
        subprocess.run(isolated+['down'],cwd=ROOT,stdout=subprocess.DEVNULL)
    print(json.dumps(results,indent=2));raise SystemExit(tested.returncode)
