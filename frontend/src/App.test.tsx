// @vitest-environment jsdom
import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import App from './App';
vi.mock('./Graph',()=>({Graph:()=> <div>Interactive graph</div>}));
vi.mock('recharts',()=>({ResponsiveContainer:()=>null,LineChart:()=>null,Line:()=>null,XAxis:()=>null,YAxis:()=>null,Tooltip:()=>null,CartesianGrid:()=>null,BarChart:()=>null,Bar:()=>null,Legend:()=>null}));
afterEach(()=>{cleanup();vi.restoreAllMocks()});
function mockApi(failed=false){
  vi.stubGlobal('fetch',vi.fn(async(input:string)=>{
    if(failed)return {ok:false,json:async()=>({detail:'Service unavailable'})};
    const value=input.endsWith('/health')?{mode:'synthetic',trained_checkpoint:true}:input.includes('statistics')?{nodes:72,edges:136}:input.endsWith('/diseases')?[{id:'SYNTHETIC:Disease:0',name:'Synthetic Disease 01'}]:input.includes('subgraph')?{nodes:[],edges:[]}:{};
    return {ok:!input.includes('metrics'),json:async()=>value};
  }));
}
describe('research dashboard',()=>{
  it('shows synthetic context and lets researchers search loaded diseases',async()=>{
    mockApi();render(<App/>);
    await screen.findByText('SYNTHETIC DATA');
    expect(screen.getByText('Research hypotheses only.')).toBeTruthy();
    fireEvent.change(screen.getByLabelText('Search loaded disease entities'),{target:{value:'does not exist'}});
    await waitFor(()=>expect(screen.queryByRole('option')).toBeNull());
  });
  it('renders backend errors',async()=>{
    mockApi(true);render(<App/>);expect(await screen.findByRole('alert')).toBeTruthy();
  });
  it('navigates to evidence gaps without inventing candidates',async()=>{
    mockApi();render(<App/>);fireEvent.click(screen.getByRole('button',{name:/Evidence & explanation/}));
    expect(screen.getByText('No candidate selected')).toBeTruthy();
  });
});
