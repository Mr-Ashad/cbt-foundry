// src/App.jsx

import ProtocolWorkbench from './components/ProtocolWorkBench';
import './index.css'; 
import './App.css';

/**
 * The main entry component for the Cerina Clinical Foundry UI.
 * It primarily serves as a wrapper for the core Protocol Workbench dashboard.
 */
function App() {
  return (
    <div className="App antialiased">
      
      {/* The ProtocolWorkbench handles all state management, API calls, 
        and the rendering of the HIL logic (Start, Monitor, Review).
      */}
      <ProtocolWorkbench />
    </div>
  );
}

export default App;