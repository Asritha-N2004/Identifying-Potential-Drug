export function ModelSensitivity({data}:{data:any}){
  if(!data)return null;
  return <><h3>Trained model sensitivity</h3><p>{data.scope}</p><div className="table-scroll"><table><thead><tr><th>Occluded relationship</th><th>Model score change</th></tr></thead><tbody>{data.edges.map((e:any,i:number)=><tr key={i}><td>{e.source} → {e.relation} → {e.target}</td><td className="mono">{e.score_difference.toFixed(5)}</td></tr>)}</tbody></table></div><p className="footnote">Positive change means the original model score decreased when this edge and its inverse were removed. Negative change means it increased. This measures the model, not a biological intervention.</p></>;
}
