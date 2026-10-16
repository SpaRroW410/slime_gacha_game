/* Transports for the game API. Both expose:  await backend.call(cmd, args) -> envelope (see webapi.py)
 *  - ServerBackend  : POSTs to serve.py (python3 serve.py)
 *  - WorkerBackend  : the very same Python in a Pyodide web worker (static hosting, offline once vendored; page never freezes)
 *  - PyodideBackend : the same on the main thread (fallback if workers fail, or with ?noworker)
 */
class ServerBackend {
  constructor() { this.name = 'Python server'; }
  async call(cmd, args = {}) {
    const r = await fetch('/api', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                    body: JSON.stringify({ cmd, args }) });
    return r.json();
  }
}

const PYODIDE_BASES = ['vendor/pyodide/', 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/'];

/* Pyodide in a Web Worker: the page stays responsive during long sessions. */
class WorkerBackend {
  constructor(onProgress) { this.name = 'In-browser Python (Pyodide, web worker)'; this.onProgress = onProgress || (() => {}); this.pending = new Map(); this.nextId = 1; }
  init() {
    return new Promise((resolve, reject) => {
      let w;
      try { w = new Worker('pyodide-worker.js'); } catch (e) { reject(e); return; }
      this.worker = w;
      w.onerror = (e) => { const err = new Error(e.message || 'worker failed'); reject(err); this._failAll(err); };
      w.onmessage = (e) => {
        const m = e.data;
        if (m.type === 'progress') this.onProgress(m.text);
        else if (m.type === 'ready') resolve();
        else if (m.type === 'error') reject(new Error(m.error));
        else if (m.type === 'result' || m.type === 'fail') {
          const p = this.pending.get(m.id);
          if (!p) return;
          this.pending.delete(m.id);
          if (m.type === 'result') { try { p.resolve(JSON.parse(m.json)); } catch (err) { p.reject(err); } } else p.reject(new Error(m.error));
        }
      };
      w.postMessage({ type: 'init', bases: PYODIDE_BASES });
    });
  }
  _failAll(err) { for (const p of this.pending.values()) p.reject(err); this.pending.clear(); }
  call(cmd, args = {}) {
    return new Promise((resolve, reject) => {
      const id = this.nextId++;
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ type: 'call', id, cmd, args });
    });
  }
}

/* Fallback: the same Python on the page's main thread (used if workers are unavailable, or with ?noworker). */
class PyodideBackend {
  constructor(onProgress) { this.name = 'In-browser Python (Pyodide)'; this.onProgress = onProgress || (() => {}); }
  async init() {
    let lastErr;
    for (const base of PYODIDE_BASES) {
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
  if (typeof Worker !== 'undefined' && !/[?&]noworker/.test(location.search)) {
    try { const w = new WorkerBackend(onProgress); await w.init(); return w; }
    catch (e) { console.warn('web worker unavailable, running Python on the main thread:', e); }
  }
  const b = new PyodideBackend(onProgress);
  await b.init();
  return b;
}
