// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {DataPipeline} from './DataPipeline';
import {api,waitForJob} from './api';
vi.mock('./api',()=>({api:vi.fn(),waitForJob:vi.fn()}));
afterEach(()=>{cleanup();vi.resetAllMocks()});

it('retrieves a snapshot and activates it through the actual API contract',async()=>{
  vi.mocked(api).mockResolvedValueOnce({job_id:'mock-job'}).mockResolvedValueOnce({});
  vi.mocked(waitForJob).mockResolvedValue({result:{snapshot_id:'a'.repeat(64),entities:100,relationships:200,selected_drugs:10}});
  const activate=vi.fn().mockResolvedValue(undefined);
  render(<DataPipeline onActivate={activate}/>);
  fireEvent.click(screen.getByRole('button',{name:'Ingest three diseases'}));
  await screen.findByText('100 entities · 200 relationships · 10 drugs');
  fireEvent.click(screen.getByRole('button',{name:'Build and activate graph'}));
  await vi.waitFor(()=>expect(activate).toHaveBeenCalledOnce());
  expect(api).toHaveBeenCalledWith('/graph/build',{snapshot_id:'a'.repeat(64)});
});

it('shows source errors without enabling graph activation',async()=>{
  vi.mocked(api).mockRejectedValue(new Error('Source unavailable'));
  render(<DataPipeline onActivate={async()=>{}}/>);
  fireEvent.click(screen.getByRole('button',{name:'Ingest three diseases'}));
  expect((await screen.findByRole('alert')).textContent).toBe('Source unavailable');
  expect(screen.queryByRole('button',{name:'Build and activate graph'})).toBeNull();
});
