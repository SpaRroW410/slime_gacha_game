/* Runs the game's Python (Pyodide) off the main thread so long sessions (Pit, Rift, Quarry, scouting, waiting days)
 * never freeze the page. Protocol (JSON strings in and out, like Session.call_json):
 *   page -> worker   {type:'init', bases:[...]}            worker -> page  {type:'progress', text} | {type:'ready'} | {type:'error', error}
 *   page -> worker   {type:'call', id, cmd, args}          worker -> page  {type:'result', id, json} | {type:'fail', id, error}
 * Every byte downloaded is reported as progress, so the page can tell a slow phone from a stalled one (backend.js watchdog).
 */
let call = null;

/* Count the bytes of every download (the Python runtime is ~9 MB) and report them as progress. */
const realFetch = self.fetch.bind(self);
self.fetch = async (input, init) => {
  const r = await realFetch(input, init);
  if (!r.body || typeof TransformStream === 'undefined') return r;
  const name = String((input && input.url) || input).split('/').pop().split('?')[0];
  const total = Number(r.headers.get('content-length')) || 0;
  let got = 0, last = 0;
  const count = new TransformStream({
    transform(chunk, ctl) {
      got += chunk.byteLength;
      const now = Date.now();
      if (now - last > 250) {
        last = now;
        postMessage({ type: 'progress', text: `Downloading the Python runtime… ${(got / 1e6).toFixed(1)}${total ? ' of ' + (total / 1e6).toFixed(1) : ''} MB (${name})` });
      }
      ctl.enqueue(chunk);
    },
  });
  return new Response(r.body.pipeThrough(count), { status: r.status, statusText: r.statusText, headers: r.headers });
};

async function init(bases) {
  let py = null, lastErr;
  for (const base of bases) {
    try {
      postMessage({ type: 'progress', text: base.startsWith('http') ? 'Loading the Python runtime from the internet…' : 'Loading the Python runtime…' });
      importScripts(base + 'pyodide.js');
      py = await loadPyodide({ indexURL: base });
      break;
    } catch (e) { lastErr = e; postMessage({ type: 'progress', text: 'That copy of Python did not load; trying another…' }); }
  }
  if (!py) throw lastErr || new Error('Pyodide unavailable');
  postMessage({ type: 'progress', text: 'Unpacking the game…' });
  const zip = await (await fetch('slime_gacha.zip')).arrayBuffer();
  py.unpackArchive(zip, 'zip');
  postMessage({ type: 'progress', text: 'Starting the colony…' });
  py.runPython(`
from slime_gacha.registry import load_plugins
from slime_gacha.webapi import Session
load_plugins()
SESSION = Session()
`);
  call = py.runPython('SESSION.call_json');
}

onmessage = async (e) => {
  const m = e.data;
  if (m.type === 'init') {
    try { await init(m.bases); postMessage({ type: 'ready' }); }
    catch (err) { postMessage({ type: 'error', error: String(err && err.message || err) }); }
  } else if (m.type === 'call') {
    try { postMessage({ type: 'result', id: m.id, json: call(m.cmd, JSON.stringify(m.args || {})) }); }
    catch (err) { postMessage({ type: 'fail', id: m.id, error: String(err && err.message || err) }); }
  }
};
