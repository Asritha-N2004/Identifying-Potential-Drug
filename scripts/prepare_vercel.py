"""Package only the built frontend and protected, real-source published analyses."""
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
ROOT=Path(__file__).resolve().parents[1]
TARGET=ROOT/'runtime/atlas-vercel'

if __name__=='__main__':
    manifest=json.loads((ROOT/'data/real/latest.json').read_text(encoding='utf-8'))
    dataset=json.loads((ROOT/'data/real'/manifest['snapshot_id']/'dataset.json').read_text(encoding='utf-8'))
    experiments=json.loads((ROOT/'models/evaluation/real-experiments.json').read_text(encoding='utf-8'))
    data={'dataset':dataset,'graph':experiments['graph'],'evaluation':experiments['evaluation'],'limitations':manifest['limitations'],'cases':{}}
    with sqlite3.connect(ROOT/'runtime/real-cases.db') as connection:
        for case in experiments['cases']:
            disease=case['disease']['id']
            records=connection.execute("SELECT id,payload,result,created_at FROM jobs WHERE kind='discovery' AND status='complete' ORDER BY created_at DESC").fetchall()
            for id,payload,result,created in records:
                payload=json.loads(payload);result=json.loads(result)
                if payload['disease_id']==disease and result['graph']['sha256']==data['graph']['sha256']:
                    # Preserve actual computed candidate records and actual recorded executions.
                    result['candidates']=case['candidates']
                    logs=[{'agent_name':name,'status':status,'duration_seconds':duration,'output_summary':json.loads(summary),'published_snapshot':True} for name,status,duration,summary in connection.execute('SELECT agent_name,status,duration_seconds,output FROM agent_executions WHERE job_id=? ORDER BY rowid',(id,))]
                    assert len(logs)==9
                    data['cases'][disease]={'job':{'id':id,'kind':'discovery','status':'complete','payload':payload,'result':result,'created_at':created.replace(' ','T')+'Z','error':None},'logs':logs}
                    break
            else:raise RuntimeError('No matching recorded execution: '+disease)
    output=TARGET/'.vercel/output';static=output/'static'
    function=output/'functions/api/handler.func';function.mkdir(parents=True,exist_ok=True)
    shutil.copytree(ROOT/'runtime/atlas-frontend',static,dirs_exist_ok=True)
    for name in ['handler.mjs','auth.mjs']:shutil.copy2(ROOT/'web'/name,function/name)
    options={'entryPoints':[str(ROOT/'web/handler.mjs')],'bundle':True,'platform':'node','format':'esm','target':'node22',
        'banner':{'js':'import { createRequire as __atlasCreateRequire } from "node:module"; const require = __atlasCreateRequire(import.meta.url);'},
        'outfile':str(function/'handler.mjs')}
    subprocess.run([shutil.which('node'),'-e','require(process.argv[1]).buildSync(JSON.parse(process.argv[2]))',str(ROOT/'frontend/node_modules/esbuild'),json.dumps(options)],check=True)
    (function/'snapshot.json').write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
    (function/'.vc-config.json').write_text(json.dumps({'runtime':'nodejs22.x','handler':'handler.mjs','launcherType':'Nodejs','maxDuration':30}),encoding='utf-8')
    routes=[{'src':'/(.*)','headers':{'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'strict-origin-when-cross-origin'},'continue':True},
        {'src':'/api/(.*)','dest':'/api/handler?__route=$1'}, {'handle':'filesystem'}, {'src':'/(.*)','dest':'/index.html'}]
    (output/'config.json').write_text(json.dumps({'version':3,'routes':routes},indent=2),encoding='utf-8')
    (TARGET/'package.json').write_text(json.dumps({'name':'atlas-drug-repurposing','private':True,'version':'1.0.0'}),encoding='utf-8')
    (TARGET/'vercel.json').write_text(json.dumps({'framework':None}),encoding='utf-8')
    print(json.dumps({'directory':str(TARGET),'diseases':list(data['cases']),'nodes':len(dataset['entities']),'protected_snapshot_bytes':(function/'snapshot.json').stat().st_size}))
