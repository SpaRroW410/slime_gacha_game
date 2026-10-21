/* Runs the game's Python (Pyodide) off the main thread so long sessions (Pit, Rift, Quarry, scouting, waiting days)
 * never freeze the page. Protocol (JSON strings in and out, like Session.call_json):
 *   page -> worker   {type:'init', bases:[...]}            worker -> page  {type:'progress', text} | {type:'ready'} | {type:'error', error}
 *   page -> worker   {type:'call', id, cmd, args}          worker -> page  {type:'result', id, json} | {type:'fail', id, error}
 */
let call = null;

const T0 = performance.now();
const lap = (what) => { try { console.log(`[boot] ${what}: ${Math.round(performance.now() - T0)} ms`); } catch (e) { /* ignore */ } };

async function init(bases) {
  const zipReq = fetch('slime_gacha.zip').then((r) => r.arrayBuffer());       // the game's files download while the Python runtime starts
  zipReq.catch(() => {});
  let py = null, lastErr;
  for (const base of bases) {
    try {
      postMessage({ type: 'progress', text: 'Loading Python runtime…' });
      importScripts(base + 'pyodide.js');
      py = await loadPyodide({ indexURL: base });
      break;
    } catch (e) { lastErr = e; }
  }
  if (!py) throw lastErr || new Error('Pyodide unavailable');
  lap('python runtime ready');
  postMessage({ type: 'progress', text: 'Unpacking the game…' });
  const zip = await zipReq;
  py.unpackArchive(zip, 'zip');
  lap('game unpacked');
  postMessage({ type: 'progress', text: 'Waking the Well…' });
  py.runPython(`
from slime_gacha.registry import load_plugins
from slime_gacha.webapi import Session
load_plugins()
SESSION = Session()
`);
  call = py.runPython('SESSION.call_json');
  lap('game imported');
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
