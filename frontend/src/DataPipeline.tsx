import {useState} from 'react';
import {api,waitForJob} from './api';

export function DataPipeline({onActivate}:{onActivate:()=>Promise<void>}){
  const [busy,setBusy]=useState(''),[snapshot,setSnapshot]=useState<any>(null),[error,setError]=useState('');
  async function ingest(){
    setBusy('Retrieving official source records');setError('');setSnapshot(null);
    try{
      const job=await api('/data/ingest',{});
      const completed=await waitForJob(job.job_id,status=>setBusy('Ingestion · '+status));
      setSnapshot(completed.result);
    }catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  async function activate(){
    setBusy('Building source graph');setError('');
    try{await api('/graph/build',{snapshot_id:snapshot.snapshot_id});await onActivate();}
    catch(e){setError((e as Error).message)}finally{setBusy('')}
  }
  return <section className="panel"><h2>Real disease case studies</h2>
    <p>Retrieve rheumatoid arthritis, psoriasis and inflammatory bowel disease from Open Targets, with Europe PMC disease-context publications. This bounded subset preserves source provenance. Search hits do not establish drug efficacy.</p>
    <button className="primary" disabled={!!busy} onClick={ingest}>Ingest three diseases</button>
    {busy&&<p role="status">{busy}</p>}{error&&<p role="alert">{error}</p>}
    {snapshot&&<><p>{snapshot.entities} entities · {snapshot.relationships} relationships · {snapshot.selected_drugs} drugs</p>
      <details><summary>Snapshot provenance and limitations</summary><pre>{JSON.stringify(snapshot,null,2)}</pre></details>
      <p>Activate this source graph, then train a matching checkpoint before discovery. Previous jobs remain in the audit store.</p>
      <button className="secondary" disabled={!!busy} onClick={activate}>Build and activate graph</button></>}
  </section>
}
