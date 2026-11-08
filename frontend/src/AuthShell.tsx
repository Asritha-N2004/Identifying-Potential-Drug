import {FormEvent,ReactNode,useEffect,useState} from 'react';

export function AuthShell({children}:{children:ReactNode}){
  const enabled=(import.meta as any).env?.VITE_AUTH_ENABLED==='true';
  const [ready,setReady]=useState(!enabled),[user,setUser]=useState<string|null>(null);
  const [username,setUsername]=useState(''),[password,setPassword]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[show,setShow]=useState(false);
  const [register,setRegister]=useState(false),[confirm,setConfirm]=useState('');
  useEffect(()=>{if(enabled)fetch('/api/auth/session',{credentials:'same-origin'}).then(r=>r.json()).then(data=>setUser(data.user||null)).catch(()=>setError('Unable to reach sign-in service. Please try again.')).finally(()=>setReady(true))},[enabled]);
  async function login(event:FormEvent){
    event.preventDefault();setError('');
    if(register&&password!==confirm){setError('Passwords do not match');return}
    setBusy(true);
    try{
      const response=await fetch(register?'/api/auth/register':'/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username,password,...(register?{confirmPassword:confirm}:{})}),credentials:'same-origin'});
      const data=await response.json();if(!response.ok)throw new Error(data.detail||'Sign-in failed');
      setPassword('');setConfirm('');setUser(data.user);
    }catch(e){setError((e as Error).message)}finally{setBusy(false)}
  }
  async function logout(){
    const response=await fetch('/api/auth/logout',{method:'POST',credentials:'same-origin'});
    if(response.ok){setUser(null);window.location.reload()}
  }
  if(!enabled)return <>{children}</>;
  if(!ready)return <div className="auth-loading" role="status">Opening your research workspace…</div>;
  if(user)return <><button className="auth-signout" onClick={logout}>Sign out</button>{children}</>;
  return <div className="auth-shell">
    <section className="auth-story"><a className="auth-brand" href="/">⌘ <span>atlas<small>RESEARCH WORKBENCH</small></span></a>
      <div className="auth-story-content"><div className="auth-eyebrow">GRAPH-BASED DRUG REPURPOSING</div><h1>See the connections.<br/><em>Ask better questions.</em></h1>
        <p>A shared workspace for molecular networks, transparent predictions, and evidence you can trace.</p>
        <div className="auth-network" aria-hidden="true"><svg viewBox="0 0 420 215"><g stroke="#446587" strokeWidth="1"><path d="M30 100L110 45L205 95L285 35L390 110L310 180L205 95L140 180L30 100M110 45L140 180M285 35L310 180M30 100L205 95L390 110" fill="none"/></g><g fill="#83b6ee"><circle cx="30" cy="100" r="8"/><circle cx="110" cy="45" r="12"/><circle cx="390" cy="110" r="10"/></g><g fill="#80c9b4"><circle cx="205" cy="95" r="20"/><circle cx="310" cy="180" r="10"/></g><g fill="#e7af83"><circle cx="285" cy="35" r="9"/><circle cx="140" cy="180" r="13"/></g></svg><div><span>● Drugs</span><span>● Molecular targets</span><span>● Diseases</span></div></div>
      </div><p className="auth-footnote">Computational hypotheses. Traceable evidence. No clinical efficacy claims.</p>
    </section>
    <main className="auth-panel"><div className="auth-form-wrap"><div className="auth-eyebrow">YOUR RESEARCH, CONNECTED</div><h2>{register?'Create your account':'Welcome back'}</h2><p>{register?'Get started with the Atlas research workspace.':'Sign in to explore the Atlas research workspace.'}</p>
      <form onSubmit={login}><label htmlFor="atlas-username">Username</label><input id="atlas-username" autoComplete="username" value={username} onChange={e=>setUsername(e.target.value)} required maxLength={register?32:100} placeholder={register?'Choose a name or nickname':'Enter your username'}/>
        <label htmlFor="atlas-password">Password</label><div className="auth-password"><input id="atlas-password" type={show?'text':'password'} autoComplete={register?'new-password':'current-password'} value={password} onChange={e=>setPassword(e.target.value)} required minLength={register?12:undefined} maxLength={200} placeholder={register?'Create a strong password':'Enter your password'}/><button type="button" onClick={()=>setShow(!show)} aria-label={show?'Hide password':'Show password'}>{show?'Hide':'Show'}</button></div>
        {register&&<><p className="auth-field-hint">Use at least 12 characters.</p><label htmlFor="atlas-confirm">Confirm password</label><input id="atlas-confirm" type={show?'text':'password'} autoComplete="new-password" value={confirm} onChange={e=>setConfirm(e.target.value)} required maxLength={200} placeholder="Enter your password again"/></>}
        {error&&<p className="auth-error" role="alert">{error}</p>}<button className="auth-submit" type="submit" disabled={busy}>{busy?(register?'Creating account…':'Signing in…'):(register?'Create account':'Sign in to workspace')}<span>→</span></button>
      </form><p className="auth-help">{register?'Already have an account?':'New to Atlas?'} <button type="button" className="auth-switch" disabled={busy} onClick={()=>{setRegister(!register);setError('');setPassword('');setConfirm('')}}>{register?'Sign in':'Create account'}</button></p><div className="auth-trust">◈ <span>Protected session · Server-verified access</span></div>
    </div><div className="auth-panel-footer">ATLAS / RESEARCH EDITION <span>Built for careful investigation</span></div></main>
  </div>
}
