import {useEffect,useRef} from 'react';
import cytoscape from 'cytoscape';

export function Graph({data}:{data:any}){
  const ref=useRef<HTMLDivElement>(null);
  useEffect(()=>{
    if(!data||!ref.current)return;
    const cy=cytoscape({container:ref.current,elements:[...data.nodes.map((n:any)=>({data:{id:n.id,label:n.name,kind:n.kind}})),...data.edges.map((e:any,i:number)=>({data:{id:'e'+i,source:e.source,target:e.target,label:e.relation}}))],style:[{selector:'node',style:{'background-color':'#4e9f88','label':'data(label)','color':'#a9b9cd','font-size':11,'text-valign':'bottom','text-margin-y':8,'width':24,'height':24}},{selector:'node[kind="Drug"]',style:{'background-color':'#77a8ed'}},{selector:'node[kind="Disease"]',style:{'background-color':'#eda66d','width':36,'height':36}},{selector:'edge',style:{'width':1.2,'line-color':'#405166','target-arrow-color':'#405166','target-arrow-shape':'triangle','curve-style':'bezier','label':'data(label)','font-size':8,'color':'#7c8ea6','text-rotation':'autorotate'}}],layout:{name:'cose',animate:false,padding:45},wheelSensitivity:.2});
    cy.on('tap','node',event=>{const n=event.target; cy.elements().removeClass('selected'); n.addClass('selected')});
    return()=>cy.destroy();
  },[data]);
  return <div ref={ref} className="graph" role="img" aria-label="Interactive knowledge graph. Drag nodes, zoom and pan."/>;
}
