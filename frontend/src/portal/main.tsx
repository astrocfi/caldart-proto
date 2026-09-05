import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';

import '../styles/index.css';
import './portal.css';
import { App } from './App';

const container = document.getElementById('portal-root');
if (!container) {
  throw new Error('#portal-root is missing — is templates/portal.html rendering?');
}

createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
