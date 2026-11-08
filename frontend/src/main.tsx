import {createRoot} from 'react-dom/client';
import App from './App';
import './style.css';
import './auth.css';
import {AuthShell} from './AuthShell';
createRoot(document.getElementById('root')!).render(<AuthShell><App/></AuthShell>);
