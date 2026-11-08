// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {AuthShell} from './AuthShell';
afterEach(()=>{cleanup();vi.unstubAllEnvs();vi.unstubAllGlobals()});
it('protects the workspace until successful sign-in',async()=>{
  vi.stubEnv('VITE_AUTH_ENABLED','true');
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({json:async()=>({user:null})}).mockResolvedValueOnce({ok:true,json:async()=>({user:'researcher'})}));
  render(<AuthShell><div>Private research workspace</div></AuthShell>);
  await screen.findByText('Welcome back');
  expect(screen.queryByText('Private research workspace')).toBeNull();
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'researcher'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-password'}});
  fireEvent.click(screen.getByRole('button',{name:/Sign in to workspace/}));
  expect(await screen.findByText('Private research workspace')).toBeTruthy();
});
it('shows invalid sign-in errors and keeps the workspace hidden',async()=>{
  vi.stubEnv('VITE_AUTH_ENABLED','true');
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({json:async()=>({user:null})}).mockResolvedValueOnce({ok:false,json:async()=>({detail:'Username or password is incorrect'})}));
  render(<AuthShell><div>Private research workspace</div></AuthShell>);
  await screen.findByText('Welcome back');
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'researcher'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'incorrect'}});
  fireEvent.click(screen.getByRole('button',{name:/Sign in to workspace/}));
  expect((await screen.findByRole('alert')).textContent).toBe('Username or password is incorrect');
  expect(screen.queryByText('Private research workspace')).toBeNull();
});

it('creates an account and opens the protected workspace',async()=>{
  vi.stubEnv('VITE_AUTH_ENABLED','true');
  const fetch=vi.fn().mockResolvedValueOnce({json:async()=>({user:null,registration_available:true})}).mockResolvedValueOnce({ok:true,json:async()=>({user:'new-researcher'})});
  vi.stubGlobal('fetch',fetch);
  render(<AuthShell><div>Private research workspace</div></AuthShell>);
  await screen.findByText('Welcome back');
  fireEvent.click(screen.getByRole('button',{name:'Create account'}));
  expect(screen.getByText('Create your account')).toBeTruthy();
  expect(screen.getByPlaceholderText('Choose a name or nickname')).toBeTruthy();
  expect(screen.queryByText(/Use 3–32 letters/)).toBeNull();
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'new-researcher'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-secure-password'}});
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'test-secure-password'}});
  fireEvent.click(screen.getByRole('button',{name:/^Create account/}));
  expect(await screen.findByText('Private research workspace')).toBeTruthy();
  expect(fetch.mock.calls[1][0]).toBe('/api/auth/register');
});

it('rejects mismatched passwords before submitting registration',async()=>{
  vi.stubEnv('VITE_AUTH_ENABLED','true');
  const fetch=vi.fn().mockResolvedValue({json:async()=>({user:null})});vi.stubGlobal('fetch',fetch);
  render(<AuthShell><div>Private research workspace</div></AuthShell>);
  await screen.findByText('Welcome back');fireEvent.click(screen.getByRole('button',{name:'Create account'}));
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'new-researcher'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-secure-password'}});
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'different-password'}});
  fireEvent.click(screen.getByRole('button',{name:/^Create account/}));
  expect((await screen.findByRole('alert')).textContent).toBe('Passwords do not match');
  expect(fetch).toHaveBeenCalledTimes(1);
});

it('shows a duplicate username error from registration',async()=>{
  vi.stubEnv('VITE_AUTH_ENABLED','true');
  vi.stubGlobal('fetch',vi.fn().mockResolvedValueOnce({json:async()=>({user:null})}).mockResolvedValueOnce({ok:false,json:async()=>({detail:'That username is already taken'})}));
  render(<AuthShell><div>Private research workspace</div></AuthShell>);
  await screen.findByText('Welcome back');fireEvent.click(screen.getByRole('button',{name:'Create account'}));
  fireEvent.change(screen.getByLabelText('Username'),{target:{value:'existing-user'}});
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'test-secure-password'}});
  fireEvent.change(screen.getByLabelText('Confirm password'),{target:{value:'test-secure-password'}});
  fireEvent.click(screen.getByRole('button',{name:/^Create account/}));
  expect((await screen.findByRole('alert')).textContent).toBe('That username is already taken');
  expect(screen.queryByText('Private research workspace')).toBeNull();
});
