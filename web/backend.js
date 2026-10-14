/* Transports for the game API. Both expose:  await backend.call(cmd, args) -> envelope (see webapi.py)
 *  - ServerBackend  : POSTs to serve.py (python3 serve.py)
 *  - PyodideBackend : runs the very same Python inside the page (static hosting, fully offline once vendored)
 */
class ServerBackend {
  constructor() { this.name = 'Python server'; }
  async call(cmd, args = {}) {
    const r = await fetch('/api', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ cmd, args }) });
    return r.json();
  }
}

class PyodideBackend {
  constructor(onProgress) { this.name = 'In-browser Python (Pyodide)'; this.onProgress = onProgress || (() => {}); }
  async init() {
    const bases = ['vendor/pyodide/', 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/'];
    let lastErr;
    for (const base of bases) {
      try {
        this.onProgress('Loading Python runtime…');
        await new Promise((res, rej) => {
          const s = document.createElement('script');
          s.src = base + 'pyodide.js'; s.onload = res; s.onerror = () => rej(new Error('cannot load ' + s.src));
          document.head.appendChild(s);
        });
        this.py = await loadPyodide({ indexURL: base });
        break;
      } catch (e) { lastErr = e; }
    }
    if (!this.py) throw lastErr || new Error('Pyodide unavailable');
    this.onProgress('Unpacking the game…');
    const zip = await (await fetch('slime_gacha.zip')).arrayBuffer();
    this.py.unpackArchive(zip, 'zip');
    this.py.runPython(`
from slime_gacha.registry import load_plugins
from slime_gacha.webapi import Session
load_plugins()
SESSION = Session()
`);
    this.fn = this.py.runPython('SESSION.call_json');
  }
  async call(cmd, args = {}) { return JSON.parse(this.fn(cmd, JSON.stringify(args))); }
}

async function chooseBackend(onProgress) {
  try {
    const r = await fetch('/api/ping', { cache: 'no-store' });
    if (r.ok && (await r.json()).ok) return new ServerBackend();
  } catch (e) { /* not served by serve.py -> static mode */ }
  const b = new PyodideBackend(onProgress);
  await b.init();
  return b;
}
