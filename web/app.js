/* Slime Gacha - browser UI. Talks to the game only through backend.call(cmd, args) (see backend.js / webapi.py). */
'use strict';

const LS_KEY = 'slimegacha.save.v1';
const CLASS_COLORS = { barbarian: '#e5604d', mage: '#8a7cff', medic: '#4cc38a', rogue: '#aab2c0', ranger: '#e0b341', necromancer: '#a56bd1' };
const RES = { white_gel: ['⚪', 'White gel'], purple_gel: ['🟣', 'Purple gel'], food: ['🍖', 'Food'], essence: ['✨', 'Essence'], herb_green: ['🟢🌿', 'Green herb (health)'], herb_red: ['🔴🌿', 'Red herb (strength)'], herb_blue: ['🔵🌿', 'Blue herb (armor)'], herb_yellow: ['🟡🌿', 'Yellow herb (stamina)'], scrap: ['🔩', 'Scrap'], alloy: ['🪙', 'Alloy'], crystal: ['💠', 'Crystal'], stardust: ['🌟', 'Stardust'], voidglass: ['🕳️', 'Voidglass'],
  stone_common: ['⚪💎', 'Common stone'], stone_uncommon: ['🟢💎', 'Uncommon stone'], stone_rare: ['🔵💎', 'Rare stone'], stone_epic: ['🟣💎', 'Epic stone'], stone_legendary: ['🟡💎', 'Legendary stone'] };
const CORE_RES = ['white_gel', 'purple_gel', 'food', 'essence'];
const NEED_NAME = { energy: 'Energy', food: 'Food', safety: 'Safety', belonging: 'Belonging', esteem: 'Esteem' };
const WISH = { energy: 'needs sleep', food: 'is hungry', safety: 'feels unsafe (hurt)', belonging: 'feels lonely', esteem: 'wants to prove itself' };
const TABS = [['colony', '🟢 Colony'], ['gacha', '🎰 Gacha'], ['parties', '👥 Parties'], ['dungeons', '🕳 Dungeons'],
  ['academy', '📚 Academy'], ['town', '🏠 Town'], ['people', '💞 People'], ['guide', '📖 Guide']];
const SUBS = {
  dungeons: [['descent', 'Hollow Descent'], ['pit', 'Gloop Pit'], ['rift', 'Rift & Quarry']],
  town: [['buildings', 'Buildings'], ['armory', 'Armory & relics'], ['alchemy', 'Alchemy']],
  people: [['bonds', 'Bonds'], ['keeper', 'Keeper'], ['council', 'Council'], ['records', 'Records']],
};
const DUNGEON_KINDS = ['main', 'grind', 'scout', 'adventure', 'quarry'];

let backend = null;
const S = { state: null, tab: 'colony', sel: null, sort: 'power', filter: 'all', feed: [], modal: null, pull: null,
  council: null, pv: null, busy: false, ui: {}, backendName: '', sub: {}, dtab: 'overview', guide: null, stockOpen: false };

/* ---------------------------------------------------------------- helpers */
const sub = (t) => (S.sub && S.sub[t]) || SUBS[t][0][0];
const info = (tip) => `<button class="info" data-act="info" data-tip="${esc(tip)}" aria-label="More information">i</button>`;
const subnav = (t) => `<div class="seg">${SUBS[t].map(([k, n]) => `<button class="${sub(t) === k ? 'on' : ''}" data-act="sub" data-t="${t}" data-s="${k}">${n}</button>`).join('')}</div>`;
const onCouncil = () => S.tab === 'people' && sub('people') === 'council';

const esc = (x) => String(x ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const ui = (k, d) => (S.ui[k] === undefined ? d : S.ui[k]);
const kindTitle = () => ({ pit: 'The Gloop Pit', delve: 'The Hollow Descent', skirmish: 'Skirmish' })[S.state?.battle?.kind];
const manualOn = () => !!S.ui.manual;
const cmdToggle = () => `<button class="btn small ${manualOn() ? 'primary' : ''}" data-act="toggle_manual" title="Fight turn by turn: every slime acts on its own turn. You can hand the fight back to the slimes at any time.">🎮 Take command: ${manualOn() ? 'ON' : 'off'}</button>`;
const num = (x, d = 0) => { const n = parseInt(x, 10); return Number.isFinite(n) ? n : d; };
const slimeById = (id) => S.state.slimes.find((s) => s.id === id);
const partyById = (id) => S.state.parties.find((p) => p.id === id);
const pct = (v, m) => Math.max(0, Math.min(100, m ? (100 * v) / m : 0));
const hashColor = (k) => { let h = 0; for (const c of String(k)) h = (h * 31 + c.charCodeAt(0)) % 360; return `hsl(${h} 60% 62%)`; };
const cost = (c) => Object.entries(c || {}).map(([k, v]) => `${v} ${RES[k]?.[0] || k}`).join(' ');
const affordable = (c) => Object.entries(c || {}).every(([k, v]) => (S.state.wallet[k] || 0) >= v);
const stars = (n) => `<span class="stars">${'★'.repeat(n)}<span class="off">${'★'.repeat(5 - n)}</span></span>`;
const bar = (v, m, cls = '', label = '', right = '') => {
  const p = pct(v, m);
  const level = (cls === 'hp' || cls === 'need') ? (p < 25 ? 'lvl-low' : p < 55 ? 'lvl-mid' : 'lvl-ok') : '';
  return `${label ? `<div class="lab"><span>${label}</span><span>${right || `${Math.round(v)}/${Math.round(m)}`}</span></div>` : ''}<div class="bar ${cls} ${level}"><i style="width:${p}%"></i></div>`;
};
const elName = (k) => { const e = S.state.elements.list.find((x) => x.key === k); return e ? `${e.emoji} ${e.name}` : k; };
const chip = (t, c = '') => `<span class="chip ${c}">${t}</span>`;
const badge = (t, c = '') => `<span class="badge ${c}">${t}</span>`;

function avatar(s, cls = '') {
  const c = CLASS_COLORS[s.archetype] || hashColor(s.archetype);
  const st = s.state === 'sleeping' || s.state === 'resting' ? s.state : '';
  return `<div class="blob ${s.rarity} ${st} ${cls}" style="--c:${c}"><i></i><i></i><span class="em">${s.emoji}</span></div>`;
}
function ghost(g) { // graveyard entry
  const c = CLASS_COLORS[g.archetype] || hashColor(g.archetype);
  return `<div class="blob sm dead" style="--c:${c}"><i></i><i></i></div>`;
}

/* ---------------------------------------------------------------- persistence + api */
function saveLocal(save) { try { localStorage.setItem(LS_KEY, JSON.stringify({ save, at: Date.now() })); } catch (e) { /* storage may be blocked */ } }
function loadLocal() { try { const r = localStorage.getItem(LS_KEY); return r ? JSON.parse(r).save : null; } catch (e) { return null; } }

function toast(msg, err = false) {
  const box = document.getElementById('toasts');
  const el = document.createElement('div');
  el.className = 'toast' + (err ? ' err' : '');
  el.textContent = msg;
  box.appendChild(el);
  while (box.children.length > 4) box.firstChild.remove();
  setTimeout(() => el.remove(), err ? 5200 : 3600);
}
function pushLog(lines) {
  const stamp = S.state ? `D${S.state.day + 1} ${String(S.state.tick % 24).padStart(2, '0')}h` : '';
  for (const l of lines) S.feed.unshift(`${stamp} · ${l}`);
  S.feed = S.feed.slice(0, 120);
}

async function act(cmd, args = {}, opt = {}) {
  if (S.busy) return null;
  S.busy = true;
  if (opt.slow) { const v = document.createElement('div'); v.className = 'busy-veil'; v.id = 'veil'; v.innerHTML = '<div class="spin"></div>'; document.body.appendChild(v); }
  let res;
  try { res = await backend.call(cmd, args); } catch (e) { toast('Connection problem: ' + e.message, true); res = null; }
  S.busy = false;
  document.getElementById('veil')?.remove();
  if (!res) { render(); return null; }
  if (res.state) S.state = res.state;
  if (res.ok) {
    if (res.save) saveLocal(res.save);
    pushLog(res.log || []);
    const b = res.result?.battle;
    if (!(b && b.length && !opt.noBattle)) (res.log || []).slice(0, 3).forEach((l) => toast(l.length > 140 ? l.slice(0, 137) + '…' : l));
    if (b && b.length && !opt.noBattle) S.modal = { type: 'battle', battles: b, title: opt.title || 'Battle report', summary: res.log };
    if (res.result?.pulled) S.pull = res.result.pulled;
  } else toast(res.error || 'Something went wrong.', true);
  if (onCouncil()) await loadCouncil(false);
  render();
  return res;
}
async function loadGuide() {
  if (S.guide) { render(); return; }
  const r = await backend.call('guide', {});
  if (r.ok) { S.guide = r.result.sections; }
  render();
}
/* (i) tooltips: hover or focus to read, click to pin */
let tipEl = null, tipPin = null;
function showTip(el) {
  if (!tipEl) { tipEl = document.createElement('div'); tipEl.id = 'tip'; document.body.appendChild(tipEl); }
  tipEl.textContent = el.dataset.tip; tipEl.style.display = 'block';
  const r = el.getBoundingClientRect(), w = Math.min(320, window.innerWidth - 24);
  tipEl.style.width = w + 'px';
  tipEl.style.left = Math.max(12, Math.min(window.innerWidth - w - 12, r.left + r.width / 2 - w / 2)) + 'px';
  const below = r.bottom + 8 + tipEl.offsetHeight < window.innerHeight;
  tipEl.style.top = (below ? r.bottom + 8 : Math.max(8, r.top - 8 - tipEl.offsetHeight)) + 'px';
}
function hideTip() { if (tipEl) tipEl.style.display = 'none'; tipPin = null; }
function toggleTip(el) { if (tipPin === el.dataset.tip && tipEl && tipEl.style.display === 'block') hideTip(); else { showTip(el); tipPin = el.dataset.tip; } }
document.addEventListener('mouseover', (e) => { const i = e.target.closest && e.target.closest('.info'); if (i && !tipPin) showTip(i); });
document.addEventListener('mouseout', (e) => { const i = e.target.closest && e.target.closest('.info'); if (i && !tipPin) hideTip(); });
document.addEventListener('focusin', (e) => { const i = e.target.closest && e.target.closest('.info'); if (i) showTip(i); });
document.addEventListener('click', (e) => { if (!(e.target.closest && e.target.closest('.info'))) hideTip(); }, true);
async function loadCouncil(rerender = true) {
  if (!S.state?.slimes.length) { S.council = null; return; }
  const r = await backend.call('council', {});
  if (r.ok) S.council = r.result;
  if (rerender) render();
}
const confirmThen = (msg, fn) => { if (window.confirm(msg)) fn(); };

/* ---------------------------------------------------------------- top-level render */
function render() {
  const app = document.getElementById('app');
  if (!S.state) { app.innerHTML = welcome(); return; }
  const keep = window.scrollY;
  const st = S.state;
  const fp = st.free_pull;
  const clk = st.clock;
  const stock = Object.entries(st.wallet).filter(([k, v]) => !CORE_RES.includes(k) && v > 0);
  app.innerHTML = `
  <header class="top">
    <div class="logo"><span class="dot"></span>Slime Gacha</div>
    <div class="res">${Object.entries(st.wallet).filter(([k]) => CORE_RES.includes(k)).map(([k, v]) => chip(`${RES[k]?.[0] || ''} <b>${v}</b>`, k === 'white_gel' ? 'white' : k === 'purple_gel' ? 'purple' : '')).join('')}
      ${stock.length ? `<button class="chip chipbtn" data-act="stock" title="Materials, stones and herbs">🎒 ${stock.length}</button>` : ''}</div>
    ${chip(`Day <b>${st.day + 1}</b> · ${String(st.tick % 24).padStart(2, '0')}:00`)}
    ${clk.mode === 'live' ? chip(`⏱ live ×${clk.rate_now}`, 'info') : ''}
    ${fp.available ? chip('🎁 free pull', 'ok') : ''}
    ${st.stress >= 0.1 ? chip(`😖 ${st.stress}`, 'bad') : ''}
    <span class="spacer"></span>
    ${clk.mode === 'turn' ? `<div class="seg small"><button data-act="wait" data-h="1">+1h</button><button data-act="wait" data-h="4">+4h</button><button data-act="wait" data-h="24">+1 day</button></div>` : ''}
    <button class="btn small" data-act="menu" title="Menu and settings">⋯</button>
  </header>
  ${S.stockOpen ? `<div class="popover" id="stockpop"><div class="row" style="gap:6px">${stock.map(([k, v]) => chip(`${RES[k]?.[0] || ''} ${RES[k]?.[1] || k}: <b>${v}</b>`)).join('')}</div></div>` : ''}
  <nav class="tabs">${TABS.map(([k, n]) => `<button class="${S.tab === k ? 'on' : ''}" data-act="tab" data-t="${k}">${n}${tabBadge(k)}</button>`).join('')}</nav>
  ${liveBar()}
  <main>${tabContent()}</main>
  <section style="padding:0 16px 20px;max-width:1280px;margin:0 auto;width:100%"><details><summary class="mute">Event log</summary><div class="feed">${S.feed.map((l) => `<div>${esc(l)}</div>`).join('') || '<small>Nothing yet.</small>'}</div></details></section>
  ${S.sel && slimeById(S.sel) ? `<div class="scrim" data-act="closesel"></div>${drawer(slimeById(S.sel))}` : ''}
  ${S.state.battle ? ARENA.render(S.state.battle) : ''}
  ${S.modal ? modalHtml() : ''}`;
  declutter();
  window.scrollTo(0, keep);
}
function tabBadge(k) {
  const st = S.state;
  if (k === 'people' && st.conflicts.length) return `<span class="n">${st.conflicts.length}</span>`;
  if (k === 'gacha' && st.free_pull.available) return '<span class="n">1</span>';
  if (k === 'dungeons' && Object.keys(st.dungeon.delves).length) return '<span class="n">!</span>';
  return '';
}
function tabContent() {
  return { colony, gacha, parties, dungeons, academy, town, people, guide }[S.tab]();
}

/* Live time: countdowns for parties that are away (wall clock, dilated). */
function liveBar() {
  const st = S.state, clk = st.clock;
  if (clk.mode !== 'live') return '';
  const rate = clk.rate_now || clk.lobby_rate;
  const mins = (h) => { const m = Math.round(h / rate * 60); return m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m} min`; };
  const items = clk.expeditions.map((e) => `🏃 ${esc(e.names.slice(0, 3).join(', '))}${e.names.length > 3 ? '…' : ''} back in ~${mins(e.hours)}`);
  Object.entries(st.dungeon.delves).forEach(([pid, d]) => { if (d.ready_in > 0) items.push(`🕳 ${esc(partyById(+pid)?.name || 'Party')} busy for ~${mins(d.ready_in)}`); });
  return `<div class="livebar"><span>⏱ Live time — home ×${clk.lobby_rate}, dungeons ×${clk.dungeon_rate}</span>${items.map((i) => `<span class="chip">${i}</span>`).join('')}</div>`;
}

/* Calm the page: long explanatory paragraphs under headings become (i) tooltips; dungeons say only whether death is possible. */
const DEATH = [[/Hollow Descent/, true, 'Death is permanent'], [/Scouting/, true, 'The whole party is lost if scouting fails'],
  [/Skirmish/, true, 'Death is permanent'], [/Gloop Pit/, false, ''], [/Wayfarer/, false, '']];
function declutter() {
  document.querySelectorAll('main .panel > h2, main .panel > h3').forEach((h) => {
    if (h.querySelector('.info')) return;
    const panel = h.parentElement;
    const p = [...panel.children].find((c) => c.tagName === 'P' && c.classList.contains('mute') && c.textContent.length > 80);
    if (p) {
      const idx = [...panel.children].indexOf(p), firstCtl = [...panel.children].findIndex((c) => c.querySelector && c.querySelector('input,select,button') && c !== h);
      if (firstCtl < 0 || idx < firstCtl + 3) {
        const b = document.createElement('button');
        b.className = 'info'; b.dataset.act = 'info'; b.dataset.tip = p.textContent.replace(/\s+/g, ' ').trim(); b.setAttribute('aria-label', 'More information'); b.textContent = 'i';
        h.appendChild(b); p.remove();
      }
    }
    const d = DEATH.find(([re]) => re.test(h.textContent));
    if (d && !panel.querySelector('.deathline')) {
      const el = document.createElement('div');
      el.className = 'deathline ' + (d[1] ? 'bad' : 'ok');
      el.textContent = d[1] ? '☠ ' + d[2] : '✓ Nobody dies here';
      h.insertAdjacentElement('afterend', el);
    }
  });
}

function welcome() {
  const saved = loadLocal();
  return `<div class="welcome panel">
    <div class="blob big"><i></i><i></i><span class="em">🟢</span></div>
    <h1>Slime Gacha</h1>
    <p class="mute">Pick me up, little goo! Collect slimes, keep them fed and happy, send them hunting, and dare the Hollow Descent.<br>Slimes can die. Choose wisely.</p>
    <div class="stack">
      ${saved ? '<button class="btn primary" data-act="continue">▶ Continue your colony</button>' : ''}
      <div class="row" style="justify-content:center">
        <label class="f">Party size <select data-ui="psize"><option>5</option><option>10</option><option>15</option></select></label>
        <label class="f">Seed <input type="text" data-ui="seed" placeholder="random" size="8"></label>
      </div>
      <button class="btn ${saved ? '' : 'primary'}" data-act="newgame">✨ New game</button>
      <small class="mute">Backend: ${esc(S.backendName)} · saves live in this browser (and Export/Import in the ⋯ menu).</small>
    </div></div>`;
}

/* ---------------------------------------------------------------- colony */
function colony() {
  const st = S.state;
  if (!st.slimes.length) return `<div class="panel well"><h2>The colony is empty</h2><p>Visit the Gacha tab and claim your free pull.</p><button class="btn primary" data-act="tab" data-t="gacha">🎰 Go to the Well</button></div>`;
  const rar = { common: 0, uncommon: 1, rare: 2, epic: 3, legendary: 4 };
  const sorters = { power: (a, b) => b.power - a.power, level: (a, b) => b.level - a.level || b.power - a.power,
    stars: (a, b) => b.stars - a.stars || rar[b.rarity] - rar[a.rarity], rarity: (a, b) => rar[b.rarity] - rar[a.rarity] || b.stars - a.stars,
    hp: (a, b) => a.hp / a.max_hp - b.hp / b.max_hp, name: (a, b) => a.name.localeCompare(b.name), morale: (a, b) => a.morale - b.morale };
  const filters = { all: () => true, free: (s) => !s.party, idle: (s) => s.state === 'idle' && !s.in_dungeon, wounded: (s) => s.hp < s.max_hp * 0.6,
    away: (s) => s.busy || s.state === 'hunting', needy: (s) => !!s.dominant };
  const list = st.slimes.filter(filters[S.filter]).sort(sorters[S.sort]);
  const opt = (obj, cur) => Object.entries(obj).map(([k, n]) => `<option value="${k}" ${k === cur ? 'selected' : ''}>${n}</option>`).join('');
  return `<div class="row between" style="margin-bottom:10px">
    <h2>${st.slimes.length} slimes · ${st.rest.used}/${st.rest.cap} resting</h2>
    <div class="row">
      <label class="f">Sort <select data-sel="sort">${opt({ power: 'Power', level: 'Level', stars: 'Stars', rarity: 'Rarity', hp: 'Lowest HP', morale: 'Lowest morale', name: 'Name' }, S.sort)}</select></label>
      <label class="f">Show <select data-sel="filter">${opt({ all: 'All', free: 'Not in a party', idle: 'Available', wounded: 'Wounded', away: 'Away', needy: 'Needs something' }, S.filter)}</select></label>
    </div></div>
  <div class="grid roster">${list.map(card).join('') || '<p class="mute">No slimes match.</p>'}</div>`;
}
function card(s) {
  const b = [];
  if (s.in_dungeon) b.push(badge('🕳 ' + s.in_dungeon, 'bad'));
  else if (s.state !== 'idle') b.push(badge(s.state, s.state === 'hunting' ? 'info' : ''));
  if (s.party) b.push(badge('👥 ' + esc(partyById(s.party)?.name || s.party)));
  if (s.hp < s.max_hp * 0.4) b.push(badge('wounded', 'warn'));
  if (s.grounded) b.push(badge('grounded', 'bad'));
  if (s.dominant && !s.busy) b.push(badge(WISH[s.dominant], 'warn'));
  if (s.feelings.length && s.feelings[0].value >= 40) b.push(badge(`${s.feelings[0].emoji} ${esc(s.feelings[0].name)}`, s.feelings[0].kind === 'bad' ? 'warn' : 'ok'));
  if (s.morale_label === 'broken') b.push(badge('broken morale', 'bad'));
  if (s.outlook) b.push(badge(`${s.outlook.emoji} ${s.outlook.name}`, 'info'));
  return `<div class="scard ${S.sel === s.id ? 'sel' : ''}" data-act="sel" data-id="${s.id}">
    ${avatar(s)}
    <div class="nm">${esc(s.name)}</div><div class="sub">${esc(s.title)} · Lv${s.level}</div>
    <div>${stars(s.stars)}</div>
    ${bar(s.hp, s.max_hp, 'hp')}
    <div class="badges">${b.join('')}</div></div>`;
}

function drawer(s) {
  const st = S.state;
  const free = !s.busy;
  const inDun = DUNGEON_KINDS.includes(s.in_dungeon);
  const ctx = { st, free, inDun };
  const tabs = [['overview', 'Overview'], ['fight', 'Fight'], ['mind', 'Mind'], ['gear', 'Gear']];
  const dt = tabs.some(([k]) => k === S.dtab) ? S.dtab : 'overview';
  const body = { overview: dOverview, fight: dFight, mind: dMind, gear: dGear }[dt](s, ctx);
  return `<aside class="drawer">
    <div class="row between"><h2 style="margin:0">${esc(s.name)}</h2><button class="btn small" data-act="closesel">✕</button></div>
    <div class="row" style="margin:8px 0">${avatar(s, 'big')}<div><div><b>${esc(s.title)}</b> ${chip(s.rarity, s.rarity)}</div><div>${stars(s.stars)} · Lv${s.level}/${s.level_cap} · stage ${s.stage}</div>
      <div class="mute">${s.state}${s.in_dungeon ? ' · inside ' + s.in_dungeon : ''} · mood ${s.mood}${s.party ? ' · 👥 ' + esc(partyById(s.party)?.name) : ''}</div></div></div>
    <div class="seg dtabs">${tabs.map(([k, n]) => `<button class="${dt === k ? 'on' : ''}" data-act="dtab" data-t="${k}">${n}</button>`).join('')}</div>
    ${body}
  </aside>`;
}
const sect = (title, tip, inner) => `<section class="dsec"><h4>${title}${tip ? info(tip) : ''}</h4>${inner}</section>`;

function dOverview(s, { st, free, inDun }) {
  const care = (c, label, extra = '') => `<button class="btn small" data-act="do" data-c="${c}" ${inDun || extra ? 'disabled' : ''} ${inDun ? 'title="Inside a dungeon - you cannot tend to them"' : ''}>${label}</button>`;
  const zone = ui('zone', st.zones[0].key);
  return `<div class="kv">${[['HP', `${s.hp}/${s.max_hp}`], ['ATK', s.stats.atk], ['DEF', s.stats.defense], ['MAG', s.stats.mag], ['SPD', s.stats.spd], ['Power', s.power]].map(([k, v]) => `<div><b>${v}</b><span>${k}</span></div>`).join('')}</div>
    ${bar(s.hp, s.max_hp, 'hp', 'HP')}${bar(s.xp, s.xp_next, 'xp', 'XP', s.level >= s.level_cap ? 'level cap' : `${s.xp}/${s.xp_next}`)}
    ${bar(s.morale, 100, 'morale', `Morale — ${s.morale_label}`, `power ×${s.morale_factor}`)}
    ${bar(s.stamina, s.max_stamina, 'know', `⚡ Stamina`, `${Math.round(s.stamina)}/${Math.round(s.max_stamina)}`)}
    ${s.buffs.length ? `<div class="row">${s.buffs.map((b) => chip(`${(st.potions.kinds.find((k) => k.key === b.kind) || {}).emoji || ''} ${b.kind} G${b.grade} · ${b.hours}h`, 'ok')).join('')}</div>` : ''}
    ${sect(`Needs ${s.dominant ? badge(WISH[s.dominant], 'warn') : badge('content', 'ok')}`, 'Needs fall over time. Unmet needs lower mood and morale, stir bad feelings and, at zero, hurt the slime. See the Guide tab for details.', Object.entries(s.needs).map(([k, v]) => bar(v, 100, 'need', NEED_NAME[k], v)).join(''))}
    ${sect('Care', inDun ? 'This slime is inside a dungeon: feeding, petting, sleeping and potions are not possible until it is back.' : 'Feeding, petting and rest. Not possible while a slime is inside a dungeon.', `<div class="row">
      ${care('feed', '🍖 Feed', st.wallet.food > 0 ? '' : 'x')}${care('pet', '🤗 Pet')}
      ${s.state === 'sleeping' || s.state === 'resting' ? care('wake', '⏰ Wake') : care('sleep', '😴 Sleep', free ? '' : 'x')}
      <button class="btn small" data-act="do" data-c="rest" ${!inDun && free && s.state !== 'resting' ? '' : 'disabled'}>🛏️ Rest Area</button>
      ${s.can_evolve ? `<button class="btn small primary" data-act="do" data-c="evolve" ${free ? '' : 'disabled'}>🌟 Evolve (${s.evolve_cost} ✨)</button>` : ''}</div>
      ${st.potions.stock.length ? `<div class="row"><select data-ui="pot_sel">${st.potions.stock.map((p) => `<option value="${p.kind}:${p.grade}">${(st.potions.kinds.find((k) => k.key === p.kind) || {}).emoji} ${p.kind} G${p.grade} ×${p.n}</option>`).join('')}</select><button class="btn small" data-act="use_potion" ${inDun ? 'disabled' : ''}>Drink</button></div>` : ''}`)}
    ${sect('Orders', 'Stance decides what the slime does in a fight. Hunting sends it out for gel, food and essence.', `<div class="row"><label class="f">Stance <select data-act-change="stance">${st.stances.map((x) => `<option ${x === s.behavior ? 'selected' : ''}>${x}</option>`).join('')}</select></label></div>
      <div class="row"><select data-ui="zone">${st.zones.map((z) => `<option value="${z.key}" ${z.key === zone ? 'selected' : ''}>${esc(z.name)} (${z.duration}h)</option>`).join('')}</select>
        <button class="btn small" data-act="hunt" ${free && s.state === 'idle' ? '' : 'disabled'}>🏞 Hunt</button>${s.state === 'hunting' ? '<button class="btn small" data-act="do" data-c="recall">Recall</button>' : ''}</div>`)}
    <p>${s.traits.map((t) => badge(t)).join(' ')}</p>`;
}

function dFight(s, { st, free }) {
  const el = (b) => {
    const e = st.elements.list.find((x) => x.key === b);
    const lv = s.mastery[b];
    return `<div class="row between"><span>${e.emoji} ${e.name} ${lv !== undefined ? `<b>L${lv}/${s.mastery_cap}</b>` : '<span class="mute">not attuned</span>'}</span>
      <button class="btn small" data-act="study" data-el="${b}" ${free && (lv !== undefined || s.attuned.length < s.element_slots) && lv !== s.mastery_cap ? '' : 'disabled'}>Study (${cost(st.library.study_cost)})</button></div>`;
  };
  const sp = s.spells.map((k) => { const d = st.spell_defs[k]; return d ? badge(`${elName(d.element)} ${esc(d.name)}`, 'info') : ''; }).join(' ');
  return `${sect('Skills', 'Abilities come from the class (by level), evolution, specialization, rarity and learned spells.', `<p>${s.abilities.map((a) => badge((a.element ? elName(a.element) + ' ' : '') + esc(a.name), 'info')).join(' ')}</p>`)}
    ${sect('Attributes', 'Each extra star adds a class attribute; each rarity step adds a class skill.', `<div class="stack" style="gap:3px">
      ${s.star_attrs.map((a) => `<div>${stars(a.star)} <b>${esc(a.label)}</b> +${Math.round(a.value * 100)}%</div>`).join('') || '<small class="mute">No star attributes yet.</small>'}
      ${s.next_star_attr ? `<small class="mute">Next at ${s.next_star_attr.star}★: ${esc(s.next_star_attr.label)} +${Math.round(s.next_star_attr.value * 100)}%</small>` : ''}
      ${s.rarity_skills.map((k) => `<div>✨ <b>${esc(k.name)}</b></div>`).join('')}
      ${s.next_rarity_skill ? `<small class="mute">Next rarity unlocks: ${esc(s.next_rarity_skill)}</small>` : ''}</div>`)}
    ${sect('Ascension', 'Rarity costs white gel; stars cost ascension stones. Both are permanent. The chamber destroys a slime for gel and stones.', `<div class="row">
      <button class="btn small ${s.ascend.next_rarity && st.wallet.white_gel >= s.ascend.rarity_cost ? 'primary' : ''}" data-act="slime_rarity" ${free && s.ascend.next_rarity && st.wallet.white_gel >= s.ascend.rarity_cost ? '' : 'disabled'}>✨ ${s.ascend.next_rarity ? `to ${s.ascend.next_rarity} · ${s.ascend.rarity_cost} ⚪` : 'Legendary'}</button>
      <button class="btn small ${s.ascend.star_cost && st.ascension.total >= s.ascend.star_cost ? 'primary' : ''}" data-act="slime_star" ${free && s.ascend.star_cost && st.ascension.total >= s.ascend.star_cost ? '' : 'disabled'}>🌟 ${s.ascend.star_cost ? `to ${s.stars + 1}★ · ${s.ascend.star_cost} 💎` : 'Max stars'}</button>
      <button class="btn small danger" data-act="destroy_slime" data-id="${s.id}" data-n="${esc(s.name)}" data-y="${esc(cost(s.ascend.chamber))}" ${free ? '' : 'disabled'}>🔥 Destroy</button></div>
      ${Object.keys(s.merge_bonus).length ? `<small class="mute">Merged-in stats: ${Object.entries(s.merge_bonus).filter(([, v]) => v).map(([k, v]) => `+${v} ${k}`).join(' ')}</small>` : ''}`)}
    ${sect('Class &amp; progress', 'Specialization turns cross-training into a hybrid class. Outlook forms from what the slime does most.', `<p>${s.spec ? `${s.spec.emoji} <b>${esc(s.spec.name)}</b> <small class="mute">(${esc(s.class_name)} + ${esc(s.spec.disc)})</small>` : `<b>${esc(s.class_name)}</b>`} · Descent: <b>floor ${s.progress}</b></p>
      <p>${s.outlook ? `${s.outlook.emoji} <b>${esc(s.outlook.name)}</b> <small class="mute">${esc(s.outlook.perk)}</small>` : '<span class="mute">Outlook undecided.</span>'}</p>
      ${s.spec_options.length ? `<div class="stack">${s.spec_options.map((o) => `<div class="row between panel flat"><span>${o.emoji} <b>${esc(o.name)}</b> <small class="mute">via ${esc(o.style)} (lvl ${o.level})</small><br><small class="mute">${o.ok ? esc(o.desc) : esc(o.reason)}</small></span>
        <button class="btn small ${o.ok ? 'primary' : ''}" data-act="specialize" data-id="${s.id}" data-disc="${o.discipline}" data-n="${esc(s.name)}" data-spec="${esc(o.name)}" data-cost="${esc(cost(st.spec.cost))}" ${o.ok && free && st.wallet.white_gel >= (st.spec.cost.white_gel || 0) && st.wallet.essence >= (st.spec.cost.essence || 0) ? '' : 'disabled'}>Specialize</button></div>`).join('')}</div>` : ''}`)}
    ${sect('Fighting style', 'Trained in the Academy by sparring; each style gives permanent perks.', st.disciplines.map((d) => bar(s.style[d.key], 10, '', `${d.emoji} ${d.style}${s.discipline === d.key ? ' (class)' : ''}`, `L${s.style[d.key]}`)).join(''))}
    ${sect('Elemental mastery', 'Unlocks at 3★ for any class.', s.can_master ? `<p class="mute">Attuned ${s.attuned.length}/${s.element_slots} · cap L${s.mastery_cap}</p><div class="stack">${st.elements.basics.map(el).join('')}</div><p>${sp || '<span class="mute">No spells learned.</span>'}</p>` : `<p class="mute">This slime is ${s.stars}★.</p>`)}`;
}

function dMind(s, { st, free, inDun }) {
  const em = { couple: '💘 Partner', best_friend: '💞 Best friend', friend: '🤝 Friend', rival: '⚔️ Rival' };
  return `${sect('Feelings', 'Passing feelings shift stats in battle. The Guide tab lists what raises and lowers each one.', `<div class="stack" style="gap:4px">${s.feelings.length ? s.feelings.map((f) => bar(f.value, 100, f.kind === 'bad' ? 'bad' : 'know', `${f.emoji} ${esc(f.name)}`, String(f.value))).join('') : '<small class="mute">Calm and unremarkable.</small>'}
      ${Object.keys(s.feeling_effects).length ? `<small class="mute">In battle: ${Object.entries(s.feeling_effects).map(([k, v]) => `${k.toUpperCase().slice(0, 3)} ${v > 0 ? '+' : ''}${v}%`).join(' · ')}</small>` : ''}
      ${s.awareness ? `<div>🧩 <b>Awareness: ${esc(s.awareness.name)}</b> <small class="mute">${s.awareness.points}/100${s.awareness.temperament ? ' · ' + (s.awareness.temperament === 'accept' ? 'at peace' : 'in despair') : ''}</small></div>` : ''}
      <div class="row"><button class="btn small" data-act="talk" ${inDun ? 'disabled' : ''}>💬 Talk</button></div></div>`)}
    ${sect('Relationships', 'Ties form from bonds: friends, best friends, rivals, mentors and couples. See the People tab.', `<div class="stack" style="gap:3px">${s.relations.map((r) => { const o = slimeById(r.other); if (!o) return ''; const label = r.kind === 'mentor' ? (r.mentor === s.id ? '🎓 Mentee' : '🎓 Mentor') : em[r.kind]; return `<div>${label}: <b>${esc(o.name)}</b></div>`; }).join('') || '<small class="mute">No ties yet.</small>'}
      ${s.parents.length ? `<div>🥚 Child of <b>${s.parent_names.map(esc).join(' &amp; ')}</b> · generation ${s.generation}</div>` : ''}</div>`)}
    ${sect('Experience', 'What this slime has done most shapes its outlook.', `<small class="mute">${Object.entries(s.exp).map(([k, v]) => `${k} ${v}`).join(' · ') || 'no experience yet'}</small><p class="mute">Wins ${s.wins} · merged ${s.merged}</p>`)}`;
}

function dGear(s, { st, free }) {
  const inv = Object.keys(st.gear.inventory);
  const slotOf = (k) => st.gear.all.find((g) => g.key === k);
  const slots = ['weapon', 'armor', 'charm'].map((sl) => {
    const cur = s.gear[sl] ? slotOf(s.gear[sl]) : null;
    const opts = inv.map((k) => slotOf(k)).filter((g) => g.slot === sl);
    return `<div class="row between"><span>${sl}: ${cur ? `<b>${cur.emoji} ${esc(cur.name)}</b>` : '<span class="mute">empty</span>'}</span>
      <span class="row">${opts.length ? `<select data-ui="eq_${sl}">${opts.map((g) => `<option value="${g.key}">${g.emoji} ${esc(g.name)} ×${st.gear.inventory[g.key]}</option>`).join('')}</select><button class="btn small" data-act="equip" data-slot="${sl}" ${free ? '' : 'disabled'}>Equip</button>` : ''}
      ${cur ? `<button class="btn small" data-act="unequip" data-slot="${sl}" ${free ? '' : 'disabled'}>Remove</button>` : ''}</span></div>`;
  }).join('');
  const relics = Object.values(s.items).map((it) => `<div class="row between"><span>${it.emoji} <b>${esc(it.name)}</b> ${chip(it.rarity, RARITY_CLS[it.rarity])} ${stars(it.stars)} Lv${it.level} <small class="mute">💞${it.compat}%</small></span><button class="btn small" data-act="item_unequip" data-id="${s.id}" data-slot="${it.slot}" ${free ? '' : 'disabled'}>Remove</button></div>`).join('');
  return `${sect('Gear', 'Plain armory gear. Relics (below) come from the Rift and are managed in Town → Armory & relics.', `<div class="stack">${slots}</div>`)}
    ${sect('Relics', 'Unique equipment with rarity, stars, mods and a compatibility with this slime.', relics || '<small class="mute">No relics worn.</small>')}
    ${sect('Weapons', 'A slime remembers up to three weapon families; practice sharpens them.', `<small class="mute">Favourite: ${s.weapons.favourite} · remembers ${s.weapons.memory.length}/${s.weapons.slots}</small>
      ${Object.entries(s.weapons.proficiency).map(([f, p]) => `<div>${f}${s.weapons.memory.includes(f) ? '' : ' <small class="mute">(forgotten)</small>'} <b>Lv${p.level}</b> <small class="mute">${p.uses} uses</small></div>`).join('')}
      <div class="row"><button class="btn small" data-act="slime_repair" ${free && Object.keys(s.items).length ? '' : 'disabled'}>🔧 Repair own gear</button></div>`)}`;
}

/* ---------------------------------------------------------------- gacha */
function gacha() {
  const st = S.state, r = st.rates, c = r.pull_cost;
  const rates = Object.entries(r.rarity).map(([k, v]) => `${chip(`${k} ${v}%`, k)}`).join(' ');
  const w = st.wallet;
  const b = (n, pay, label, cls) => `<button class="btn ${cls}" data-act="pull" data-n="${n}" data-pay="${pay}" ${w[pay] >= c * n ? '' : 'disabled'}>${label}<br><small>${c * n} ${RES[pay][0]}</small></button>`;
  return `<div class="panel well">
    <div class="blob big"><i></i><i></i><span class="em">🎰</span></div>
    <h2>The Last Gacha Well</h2>
    <p class="mute">Each pull wakes a slime. Odds: ${rates}. Stars 1–5 fall off exponentially (steeper for higher rarities).<br>⚪ White gel and 🟣 purple gel cost ${c} per pull — purple gel multiplies rare+ odds ×${r.purple_boost}.</p>
    <div class="row" style="justify-content:center;gap:12px">
      <button class="btn primary" data-act="pull" data-n="1" data-pay="free" ${st.free_pull.available ? '' : 'disabled'}>🎁 Free daily pull<br><small>${st.free_pull.available ? 'ready!' : `in ${st.free_pull.hours}h`}</small></button>
      ${b(1, 'white_gel', '⚪ Pull ×1', '')}${b(10, 'white_gel', '⚪ Pull ×10', '')}
      ${b(1, 'purple_gel', '🟣 Pull ×1', 'purple')}${b(10, 'purple_gel', '🟣 Pull ×10', 'purple')}
    </div></div>
  ${S.pull ? `<div class="pull-grid">${S.pull.map((s, i) => `<div class="pull-card ${s.rarity}" style="animation-delay:${i * 90}ms">${avatar(s)}<div class="nm"><b>${esc(s.name)}</b></div>
      <div class="sub mute">${esc(s.class_name)}</div><div>${stars(s.stars)}</div>${chip(s.rarity, s.rarity)}
      <div class="sub mute">${s.traits.join(', ')}</div></div>`).join('')}</div>` : ''}`;
}

/* ---------------------------------------------------------------- parties */
function mini(id, removeBtn = false) {
  const s = slimeById(id);
  if (!s) return '';
  return `<div class="mini" data-act="sel" data-id="${s.id}">${avatar(s, 'sm')}<span>${esc(s.name)}</span>${bar(s.hp, s.max_hp, 'hp')}
    ${removeBtn ? `<button class="btn small" data-act="party_remove" data-id="${s.id}" title="Remove from party">✕</button>` : ''}</div>`;
}
function parties() {
  const st = S.state;
  const freeSlimes = st.slimes.filter((s) => !s.party && !s.busy);
  const zone = ui('pzone', st.zones[0].key);
  return `<div class="panel flat row"><input type="text" data-ui="pname" placeholder="Party name" maxlength="24" value="${esc(ui('pname', ''))}">
      <button class="btn primary" data-act="party_create">➕ New party</button>
      <small class="mute">Parties are fixed at <b>${st.party_size}</b> slimes. Only full parties can battle, hunt together or scout. A slime belongs to one party.</small></div>
    <div class="grid cols2" style="margin-top:12px">${st.parties.map((p) => `<div class="panel">
      <div class="row between"><h3>${esc(p.name)} ${p.in_delve ? badge('🕳 inside dungeon', 'bad') : ''}</h3>${chip(`${p.members.length}/${st.party_size}`, p.full ? 'ok' : 'warn')}</div>
      <div class="row" style="margin:6px 0">${p.members.map((id) => mini(id, !p.in_delve)).join('') || '<small class="mute">Empty</small>'}</div>
      ${p.members.length > 1 ? `<p class="mute">Synergy <b class="${p.synergy >= 0 ? '' : ''}">${(p.synergy * 100).toFixed(1)}%</b> power (from average compatibility)</p>` : ''}
      <div class="row">
        ${!p.full && !p.in_delve ? `<button class="btn small" data-act="party_fill" data-pid="${p.id}">⚡ Fill with best free</button>` : ''}
        ${!p.in_delve ? `<select data-ui="add_${p.id}"><option value="">Add slime…</option>${freeSlimes.map((s) => `<option value="${s.id}">${esc(s.name)} (${esc(s.class_name)} Lv${s.level})</option>`).join('')}</select><button class="btn small" data-act="party_add" data-pid="${p.id}">Add</button>` : ''}
      </div>
      ${!p.in_delve ? `<div class="row" style="margin-top:8px">
        <button class="btn small" data-act="party_rest" data-pid="${p.id}" ${p.members.length ? '' : 'disabled'}>🛏️ Rest</button>
        <select data-ui="pzone">${st.zones.map((z) => `<option value="${z.key}" ${z.key === zone ? 'selected' : ''}>${esc(z.name)}</option>`).join('')}</select>
        <button class="btn small" data-act="party_hunt" data-pid="${p.id}" ${p.full ? '' : 'disabled'}>🏞 Hunt together</button>
        <button class="btn small danger" data-act="party_disband" data-pid="${p.id}">Disband</button></div>` : ''}
    </div>`).join('') || '<p class="mute">No parties yet.</p>'}</div>`;
}

/* ---------------------------------------------------------------- dungeons */
function partyOptions(key, fullOnly = true, includeDelve = false) {
  const st = S.state;
  const home = (p) => p.members.every((id) => { const m = slimeById(id); return m && !m.busy; });
  const list = st.parties.filter((p) => (includeDelve ? true : !p.in_delve && home(p)) && (!fullOnly || p.full));
  let cur = ui(key, list[0]?.id);
  if (!list.some((p) => p.id == cur)) cur = list[0]?.id;
  S.ui[key] = cur;
  return list.length ? `<select data-ui="${key}" data-rerender="1">${list.map((p) => `<option value="${p.id}" ${p.id == cur ? 'selected' : ''}>${esc(p.name)} (${p.members.length}/${st.party_size})</option>`).join('')}</select>`
    : '<small class="mute">No party is free (full and at home). Make one in the Parties tab or wait for them to return.</small>';
}
function dungeonsAll() {
  const st = S.state, d = st.dungeon;
  const delves = Object.entries(d.delves);
  const nowFloors = Object.fromEntries(delves.map(([pid, v]) => [v.floor, pid]));
  const depth = ui('depth', 3), runs = ui('runs', 5), camp = ui('camp_h', 6), tier = ui('tier', 1);
  const floorHtml = (f) => `<div class="floor ${f.boss ? 'boss' : ''} ${nowFloors[f.floor] ? 'now' : ''}"><div class="row between"><b>Floor ${f.floor}${f.boss ? ' · BOSS' : ''}${f.terrain ? ` · ${esc(f.title || f.terrain.name || '')}` : ''}</b><small class="mute">${f.knowledge.toFixed(0)}% known</small></div>
    ${bar(f.knowledge, 100, 'know')}${f.knowledge > 0 ? f.lines.map((l) => `<div class="mute">• ${esc(l)}</div>`).join('') : ''}</div>`;
  const segs = [];
  for (let i = 0; i < d.floors.length; i += d.boss_every) segs.push(d.floors.slice(i, i + d.boss_every));
  const entryParty = partyById(num(ui('dpid', st.parties.find((p) => p.full && !p.in_delve)?.id)));
  const entry = entryParty?.entry || [1];
  const dstart = entry.includes(num(ui('dstart'))) ? num(ui('dstart')) : entry[entry.length - 1];
  const sfirst = num(ui('sfirst', 1), 1), slast = num(ui('slast', sfirst), sfirst);
  const plan = S.plan && S.plan.first === sfirst && S.plan.last === slast ? S.plan : null;
  return `<div class="grid cols2">
  <div class="panel stack"><h2>🕳 The Hollow Descent</h2>
    <p class="mute">Rough, permanent death. Walk the floors <b>in order</b>. You may only <b>leave after a boss floor</b> (every ${d.boss_every}) — go home, train, study, come back stronger. <b>Each slime must have cleared the floors above</b> to enter a floor, so nobody can be carried; other parties may walk the same floors again. Best floor ever: <b>${d.best_floor}</b> of ${d.max_floor}.</p>
    ${d.cleared ? '<div class="panel flat">👑 <b>The Parched King has fallen.</b> The Descent is conquered — but the floors remain for training and scouting.</div>' : ''}
    ${delves.map(([pid, v]) => { const p = partyById(+pid); return `<div class="panel flat"><div class="row between"><b>${esc(p?.name)}</b>${chip(`floor ${v.floor} · exit after boss ${v.boss_floor}`, v.can_leave ? 'ok' : 'bad')}</div>
      <p class="mute">${v.hours}h inside · this floor ${v.knowledge.toFixed(0)}% known · clearing it takes ~${v.next_hours} game hour${v.next_hours === 1 ? '' : 's'}${S.state.clock.mode === 'live' ? ` (~${Math.max(1, Math.round(v.next_hours / S.state.clock.dungeon_rate * 60))} real min)` : ''}</p>
      ${v.ready_in > 0 ? `<div class="chip bad">⏱ busy — back in ~${Math.max(1, Math.round(v.ready_in / (S.state.clock.rate_now || 1) * 60))} real min</div>` : ''}
      <div class="row">${v.members.map((id) => mini(id)).join('')}</div>
      <div class="row" style="margin-top:6px"><button class="btn primary" data-act="delve_next" data-pid="${pid}" ${v.ready_in > 0 ? 'disabled' : ''}>⚔ Fight floor ${v.floor}</button>${cmdToggle()}
        <input type="number" min="1" max="24" value="${camp}" data-ui="camp_h" style="width:70px"><button class="btn" data-act="delve_camp" data-pid="${pid}" ${v.ready_in > 0 ? 'disabled' : ''}>⛺ Camp (h)</button>
        <button class="btn ${v.can_leave ? 'primary' : ''}" data-act="leave_dungeon" data-pid="${pid}" ${v.can_leave ? '' : 'disabled'} title="${v.can_leave ? 'Climb out' : 'Only possible at a checkpoint'}">🚪 Leave</button></div>
      ${v.can_leave ? '' : `<small class="mute">No way out until the boss of floor ${v.boss_floor} falls.</small>`}</div>`; }).join('')}
    <div class="row">${partyOptions('dpid')}
      ${entryParty ? `<label class="f">Start at floor <select data-ui="dstart">${entry.map((f) => `<option value="${f}" ${f === dstart ? 'selected' : ''}>${f}</option>`).join('')}</select></label>` : ''}
      <button class="btn danger" data-act="enter_dungeon">Enter</button></div>
    ${entryParty ? `<small class="mute">${esc(entryParty.name)}: least-travelled member has cleared floor ${entryParty.min_progress}.${entry.length === 1 ? ' They must start from floor 1.' : ''}</small>` : ''}
    <h4>What the colony knows</h4>
    ${segs.map((seg, i) => `<details ${i === 0 || nowFloors[seg[0].floor] ? 'open' : ''}><summary><b>Floors ${seg[0].floor}–${seg[seg.length - 1].floor}</b> <small class="mute">${Math.round(seg.reduce((a, f) => a + f.knowledge, 0) / seg.length)}% known</small></summary>${seg.map(floorHtml).join('')}</details>`).join('')}
  </div>
  <div class="stack">
    <div class="panel stack"><h2>🔭 Scouting</h2>
      <p class="mute">Send an exploration party to learn specific floors (1 to ${d.scout_max_floors} at a time, not only multiples of 5). Scouts must reach <b>100% of every targeted floor</b> before their time runs out — <b>otherwise the whole party is lost</b> (a half-finished note survives). Time needed grows with depth and is never exactly predictable. They must have cleared the floors above the first one. Supplies (${d.scout_food} 🍖 per budgeted hour) are paid up front, even if they finish early.</p>
      <div class="row">${partyOptions('spid')}<label class="f">Floors <input type="number" min="1" max="${d.max_floor}" value="${sfirst}" data-ui="sfirst" style="width:64px"> to <input type="number" min="1" max="${d.max_floor}" value="${slast}" data-ui="slast" style="width:64px"></label>
        <button class="btn small" data-act="scout_plan">📏 Estimate</button></div>
      ${plan ? `<div class="panel flat"><b>Estimate:</b> ~${plan.nominal}h (between ${plan.low}h and ${plan.high}h) · skill ×${plan.skill}<br>Safe budget: <b>${plan.safe}h</b> costs ${plan.food} 🍖 <button class="btn small" data-act="use_safe" data-h="${plan.safe}">use it</button></div>` : '<small class="mute">Press Estimate to see how long it should take.</small>'}
      <div class="row"><label class="f">Hour budget <input type="number" min="${d.scout_hours[0]}" max="${d.scout_hours[1]}" value="${ui('shours', plan ? plan.safe : 8)}" data-ui="shours" style="width:72px"></label>
        <button class="btn danger" data-act="scout">Send scouts</button></div></div>
    <div class="panel stack"><h2>🫧 The Gloop Pit</h2>
      ${d.pit ? `<div class="panel flat"><b>Today (day ${d.pit.day}): ${esc(d.pit.title)}</b><br><span class="mute">${d.pit.terrain.emoji} ${esc(d.pit.terrain.name)} — ${esc(d.pit.terrain.effects)}</span></div>` : ''}
      <p class="mute">A <b>committed</b> XP-farming session. The party fights all the runs (camping when hurt) unless everyone goes down. Nobody dies here, but a downed slime <b>loses XP, morale and drops its gear</b> — survivors may carry it back (more likely with high party synergy); else it stays in the Pit's lost-and-found${st.gear.pit_lost.length ? ` (${st.gear.pit_lost.length} item(s) lost there now)` : ''}.</p>
      <div class="row">${partyOptions('gpid')}
        <label class="f">Depth <input type="range" min="1" max="${d.grind_depths}" value="${depth}" data-ui="depth" data-rerender="1"> <b>${depth}</b></label>
        <label class="f">Runs <input type="number" min="1" max="60" value="${runs}" data-ui="runs" style="width:70px"></label>
        <button class="btn primary" data-act="grind">Commit</button>${cmdToggle()}</div>
      <small class="mute">Depth 3 = enemies at your party's average level; 1 is easier, 5 is harder and pays more XP.</small></div>
    <div class="panel stack"><h2>⚔ Skirmish</h2><p class="mute">One quick fight (permanent death applies). Tier 4 is a boss.</p>
      <div class="row">${partyOptions('kpid')}<select data-ui="tier">${[1, 2, 3, 4].map((t) => `<option ${t == tier ? 'selected' : ''}>${t}</option>`).join('')}</select><button class="btn" data-act="skirmish">Fight</button>${cmdToggle()}</div></div>
  </div></div>`;
}


/* ---------------------------------------------------------------- grouped views (sub-tabs) */
function cut(html, from, to) {
  const a = from ? html.indexOf(from) : 0, b = to ? html.indexOf(to) : html.length;
  return html.slice(Math.max(0, a), b < 0 ? html.length : b);
}
function dungeons() {
  const all = dungeonsAll(), v = sub('dungeons');
  const scout = '<div class="panel stack"><h2>🔭 Scouting', pit = '<div class="panel stack"><h2>🫧 The Gloop Pit', skirm = '<div class="panel stack"><h2>⚔ Skirmish';
  const left = cut(all, '<div class="panel stack"><h2>🕳', '  <div class="stack">\n    ' + scout);
  const scoutHtml = cut(all, scout, pit), pitHtml = cut(all, pit, skirm), skHtml = cut(all, skirm, null).replace(/<\/div><\/div>\s*$/, '</div>');
  const body = v === 'descent' ? `<div class="grid cols2"><div class="stack">${left}</div><div class="stack">${scoutHtml}${skHtml.endsWith('</div></div>') ? skHtml : skHtml + '</div>'}</div>`
    : v === 'pit' ? `<div class="grid cols2">${pitHtml}</div>` : riftView();
  return subnav('dungeons') + body;
}
function riftView() {
  const all = riftAll();
  const left = cut(all, '<div class="panel stack"><h2>🧭', '  <div class="stack"><div class="panel stack"><h2>🎒 Relic vault');
  return `<div class="grid cols2">${left}</div>`;
}
function town() {
  const v = sub('town');
  const all = townAll();
  const alch = '<div class="panel stack" style="margin-top:12px"><h2>⚗️', armory = '<div class="grid cols2" style="margin-top:12px">\n    <div class="panel stack"><h2>🛠️ Armory';
  let body;
  if (v === 'buildings') body = cut(all, null, alch);
  else if (v === 'alchemy') body = cut(all, alch, armory).replace('margin-top:12px', 'margin-top:0');
  else {
    const rv = riftAll();
    const relics = cut(rv, '  <div class="stack"><div class="panel stack"><h2>🎒 Relic vault', null);
    body = cut(all, armory, null) + `<div class="grid cols2" style="margin-top:12px">${relics.replace(/^\s*<div class="stack">/, '<div class="stack">')}`;
  }
  return subnav('town') + body;
}
function people() {
  const v = sub('people');
  return subnav('people') + { bonds, keeper, council, records }[v]();
}
function guide() {
  const g = S.guide;
  if (!g) return '<div class="panel"><p class="mute">Opening the booklet…</p></div>';
  const q = (ui('guide_q', '') || '').toLowerCase();
  const sections = g.map((sec) => ({ ...sec, items: sec.items.filter((i) => !q || (i.name + ' ' + i.text).toLowerCase().includes(q)) })).filter((sec) => sec.items.length);
  return `<div class="panel stack"><div class="row between"><h2>📖 The Keeper's booklet</h2><input type="search" data-ui="guide_q" data-rerender="1" value="${esc(ui('guide_q', ''))}" placeholder="Search (e.g. morale, anger, stamina)" style="max-width:280px"></div>
    <small class="mute">What every attribute means and what raises or lowers it. The numbers come straight from the game.</small></div>
  ${sections.map((sec) => `<details class="panel guide" ${q || sec.title.startsWith('Needs') ? 'open' : ''}><summary><b>${sec.icon} ${esc(sec.title)}</b> <small class="mute">${esc(sec.blurb)}</small></summary>
    <dl>${sec.items.map((i) => `<dt>${esc(i.name)}</dt><dd>${esc(i.text)}</dd>`).join('')}</dl></details>`).join('') || '<div class="panel"><p class="mute">Nothing matches.</p></div>'}`;
}

/* ---------------------------------------------------------------- academy */
function academy() {
  const st = S.state;
  const arena = ui('arena', 'sword');
  const slimeSel = (key, filter = () => true, extra = '', idx = 0) => {
    const list = st.slimes.filter(filter);
    let cur = ui(key, list[Math.min(idx, list.length - 1)]?.id);
    if (!list.some((s) => s.id == cur)) cur = list[Math.min(idx, list.length - 1)]?.id;   // a slime that left is no longer chosen
    S.ui[key] = cur;   // what the dropdown shows is what the action uses
    if (!list.length) return '<small class="mute">nobody is free</small>';
    return `<select data-ui="${key}" ${extra}>${list.map((s) => `<option value="${s.id}" ${s.id == cur ? 'selected' : ''}>${esc(s.name)} (${esc(s.class_name)} Lv${s.level} ${s.stars}★)</option>`).join('')}</select>`;
  };
  const avail = (s) => !s.busy && s.state !== 'hunting' && s.state !== 'studying';
  const lib = st.library;
  const scholars = st.slimes.filter((s) => s.can_master && avail(s));
  let lsid = num(ui('lib_s', scholars[0]?.id));
  if (!scholars.some((s) => s.id === lsid)) lsid = scholars[0]?.id;
  S.ui.lib_s = lsid;
  const ls = slimeById(lsid);
  const away = st.slimes.filter((s) => !avail(s)).length;
  const known = ls ? ls.spells : [];
  const ra = ui('res_a', known[0]), rb = ui('res_b', known[1]);
  const nameOf = (k) => st.spell_defs[k]?.name || k;
  const tg = st.buildings.find((b) => b.key === 'training_grounds');
  return `<div class="grid cols2">
  <div class="panel stack"><h2>⚔ Sparring — fighting styles</h2>
    <p class="mute">Training is not for XP. Slimes duel each other (non-lethal; the loser is left at <b>1 HP</b> — heal them at the Rest Area) to develop a <b>fighting style</b> with permanent combat perks. Costs ${cost(st.mercy.spar_cost)} per duel and ${st.mercy.train_ticks}h. Training Grounds L${tg.level}: ${esc(tg.now)}.</p>
    <div class="grid cols3">${st.disciplines.map((d) => `<div class="panel flat scard ${arena === d.key ? 'sel' : ''}" data-act="arena" data-k="${d.key}"><div style="font-size:1.6rem">${d.emoji}</div><b>${esc(d.name)}</b><div class="sub">${esc(d.style)}</div><small class="mute">${esc(d.perk)}</small></div>`).join('')}</div>
    <div class="row"><b>Duel:</b> ${slimeSel('spa', avail)} vs ${slimeSel('spb', (s) => avail(s), '', 1)}<button class="btn primary" data-act="spar">Spar</button></div>
    ${away ? `<small class="mute">${away} slime${away > 1 ? 's are' : ' is'} away (dungeon, hunt or study) and not listed.</small>` : ''}
    <div class="row"><b>Party:</b> ${partyOptions('sppid')}<button class="btn" data-act="spar_party">Everyone spars</button></div></div>

  <div class="panel stack"><h2>📚 Library</h2>
    <p class="mute">Elemental mastery unlocks at <b>3★ for any class</b> (mages get an extra element slot and study faster). Library spell slots: <b>${lib.slots}</b>${lib.tier3 ? '' : ' · Restricted Section (tier-3) needs Library L3'}.</p>
    <div class="row"><label class="f">Scholar ${slimeSel('lib_s', (s) => s.can_master && avail(s), 'data-rerender="1"') || ''}</label></div>
    ${ls ? `<div class="stack">${st.elements.basics.map((b) => {
      const e = st.elements.list.find((x) => x.key === b), lv = ls.mastery[b];
      return `<div class="row between"><span>${e.emoji} ${e.name} ${lv !== undefined ? `<b>L${lv}/${ls.mastery_cap}</b>` : '<span class="mute">not attuned</span>'}</span>
        <button class="btn small" data-act="study_lib" data-id="${ls.id}" data-el="${b}" ${avail(ls) ? '' : 'disabled'}>Study (${cost(lib.study_cost)}, 4h)</button></div>`; }).join('')}
      <p>Spells (${ls.spells.length}/${lib.slots}): ${ls.spells.map((k) => `${badge(esc(nameOf(k)), 'info')} <button class="btn small" data-act="forget" data-id="${ls.id}" data-spell="${k}">forget</button>`).join(' ') || '<span class="mute">none</span>'}</p></div>` : '<p class="mute">Pull a 3★+ slime to use the Library.</p>'}
    <h4>Spell catalogue</h4>
    <table><thead><tr><th>Spell</th><th>Tier</th><th>Effect</th><th>Cost</th><th></th></tr></thead><tbody>${lib.catalog.map((a) => `<tr><td>${elName(a.element)} <b>${esc(a.name)}</b>${a.creator ? `<br><small class="mute">by ${esc(a.creator)}</small>` : ''}</td><td>T${a.tier}</td>
      <td>${a.kind} ×${a.power}<br><small class="mute">${a.target.replace('_', ' ')} · cd ${a.cooldown}</small></td><td>${cost(lib.learn_cost[a.tier])}</td>
      <td><button class="btn small" data-act="learn" data-spell="${a.key}" ${ls && !ls.spells.includes(a.key) ? '' : 'disabled'}>Learn</button></td></tr>`).join('')}</tbody></table></div>

  <div class="panel stack"><h2>🧪 Spell lab</h2>
    <p class="mute">Fuse two learned spells of <b>different elements</b> into a brand-new spell: Fire + Wind = ⚡ Lightning, Lightning + Fire = 🔆 Plasma… Costs essence, takes hours, can fizzle and backfire (never fatal). Discovered spells join the Library for everyone.</p>
    ${known.length >= 2 ? `<div class="row"><select data-ui="res_a">${known.map((k) => `<option value="${k}" ${k === ra ? 'selected' : ''}>${esc(nameOf(k))}</option>`).join('')}</select> + <select data-ui="res_b">${known.map((k) => `<option value="${k}" ${k === rb ? 'selected' : ''}>${esc(nameOf(k))}</option>`).join('')}</select>
      <button class="btn" data-act="res_preview" data-id="${ls.id}">Preview</button></div>
      <input type="text" data-ui="res_name" placeholder="Name your spell (optional)" maxlength="28" value="${esc(ui('res_name', ''))}">
      ${S.pv ? `<div class="panel flat">→ ${S.pv.element.emoji} <b>${esc(S.pv.element.name)}</b> (tier ${S.pv.element.tier}) · ${Math.round(S.pv.chance * 100)}% success · ${S.pv.hours}h · cost ${cost(S.pv.cost)}<br>
        <button class="btn primary" data-act="research" data-id="${ls.id}">Start the experiment</button></div>` : ''}`
      : '<p class="mute">The scholar needs at least two learned spells of different elements.</p>'}</div>

  <div class="panel stack"><h2>🧬 Specialization</h2>
    <p class="mute">Cross-training builds hybrid classes; the full list of hybrids and what each needs is in the <b>Guide</b> tab (Specialization). Reach style level <b>${st.spec.style}</b> in a discipline outside your class and level <b>${st.spec.level}</b>, then specialize for ${cost(st.spec.cost)}.</p>
        <h4>Ready to specialize</h4>
    ${st.slimes.flatMap((s) => s.spec_options.filter((o) => o.ok && !s.busy).map((o) => `<div class="row between panel flat"><span>${avatar(s, 'sm')} <b>${esc(s.name)}</b> → ${o.emoji} ${esc(o.name)}</span>
      <button class="btn small primary" data-act="specialize" data-id="${s.id}" data-disc="${o.discipline}" data-n="${esc(s.name)}" data-spec="${esc(o.name)}" data-cost="${esc(cost(st.spec.cost))}" ${affordable(st.spec.cost) ? '' : 'disabled'}>Specialize</button></div>`)).join('') || '<small class="mute">Nobody qualifies yet. Spar in an arena that is not your class\'s own.</small>'}</div>
  </div>`;
}

/* ---------------------------------------------------------------- rift (adventure dungeon & relics) */
const RARITY_CLS = { common: '', uncommon: 'uncommon', rare: 'rare', epic: 'epic', legendary: 'legendary' };
function relicCard(it, holderId = null) {
  const st = S.state, a = st.gear.adventure, free = holderId ? !slimeById(holderId)?.busy : true;
  const stat = Object.entries(it.stats).map(([k, v]) => `+${v} ${k}`).join(' ');
  const dur = it.durability === null ? '<span class="chip ok">unbreakable</span>' : `<div class="mute">Durability ${it.durability}/${it.max_durability}</div>${bar(it.durability, it.max_durability, it.durability < it.max_durability * 0.3 ? 'bad' : '')}`;
  const act_ = (c, label, cs, cls = '') => `<button class="btn small ${cls}" data-act="item_cmd" data-c="${c}" data-uid="${it.uid}" ${cs && !affordable(cs) ? 'disabled' : ''} ${free ? '' : 'disabled'}>${label}${cs ? ' · ' + cost(cs) : ''}</button>`;
  const slimeSel = holderId ? '' : `<select data-ui="ie_${it.uid}">${st.slimes.filter((s) => !s.busy).map((s) => `<option value="${s.id}" ${s.id == ui('ie_' + it.uid, st.slimes[0]?.id) ? 'selected' : ''}>${esc(s.name)} (${esc(s.class_name)})</option>`).join('')}</select><button class="btn small primary" data-act="item_equip" data-uid="${it.uid}">Equip</button>`;
  return `<div class="panel flat stack"><div class="row between"><b>${it.emoji} ${esc(it.name)}</b>${chip(it.rarity, RARITY_CLS[it.rarity])}</div>
    <div>${stars(it.stars)} · Lv${it.level}/10 · ${stat}${it.compat !== null ? ` · 💞 compat ${it.compat}%` : ''}</div>
    ${it.mods.length ? `<div>${it.mods.map((m) => chip(esc(m), 'info')).join(' ')}</div>` : ''}
    ${it.ego ? `<div class="mute">👁️ Soul of ${esc(it.ego.name)} (Lv${it.ego.level}) — only 5★ legendaries may wield it.</div>` : `<small class="mute">${it.family ? it.family + ' · ' : ''}fits: ${it.fits.join(', ')}</small>`}
    ${dur}
    <div class="row">${slimeSel}
      ${it.level_cost ? act_('level_item', '⬆ Level', it.level_cost) : ''}${it.star_cost ? act_('ascend_star', '🌟 Ascend ★', it.star_cost) : ''}${it.rarity_cost ? act_('ascend_rarity', '💎 Raise rarity', it.rarity_cost) : ''}
      ${it.repair_cost ? act_('repair_item', '🛠 Repair', { white_gel: it.repair_cost }) : ''}
      ${it.salvage ? `<button class="btn small danger" data-act="item_cmd" data-c="salvage_item" data-uid="${it.uid}" data-ask="Break this relic down for ${cost(it.salvage)}?" ${free ? '' : 'disabled'}>♻ Salvage → ${cost(it.salvage)}</button>` : ''}
      ${holderId ? `<button class="btn small" data-act="item_unequip" data-id="${holderId}" data-slot="${it.slot}" ${free ? '' : 'disabled'}>Remove</button>` : ''}
      ${!it.ego && it.rarity === 'legendary' && it.stars === 5 ? `<button class="btn small danger" data-act="item_fuse" data-uid="${it.uid}">👁 Fuse ego…</button>` : ''}</div></div>`;
}
function riftAll() {
  const st = S.state, a = st.gear.adventure;
  const sel = new Set((ui('adv_ids', []) || []).map(num));
  const equipped = st.slimes.flatMap((s) => Object.values(s.items).map((it) => ({ it, s })));
  const rates = Object.entries(a.rates).map(([k, v]) => `${k} ${v}%`).join(' · ');
  return `<div class="grid cols2">
  <div class="panel stack"><h2>🧭 The Wayfarer's Rift</h2>
    <p class="mute">An adventure dungeon for <b>relics</b>. Any <b>1–${a.max_party}</b> slimes may go; monsters are <b>one level above</b> the party average (a smaller party meets fewer). Nobody dies, but a knocked-out slime loses morale and its relics are battered. Every win may drop a relic — odds are far harsher than the gacha: ${rates}. A <b>lure</b> (${a.lure_cost} 🟣 per run) multiplies the rare odds.</p>
    <div class="row">${st.slimes.filter((s) => !s.busy).map((s) => `<button class="btn small ${sel.has(s.id) ? 'primary' : ''}" data-act="adv_toggle" data-id="${s.id}">${sel.has(s.id) ? '✔ ' : ''}${esc(s.name)} · Lv${s.level}</button>`).join('') || '<small class="mute">Nobody is free.</small>'}</div>
    <div class="row"><label class="f">Runs <input type="number" min="1" max="${a.max_runs}" value="${ui('adv_runs', 5)}" data-ui="adv_runs" style="width:70px"></label>
      <button class="btn small ${ui('adv_lure', false) ? 'primary' : ''}" data-act="adv_lure">${ui('adv_lure', false) ? '✔ ' : ''}Lure (🟣)</button>
      <button class="btn primary" data-act="adventure" ${sel.size ? '' : 'disabled'}>🧭 Rift (${sel.size}/${a.max_party})</button>
      <button class="btn" data-act="quarry" ${sel.size ? '' : 'disabled'} title="Starfall Quarry: ascension stones instead of relics">💎 Quarry</button></div>
    <h4>💎 Ascension stones</h4>
    <div class="row">${Object.entries(st.ascension.stones).map(([r, n]) => `<span class="chip ${r}">${RES['stone_' + r][0]} ${n}${n >= st.ascension.merge && r !== 'legendary' ? ` <button class="btn small" data-act="merge_stones" data-r="${r}">merge ${st.ascension.merge} → 1</button>` : ''}</span>`).join('')}</div>
    <small class="mute">Total worth ${st.ascension.total} common stones. Stars cost ${Object.entries(st.ascension.star_stones).map(([k, v]) => `${k - 1}→${k}★: ${v}`).join(' · ')}. 100 stones of a rarity merge into 1 of the next. The 💎 <b>Starfall Quarry</b> drops stones (${Object.entries(st.ascension.rates).map(([k, v]) => `${k} ${v}%`).join(', ')}); other dungeons hide the odd common stone and boss hoards hold more. Destroying slimes in the 🔥 Chamber also yields stones.</small>
    <h4>Materials</h4><div class="row">${Object.entries(a.materials || st.gear.materials).map(([k, v]) => chip(`${RES[k][0]} ${RES[k][1]}: ${v}`)).join('')}</div>
    <small class="mute">Salvaging relics gives materials of their tier; the higher the level and stars, the more — and a better tier. Levelling needs materials of the relic's own tier. Star ascension (level 10) also needs Armory level ≥ the current star count; raising rarity needs ★5 Lv10 and Armory level 5.</small></div>
  <div class="stack"><div class="panel stack"><h2>🎒 Relic vault <small class="mute">(${st.gear.vault.length})</small></h2>
    ${st.gear.vault.map((it) => relicCard(it)).join('') || '<p class="mute">No relics yet. Venture into the Rift.</p>'}</div>
    <div class="panel stack"><h2>⚔ Worn relics</h2>
    ${equipped.map(({ it, s }) => `<div><small class="mute">${esc(s.name)}</small>${relicCard(it, s.id)}</div>`).join('') || '<p class="mute">Nothing worn.</p>'}</div></div></div>`;
}

/* ---------------------------------------------------------------- bonds (relationship tree) */
function famUnit(u, depth = 0) {
  const pad = depth * 20;
  return `<div style="margin-left:${pad}px">👪 ${u.names.map((n, i) => `${u.alive[i] ? '' : '🪦 '}<b>${esc(n)}</b>`).join(' & ')}</div>
    ${u.children.map((c) => `<div style="margin-left:${pad + 20}px">└ ${c.alive ? '' : '🪦 '}${esc(c.name)}</div>${c.families.map((f) => famUnit(f, depth + 2)).join('')}`).join('')}`;
}
function bonds() {
  const st = S.state, f = st.family;
  const ties = (k) => f.ties[k].map((t) => {
    const aS = slimeById(t.a), bS = slimeById(t.b);
    const extra = k === 'mentor' ? ` <small class="mute">(${esc(t.mentor === t.a ? t.a_name : t.b_name)} teaches)</small>` : '';
    const bud = k === 'couple' ? `<button class="btn small ${t.bud_in === 0 ? 'primary' : ''}" data-act="bud" data-a="${t.a}" data-b="${t.b}" ${t.bud_in === 0 && aS && bS && !aS.busy && !bS.busy && affordable(f.bud_cost) ? '' : 'disabled'}>🥚 Have a child · ${cost(f.bud_cost)}</button>${t.bud_in ? `<small class="mute"> in ${t.bud_in}d</small>` : ''}` : '';
    return `<div class="row between panel flat" style="margin:4px 0"><span>${esc(t.a_name)} ${f.kinds[k].emoji} ${esc(t.b_name)}${extra} <small class="mute">bond ${t.bond}</small></span>${bud}</div>`;
  }).join('') || '<small class="mute">None yet.</small>';
  return `<div class="grid cols2">
  <div class="stack">${['couple', 'best_friend', 'friend', 'mentor', 'rival'].map((k) => `<div class="panel stack"><h3>${f.kinds[k].emoji} ${esc(f.kinds[k].label)} <small class="mute">(${f.ties[k].length})</small></h3>${ties(k)}</div>`).join('')}</div>
  <div class="stack"><div class="panel stack"><h2>🌳 Family trees</h2>
    <p class="mute">Slimes who bond become friends and best friends; quarrels breed rivals; veterans take younger slimes under their wing; and two slimes who truly love each other can have a child — a new slime with traits, class and rarity drawn from both parents. Ties help parties (synergy, feelings) and hurt when someone is lost.</p>
    ${f.families.length ? f.families.map((r) => `<div class="panel flat">${famUnit(r)}</div>`).join('') : '<p class="mute">No children yet.</p>'}</div></div></div>`;
}

/* ---------------------------------------------------------------- keeper (the player's skills) */
function keeper() {
  const k = S.state.keeper;
  const pips = (r, m) => '●'.repeat(r) + '○'.repeat(m - r);
  return `<div class="panel stack"><div class="row between"><h2>🧙 ${esc(k.title)} <small class="mute">level ${k.level}/${k.max_level}</small></h2>${chip(`${k.points} skill point${k.points === 1 ? '' : 's'}`, k.points ? 'ok' : '')}</div>
    ${bar(k.xp, k.xp_next, 'know', `XP ${k.xp}/${k.xp_next}`)}
    <p class="mute">You earn Keeper XP by tending slimes, pulling, winning fights, clearing floors, scouting, mediating, forging, brewing and by seeing families grow. Each level gives a skill point (a bonus one every 5 levels).</p></div>
  <div class="grid cols2" style="margin-top:12px">${Object.entries(k.branches).map(([b, br]) => `<div class="panel stack"><h3>${br.emoji} ${esc(br.name)}</h3>
    ${k.skills.filter((s) => s.branch === b).map((s) => `<div class="panel flat"><div class="row between"><b>${s.emoji} ${esc(s.name)}${info(s.per_rank + ' (per rank). Needs Keeper level ' + s.level + '+, +2 for each further rank.')}</b><span>${pips(s.rank, s.max_rank)}</span></div>
      <div class="row" style="margin-top:4px"><button class="btn small ${!s.why_not ? 'primary' : ''}" data-act="keeper_learn" data-key="${s.key}" ${s.why_not ? 'disabled' : ''} title="${esc(s.why_not || '')}">${s.rank >= s.max_rank ? 'Mastered' : 'Learn'}</button>${s.why_not && s.rank < s.max_rank ? `<small class="mute">${esc(s.why_not)}</small>` : ''}</div></div>`).join('')}
    ${k.actives.filter((a) => a.branch === b).map((a) => `<div class="panel flat" style="border-left:3px solid var(--accent)"><div class="row between"><b>${a.emoji} ${esc(a.name)}${info(a.desc + (a.unlocked ? '' : ` Unlocked by ${a.needs}.`))}</b><small class="mute">every ${a.cooldown_days} day${a.cooldown_days > 1 ? 's' : ''}</small></div>
      <div class="row" style="margin-top:4px"><button class="btn small ${a.ready ? 'primary' : ''}" data-act="keeper_use" data-key="${a.key}" ${a.ready ? '' : 'disabled'}>${a.unlocked ? (a.ready ? 'Use' : 'Recovering') : 'Locked'}</button></div></div>`).join('')}</div>`).join('')}</div>`;
}

/* ---------------------------------------------------------------- town */
function townAll() {
  const st = S.state;
  const inv = Object.entries(st.gear.inventory);
  const gearOf = (k) => st.gear.all.find((g) => g.key === k);
  const stat = (o) => Object.entries(o).map(([k, v]) => `+${v} ${k}`).join(' ');
  return `<div class="grid cols3">${st.buildings.map((b) => `<div class="panel stack"><h3>${b.emoji} ${esc(b.name)} <small class="mute">L${b.level}/${b.max}</small></h3>
      ${bar(b.level, b.max)}<p>${esc(b.now)}</p>
      ${b.cost ? `<p class="mute">Next: ${esc(b.nxt)}</p><button class="btn ${affordable(b.cost) ? 'primary' : ''}" data-act="upgrade" data-key="${b.key}" ${affordable(b.cost) ? '' : 'disabled'}>⬆ Upgrade · ${cost(b.cost)}</button>` : '<p class="chip ok">Max level</p>'}</div>`).join('')}</div>
  <div class="panel stack" style="margin-top:12px"><h2>⚗️ Alchemy Lab <small class="mute">(level ${st.potions.lab}: brews up to grade ${st.potions.lab})</small></h2>
    <p class="mute">A slime brews potions from coloured herbs: 🟢 <b>green</b> = health, 🔴 <b>red</b> = strength, 🔵 <b>blue</b> = armor, 🟡 <b>yellow</b> = stamina. Each makes its basic potion; <b>two different herbs combine</b> into a further attribute (lifesteal, guard, regeneration, magic, crit, speed & evasion). The daily Pit's terrain decides which herb is plentiful; other dungeons drop a few. A magical brewer (medics and necromancers have a knack) and a roomy lab improve the odds; failures lose the gel and half the herbs.</p>
    <div class="row">${Object.entries(st.potions.herbs).map(([c, n]) => chip(`${RES['herb_' + c][0]} ${n}`)).join('')}</div>
    <div class="row"><label class="f">Brewer <select data-ui="brewer">${st.slimes.filter((x) => !x.busy).map((x) => `<option value="${x.id}">${esc(x.name)} (${esc(x.class_name)})</option>`).join('')}</select></label>
      <label class="f">Potion <select data-ui="brew_kind" data-rerender="1">${st.potions.kinds.map((k) => `<option value="${k.key}" ${k.key === ui('brew_kind', 'stamina') ? 'selected' : ''}>${k.emoji} ${esc(k.name)} — ${esc(k.effect)}</option>`).join('')}</select></label>
      <label class="f">Grade <select data-ui="brew_grade" data-rerender="1">${st.potions.grades.map((g) => `<option value="${g.grade}" ${g.grade == ui('brew_grade', 1) ? 'selected' : ''} ${g.grade > st.potions.lab ? 'disabled' : ''}>${g.grade}</option>`).join('')}</select></label>
      ${(() => { const k = st.potions.kinds.find((x) => x.key === ui('brew_kind', 'stamina')) || st.potions.kinds[0]; const gr = num(ui('brew_grade', 1), 1); const c = k.costs[gr - 1];
        return `<button class="btn primary" data-act="brew" ${affordable(c) && gr <= st.potions.lab ? '' : 'disabled'}>Brew · ${cost(c)} · ${st.potions.grades[gr - 1].brew_hours}h</button>`; })()}</div>
    <small class="mute">Grades: ${st.potions.grades.map((g) => `${g.grade}: +${Math.round(g.bonus * 100)}% for ${g.hours}h`).join(' · ')}</small>
    <div class="row">${st.potions.stock.map((p) => chip(`${(st.potions.kinds.find((k) => k.key === p.kind) || {}).emoji} ${p.kind} G${p.grade} ×${p.n}`, 'info')).join('') || '<small class="mute">No potions yet.</small>'}</div>
    <div class="row"><button class="btn small ${st.potions.autonomy ? 'primary' : ''}" data-act="autonomy">🤖 Slime autonomy: ${st.potions.autonomy ? 'on' : 'off'}</button>
      <small class="mute">When on, slimes help themselves to up to ${Math.round(st.potions.autonomy_share * 100)}% of your stocks without asking: they drink potions (tired ones stamina, hurt ones vigor, class-suited ones before a trip), mend worn gear, dress themselves from the relic vault and armory, and brew potions the colony is short of — the rest is yours.</small></div></div>
  <div class="grid cols2" style="margin-top:12px">
    <div class="panel stack"><h2>🛠️ Armory</h2><p class="mute">Gear is usable by any class. The Armory level limits which tier it sells. Gear also drops in dungeons — but a fallen slime's gear can be lost.</p>
      <table><tbody>${st.gear.shop.map((g) => `<tr><td>${g.emoji} <b>${esc(g.name)}</b><br><small class="mute">T${g.tier} ${g.slot} · ${stat(g.stats)}</small></td><td>${cost(g.cost)}</td>
        <td><button class="btn small" data-act="buy_gear" data-key="${g.key}" ${affordable(g.cost) ? '' : 'disabled'}>Buy</button></td></tr>`).join('')}</tbody></table></div>
    <div class="panel stack"><h2>🎒 Inventory</h2>
      ${inv.length ? inv.map(([k, n]) => { const g = gearOf(k); return `<div class="row between"><span>${g.emoji} ${esc(g.name)} ×${n} <small class="mute">${stat(g.stats)}</small></span></div>`; }).join('') : '<p class="mute">Empty. Equip from a slime\'s card (Colony tab).</p>'}
      ${st.gear.pit_lost.length ? `<div class="warnbox">Left behind in the Pit: ${st.gear.pit_lost.map((k) => esc(gearOf(k).name)).join(', ')}. A later Pit victory may dig it up.</div>` : ''}</div></div>`;
}

/* ---------------------------------------------------------------- council */
function council() {
  const st = S.state, c = S.council;
  const sel = (key, idx = 0) => `<select data-ui="${key}">${st.slimes.map((s) => `<option value="${s.id}" ${s.id == ui(key, st.slimes[Math.min(idx, st.slimes.length - 1)]?.id) ? 'selected' : ''}>${esc(s.name)} (${esc(s.class_name)})</option>`).join('')}</select>`;
  const comp = S.compat;
  return `<div class="grid cols2">
    <div class="panel stack"><h2>⚖️ Who to keep, who to sacrifice?</h2>
      <p class="mute">Merging consumes the donor to feed the target. It lowers everyone's morale, and <b>sacrifices compound</b>: stress now <b>${st.stress}</b> (each recent merge makes the next cost +${Math.round(st.max_stress_amp * 100)}% more and lowers the whole colony's morale target; it fades by 1 per day).</p>
      ${bar(Math.min(st.stress, 5), 5, 'morale', 'Sacrifice stress', st.stress)}
      ${c && c.rows.length ? `<table><thead><tr><th>Verdict</th><th>Slime</th><th>Score</th><th>Compat</th><th>Why</th></tr></thead><tbody>${c.rows.map((r) => `<tr><td class="verdict-${r.verdict}">${r.verdict}</td><td><a href="#" data-act="sel" data-id="${r.id}">${esc(r.name)}</a></td><td>${r.score}</td><td>${r.avg_compat >= 0 ? '+' : ''}${r.avg_compat}</td><td class="mute">${esc(r.reasons.join(', ') || '-')}</td></tr>`).join('')}</tbody></table>` : '<p class="mute">No slimes yet.</p>'}
    </div>
    <div class="stack">
      <div class="panel stack"><h3>Best merge suggestions</h3>
        ${c && c.merges.length ? c.merges.map((m) => `<div class="row between panel flat"><span><b>${esc(m.donor_name)}</b> → <b>${esc(m.target_name)}</b><br><small class="mute">+${m.xp} XP · compat ${m.compat >= 0 ? '+' : ''}${m.compat} · colony morale cost ${m.grief}</small></span>
          <button class="btn small danger" data-act="merge" data-t="${m.target}" data-d="${m.donor}" data-tn="${esc(m.target_name)}" data-dn="${esc(m.donor_name)}" data-xp="${m.xp}" data-g="${m.grief}">Merge</button></div>`).join('') : '<p class="mute">Not enough slimes.</p>'}</div>
      <div class="panel stack"><h3>Compatibility</h3><div class="row">${sel('ca')} & ${sel('cb', 1)}<button class="btn" data-act="compat">Check</button></div>
        ${comp ? `<p><b>${comp.total >= 0 ? '+' : ''}${comp.total}</b> (${comp.label}) — ${Object.entries(comp.parts).filter(([, v]) => v).map(([k, v]) => `${k} ${v >= 0 ? '+' : ''}${v}`).join(', ')}</p>` : ''}</div>
      <div class="panel stack"><h3>Quarrels</h3>${st.conflicts.length ? st.conflicts.map((q) => `<div class="row between panel flat"><span>${esc(slimeById(q.a)?.name)} vs ${esc(slimeById(q.b)?.name)}<br><small class="mute">${esc(q.reason)} · severity ${q.severity}</small></span>
        <span class="row"><button class="btn small" data-act="mediate" data-cid="${q.id}" data-m="talk">Talk</button><button class="btn small" data-act="mediate" data-cid="${q.id}" data-m="snack" ${st.wallet.food >= 2 ? '' : 'disabled'}>Snack (2🍖)</button></span></div>`).join('') : '<p class="mute">The colony is peaceful.</p>'}</div>
    </div></div>`;
}

/* ---------------------------------------------------------------- records */
function records() {
  const st = S.state;
  return `<div class="grid cols2"><div class="panel"><h2>🪦 Memorial Pond</h2>${st.graveyard.length ? st.graveyard.slice().reverse().map((g) => `<div class="row panel flat" style="margin:6px 0">${ghost(g)}<div><b>${esc(g.name)}</b> the ${esc(g.archetype)} <small class="mute">${esc(g.rarity)} ${'★'.repeat(g.stars)} · Lv${g.level}</small><br><small class="mute">hour ${g.tick}: ${esc(g.cause)}</small></div></div>`).join('') : '<p class="mute">Nobody has fallen yet.</p>'}</div>
    <div class="panel"><h2>📜 Journal</h2><div class="feed" style="max-height:60vh">${st.journal.slice().reverse().map((l) => `<div>${esc(l)}</div>`).join('') || '<small>Quiet so far.</small>'}</div></div></div>`;
}

/* ---------------------------------------------------------------- battle arena
   ARENA.render(view) turns the server's battle view into markup. It is the ONLY place that knows how a fight looks, so
   an animated arena (sprites, tweens) can replace it later without touching the rules or the commands.
   Every unit has data-unit="<index>" and classes (.alive/.dead/.acting/.targetable) a stylesheet or canvas can hook. */
const EL_EMOJI = { fire: '🔥', water: '💧', earth: '🪨', air: '🌪', light: '✨', dark: '🌑', lightning: '⚡', ice: '❄', steam: '♨', mud: '🟤', lava: '🌋', storm: '⛈' };
const ARENA = {
  unit(u, b, targetable) {
    const acting = b.waiting === u.i, pct = u.max_hp ? Math.max(0, Math.min(100, 100 * u.hp / u.max_hp)) : 0;
    const cls = ['unit', u.alive ? 'alive' : 'dead', acting ? 'acting' : '', targetable ? 'targetable' : '', u.side].join(' ');
    return `<div class="${cls}" data-unit="${u.i}" ${targetable ? `data-act="battle_target" data-i="${u.i}"` : ''}>
      <div class="uname">${esc(u.emoji)} ${esc(u.name)}${u.element ? ` <small>${EL_EMOJI[u.element] || esc(u.element)}</small>` : ''}</div>
      <div class="bar ${pct < 30 ? 'lvl-low' : pct < 60 ? 'lvl-mid' : 'lvl-ok'}"><i style="width:${pct}%"></i></div>
      <small class="mute">${u.hp}/${u.max_hp}${u.stamina != null ? ` · ⚡${u.stamina}/${u.stamina_max}` : ''}</small>
      <div class="ustat">${u.guard ? '<span>🛡</span>' : ''}${u.poison ? `<span>☠${u.poison}</span>` : ''}${!u.alive ? '<span>💀</span>' : ''}${u.minion ? '<span>👻</span>' : ''}</div></div>`;
  },
  render(b) {
    const pick = S.ui.pick ? b.abilities.find((a) => a.key === S.ui.pick) : null;
    const tside = pick ? (pick.target === 'enemy' ? 'foes' : 'party') : null;
    const col = (side) => b.units.filter((u) => u.side === side).map((u) => this.unit(u, b, !!pick && u.alive && u.side === tside && (side === 'foes' || !u.minion))).join('');
    const order = b.order.map((i) => { const u = b.units[i]; return `<span class="ord ${u.side} ${i === b.current ? 'now' : ''}" title="${esc(u.name)}">${esc(u.emoji)}</span>`; }).join('');
    const w = b.waiting != null ? b.units[b.waiting] : null;
    const abil = w ? b.abilities.map((a) => {
      const tip = `${a.kind}${a.element ? ' · ' + a.element : ''} · power ${a.power}${a.cooldown ? ` · cooldown ${a.cooldown}` : ''}${a.cost ? ` · stamina ${a.cost}` : ''}`;
      const eff = Object.values(a.eff || {});
      const hint = eff.length ? (eff.some((v) => v > 1) ? ' ▲' : eff.every((v) => v < 1) ? ' ▼' : '') : '';
      return `<button class="btn ${S.ui.pick === a.key ? 'primary' : ''}" data-act="battle_pick" data-key="${esc(a.key)}" ${a.ready ? '' : 'disabled'} title="${esc(tip)}">${esc(a.name)}${hint}${a.cooldown ? ` (${a.cooldown})` : ''}${a.winded ? ' 😮‍💨' : ''}</button>`;
    }).join('') : '';
    return `<div class="scrim" style="z-index:70"></div><div class="arena-wrap"><div class="arena panel">
      <div class="row between"><b>⚔ ${b.kind === 'pit' ? 'The Gloop Pit' : b.kind === 'delve' ? 'The Hollow Descent' : 'Skirmish'} — round ${b.round}</b>
        ${b.terrain ? chip(`${b.terrain.emoji} ${esc(b.terrain.name)}`, 'info') : ''}</div>
      ${b.terrain ? `<small class="mute">${esc(b.terrain.text)}</small>` : ''}
      <div class="turns" title="Turn order this round">${order}</div>
      <div class="field"><div class="side party">${col('party')}</div><div class="vs">VS</div><div class="side foes">${col('foes')}</div></div>
      <div class="cmd">${w ? `<div><b>${esc(w.emoji)} ${esc(w.name)}</b>'s turn ${pick ? `— choose a target for <b>${esc(pick.name)}</b> <button class="btn small" data-act="battle_cancel">cancel</button>` : '— choose an action'}</div>
        <div class="row">${abil}</div>` : '<div class="mute">The slimes are fighting on their own…</div>'}
        <div class="row" style="margin-top:6px">${w ? '<button class="btn small" data-act="battle_auto_turn" title="Let the slime decide this one turn">⏩ Auto this turn</button>' : ''}
          <button class="btn small" data-act="battle_manual" data-on="0" title="Let the slimes finish this fight (and later Pit runs) on their own">🤖 Hand over to auto</button></div></div>
      <div class="log arena-log">${logHtml(b.log.slice(-14))}</div></div></div>`;
  },
};

/* ---------------------------------------------------------------- modal */
function logHtml(lines) {
  return lines.map((l) => {
    const t = esc(l);
    if (l.startsWith('---')) return `<div class="rd">${t}</div>`;
    if (/Victory|wins the spar|cleared|defeated -/.test(l)) return `<div class="win">${t}</div>`;
    if (/Defeat|fallen|died|☠|lost/.test(l)) return `<div class="lose">${t}</div>`;
    if (/CRIT|WEAK/.test(l)) return `<div class="crit">${t}</div>`;
    if (/💚|heals|Mend/.test(l)) return `<div class="heal">${t}</div>`;
    return `<div>${t}</div>`;
  }).join('');
}
function modalHtml() {
  const m = S.modal;
  if (m.type === 'battle') {
    const i = m.i ?? m.battles.length - 1;
    const b = m.battles[i];
    return `<div class="scrim" style="z-index:55" data-act="closemodal"></div><div class="modal"><header><h3 style="margin:0">${esc(m.title)}${m.battles.length > 1 ? ` — fight ${i + 1}/${m.battles.length}` : ''}</h3><button class="btn small" data-act="closemodal">✕</button></header>
      <div class="body">${m.summary?.length ? `<div class="panel flat" style="margin-bottom:8px">${m.summary.slice(0, 12).map((l) => `<div>${esc(l)}</div>`).join('')}</div>` : ''}
      <div class="row" style="margin-bottom:6px">${b.victory ? chip('Victory', 'ok') : b.winner === 'foes' ? chip('Defeat', 'bad') : chip('Draw / duel')}${chip(`${b.rounds} rounds`)}${b.xp ? chip(`+${b.xp} XP`) : ''}${Object.entries(b.loot).map(([k, v]) => chip(`${RES[k]?.[0] || k} ${v}`)).join('')}${b.deaths.map((d) => chip('☠ ' + esc(d), 'bad')).join('')}</div>
      <div class="log">${logHtml(b.log)}</div></div>
      <footer>${m.battles.length > 1 ? `<button class="btn" data-act="battle_nav" data-d="-1">◀</button><button class="btn" data-act="battle_nav" data-d="1">▶</button>` : ''}<button class="btn primary" data-act="closemodal">Close</button></footer></div>`;
  }
  if (m.type === 'menu') {
    return `<div class="scrim" style="z-index:55" data-act="closemodal"></div><div class="modal" style="width:min(420px,94vw)"><header><h3 style="margin:0">Menu</h3><button class="btn small" data-act="closemodal">✕</button></header>
      <div class="body stack">
      <h4 style="margin:0">Time ${info('Turn-based: time passes when you press the wait buttons or act. Live: time passes by itself with the wall clock — study, hunts and brewing take real time; at home 1 game hour = 1 real hour, and while a party is in a dungeon the clock runs 3x faster. The speed presets multiply both. Offline progress is capped at 48 game hours.')}</h4>
      <div class="seg"><button class="${S.state.clock.mode === 'turn' ? 'on' : ''}" data-act="set_time" data-mode="turn">Turn-based</button><button class="${S.state.clock.mode === 'live' ? 'on' : ''}" data-act="set_time" data-mode="live" data-scale="${S.state.clock.scale}">Live (wall clock)</button></div>
      ${S.state.clock.mode === 'live' || true ? `<div class="row"><small class="mute">Speed</small><div class="seg small">${S.state.clock.scales.map((x) => `<button class="${S.state.clock.scale === x ? 'on' : ''}" data-act="set_time" data-mode="${S.state.clock.mode}" data-scale="${x}">×${x}</button>`).join('')}</div></div>` : ''}
      <h4 style="margin:6px 0 0">Helpers</h4>
      <div class="row"><button class="btn small ${S.state.auto_care ? 'primary' : ''}" data-act="autocare" title="Auto-care feeds, sleeps and rests slimes by itself">🤖 Auto-care ${S.state.auto_care ? 'on' : 'off'}</button>
        <button class="btn small ${S.state.potions.autonomy ? 'primary' : ''}" data-act="autonomy" title="Slimes use up to 66% of your stocks by themselves">🤖 Autonomy ${S.state.potions.autonomy ? 'on' : 'off'}</button></div>
      <h4 style="margin:6px 0 0">Save</h4>
      <button class="btn" data-act="export">⬇ Export save (.json)</button>
      <label class="btn" style="display:block">⬆ Import save<input type="file" accept=".json,application/json" data-import hidden></label>
      <button class="btn danger" data-act="newgame2">🗑 Start a new colony</button>
      <small class="mute">Backend: ${esc(S.backendName)}. Your colony is saved automatically in this browser.</small></div></div>`;
  }
  return '';
}

/* ---------------------------------------------------------------- actions */
const A = {
  tab: (d) => { S.tab = d.t; S.pull = d.t === 'gacha' ? S.pull : null; S.stockOpen = false;
    if (d.t === 'guide') loadGuide(); if (onCouncil()) loadCouncil(); else render(); },
  sub: (d) => { S.sub[d.t] = d.s; if (onCouncil()) loadCouncil(); else render(); },
  stock: () => { S.stockOpen = !S.stockOpen; render(); },
  info: (d, el) => toggleTip(el),
  dtab: (d) => { S.dtab = d.t; render(); },
  sel: (d) => { S.sel = num(d.id); render(); },
  closesel: () => { S.sel = null; render(); },
  closemodal: () => { S.modal = null; render(); },
  battle_nav: (d) => { const m = S.modal; m.i = Math.max(0, Math.min(m.battles.length - 1, (m.i ?? m.battles.length - 1) + num(d.d))); render(); },
  menu: () => { S.modal = { type: 'menu' }; render(); },
  set_time: (d) => act('set_time', { mode: d.mode, scale: d.scale ? Number(d.scale) : undefined }).then(() => { S.modal = { type: 'menu' }; render(); }),
  wait: (d) => act('wait', { hours: num(d.h) }, { slow: num(d.h) >= 24 }),
  autocare: () => act('auto_care', { on: !S.state.auto_care }),
  arena: (d) => { S.ui.arena = d.k; render(); },
  do: (d) => act(d.c, { id: S.sel }),
  hunt: () => act('hunt', { id: S.sel, zone: ui('zone', S.state.zones[0].key) }),
  equip: (d) => act('equip', { id: S.sel, key: ui('eq_' + d.slot, Object.keys(S.state.gear.inventory).find((k) => S.state.gear.all.find((g) => g.key === k).slot === d.slot)) }),
  unequip: (d) => act('unequip', { id: S.sel, slot: d.slot }),
  slime_rarity: () => act('slime_rarity', { id: S.sel }),
  slime_star: () => act('slime_star', { id: S.sel }),
  merge_stones: (d) => act('merge_stones', { rarity: d.r }),
  destroy_slime: (d) => confirmThen(`Destroy ${d.n} in the Destruction Chamber?\n\nYou receive ${d.y}. ${d.n} is gone forever and the colony will mourn (sacrifice stress).`, () => act('destroy_slime', { id: num(d.id) }).then(() => { S.sel = null; render(); })),
  quarry: () => { const ids = (ui('adv_ids', []) || []).map(num); act('quarry', { ids, runs: num(ui('adv_runs', 5), 5) }, { title: 'The Starfall Quarry', slow: true }).then(() => { S.ui.adv_ids = []; render(); }); },
  brew: () => act('brew', { id: num(ui('brewer', S.state.slimes.find((x) => !x.busy)?.id)), kind: ui('brew_kind', 'stamina'), grade: num(ui('brew_grade', 1), 1) }, { slow: true }),
  use_potion: () => { const [kind, grade] = String(ui('pot_sel', S.state.potions.stock[0] ? S.state.potions.stock[0].kind + ':' + S.state.potions.stock[0].grade : ':')).split(':'); act('use_potion', { id: S.sel, kind, grade: num(grade) }); },
  slime_repair: () => act('slime_repair', { id: S.sel }),
  talk: () => act('talk', { id: S.sel }),
  keeper_learn: (d) => act('keeper_learn', { key: d.key }),
  keeper_use: (d) => act('keeper_use', { key: d.key }),
  bud: (d) => confirmThen('Have a child? It costs ' + cost(S.state.family.bud_cost) + '.', () => act('bud', { a: num(d.a), b: num(d.b) })),
  autonomy: () => act('autonomy', { on: !S.state.potions.autonomy }),
  adv_lure: () => { S.ui.adv_lure = !ui('adv_lure', false); render(); },
  adv_toggle: (d) => { const ids = new Set((ui('adv_ids', []) || []).map(num)); const id = num(d.id); ids.has(id) ? ids.delete(id) : ids.add(id); S.ui.adv_ids = [...ids].slice(0, S.state.gear.adventure.max_party); render(); },
  adventure: () => { const ids = (ui('adv_ids', []) || []).map(num); const runs = num(ui('adv_runs', 5), 5);
    act('adventure', { ids, runs, lure: !!ui('adv_lure', false) }, { title: "The Wayfarer's Rift", slow: true }).then(() => { S.ui.adv_ids = []; render(); }); },
  item_equip: (d) => act('equip_item', { id: num(ui('ie_' + d.uid, S.state.slimes[0]?.id)), uid: num(d.uid) }),
  item_unequip: (d) => act('unequip_item', { id: num(d.id), slot: d.slot }),
  item_cmd: (d) => d.ask ? confirmThen(d.ask, () => act(d.c, { uid: num(d.uid) })) : act(d.c, { uid: num(d.uid) }),
  item_fuse: (d) => { const souls = S.state.slimes.filter((s) => !s.busy && s.rarity === 'legendary' && s.stars === 5);
    if (!souls.length) return toast('You need a free 5★ legendary slime to be the soul.', true);
    const best = souls.reduce((a, b) => (b.level > a.level ? b : a));
    confirmThen(`Sacrifice ${best.name} (Lv${best.level} ${best.class_name}) into this relic?\n\nIt becomes an EGO relic (stronger with the soul's level). ${best.name} is gone forever and the colony will mourn.`, () => act('fuse_ego', { uid: num(d.uid), id: best.id })); },
  study: (d) => act('study', { id: S.sel, element: d.el }),
  study_lib: (d) => act('study', { id: num(d.id), element: d.el }),
  pull: (d) => { S.pull = null; return act('pull', { n: num(d.n), pay: d.pay }); },
  party_create: () => act('party_create', { name: ui('pname', '') }).then(() => { S.ui.pname = ''; render(); }),
  party_add: (d) => { const id = num(ui('add_' + d.pid)); return id ? act('party_add', { pid: num(d.pid), id }) : toast('Choose a slime first.', true); },
  party_remove: (d) => act('party_remove', { id: num(d.id) }),
  party_fill: (d) => act('party_fill', { pid: num(d.pid) }),
  party_rest: (d) => act('party_rest', { pid: num(d.pid) }),
  party_hunt: (d) => act('party_hunt', { pid: num(d.pid), zone: ui('pzone', S.state.zones[0].key) }),
  party_disband: (d) => confirmThen('Disband this party?', () => act('party_disband', { pid: num(d.pid) })),
  enter_dungeon: () => { const pid = num(ui('dpid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); if (!pid) return toast('You need a full party.', true);
    const p = partyById(pid); const start = num(ui('dstart'), p.entry[p.entry.length - 1]);
    confirmThen(`Enter the Hollow Descent at floor ${start}?\n\nYou can only leave after a boss floor (every 5). Deaths are permanent.`, () => act('enter_dungeon', { pid, start: p.entry.includes(start) ? start : p.entry[p.entry.length - 1] })); },
  leave_dungeon: (d) => act('leave_dungeon', { pid: num(d.pid) }),
  scout_plan: async () => { const pid = num(ui('spid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); const first = num(ui('sfirst', 1), 1), last = num(ui('slast', first), first);
    if (!pid) return toast('You need a full party.', true);
    const r = await backend.call('scout_plan', { pid, first, last });
    if (r.ok) { S.plan = { ...r.result, first, last }; render(); } else toast(r.error, true); },
  use_safe: (d) => { S.ui.shours = num(d.h); render(); },
  toggle_manual: () => { S.ui.manual = !manualOn(); render(); },
  delve_next: (d) => act('delve_next', { pid: num(d.pid), manual: manualOn() }, { title: 'The Hollow Descent' }),
  battle_pick: (d) => { const b = S.state.battle; const ab = b?.abilities.find((a) => a.key === d.key); if (!ab) return;
    if (ab.target === 'enemy' || ab.target === 'ally') {
      const side = ab.target === 'enemy' ? 'foes' : 'party';
      const pool = b.units.filter((u) => u.alive && u.side === side && (side === 'foes' || !u.minion));
      if (pool.length === 1) return act('battle_act', { ability: ab.key, target: pool[0].i }, { title: kindTitle() });
      S.ui.pick = ab.key; render();
    } else act('battle_act', { ability: ab.key }, { title: kindTitle() }); },
  battle_target: (d) => { const key = S.ui.pick; S.ui.pick = null; if (key) act('battle_act', { ability: key, target: num(d.i) }, { title: kindTitle() }); },
  battle_cancel: () => { S.ui.pick = null; render(); },
  battle_auto_turn: () => { S.ui.pick = null; act('battle_auto_turn', {}, { title: kindTitle() }); },
  battle_manual: (d) => { S.ui.pick = null; S.ui.manual = d.on === '1'; act('battle_manual', { manual: d.on === '1' }, { slow: d.on !== '1', title: kindTitle() }); },
  delve_camp: (d) => act('delve_camp', { pid: num(d.pid), hours: num(ui('camp_h', 6), 6) }),
  scout: () => { const pid = num(ui('spid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); const h = num(ui('shours', 8), 8);
    const first = num(ui('sfirst', 1), 1), last = num(ui('slast', first), first);
    if (!pid) return toast('You need a full party.', true);
    confirmThen(`Scout floors ${first}-${last} with a ${h}-hour budget?\n\nIf they cannot finish ALL of it within the budget, the whole party is lost. Ambushes can kill scouts too.`, () => act('scout', { pid, first, last, hours: h }, { slow: true })); },
  specialize: (d) => confirmThen(`Specialize ${d.n} as a ${d.spec}? This is permanent and costs ${d.cost}.`, () => act('specialize', { id: num(d.id), discipline: d.disc })),
  grind: () => { const pid = num(ui('gpid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); const depth = num(ui('depth', 3), 3), runs = num(ui('runs', 5), 5);
    if (!pid) return toast('You need a full party.', true);
    confirmThen(`Commit the party to ${runs} Pit run(s) at depth ${depth}?\n\nThey only leave when finished or if everyone is knocked out. Downed slimes lose XP, morale and gear.`, () => act('grind', { pid, depth, runs, manual: manualOn() }, { slow: !manualOn(), title: 'The Gloop Pit' })); },
  skirmish: () => { const pid = num(ui('kpid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); if (!pid) return toast('You need a full party.', true);
    act('skirmish', { pid, tier: num(ui('tier', 1), 1), manual: manualOn() }, { title: 'Skirmish' }); },
  spar: () => { const a = num(ui('spa', S.state.slimes[0]?.id)), b = num(ui('spb', S.state.slimes[1]?.id)); act('spar', { a, b, discipline: ui('arena', 'sword') }, { title: 'Sparring match' }); },
  spar_party: () => { const pid = num(ui('sppid', S.state.parties.find((p) => p.full && !p.in_delve)?.id)); if (!pid) return toast('You need a full party.', true);
    act('spar_party', { pid, discipline: ui('arena', 'sword') }, { title: 'Sparring session', slow: true }); },
  learn: (d) => { const id = num(ui('lib_s', S.state.slimes.find((s) => s.can_master)?.id)); act('learn', { id, spell: d.spell }); },
  forget: (d) => act('forget', { id: num(d.id), spell: d.spell }),
  res_preview: async (d) => { const r = await backend.call('research_preview', { id: num(d.id), a: ui('res_a'), b: ui('res_b') });
    if (r.ok) { S.pv = r.result; render(); } else toast(r.error, true); },
  research: (d) => act('research', { id: num(d.id), a: ui('res_a'), b: ui('res_b'), name: ui('res_name', '') }).then(() => { S.pv = null; render(); }),
  upgrade: (d) => act('upgrade', { key: d.key }),
  buy_gear: (d) => act('buy_gear', { key: d.key }),
  mediate: (d) => act('mediate', { cid: num(d.cid), method: d.m }),
  compat: async () => { const r = await backend.call('compat', { a: num(ui('ca', S.state.slimes[0]?.id)), b: num(ui('cb', S.state.slimes[1]?.id)) });
    if (r.ok) { S.compat = r.result; render(); } else toast(r.error, true); },
  merge: (d) => confirmThen(`Sacrifice ${d.dn} to feed ${d.tn}?\n\n${d.dn} is consumed for good (+${d.xp} XP for ${d.tn}).\nThe colony's morale will fall (about ${d.g} points in total), and repeated sacrifices compound.`,
    () => act('merge', { target: num(d.t), donor: num(d.d) })),
  newgame: () => act('new_game', { seed: ui('seed') ? num(ui('seed')) : null, party_size: num(ui('psize', 5), 5) }).then(() => { S.tab = 'colony'; S.sel = null; S.pull = null; render(); }),
  newgame2: () => confirmThen('Abandon this colony and start over? The current save will be overwritten.', () => { S.modal = null; S.state = null; S.feed = []; render(); }),
  continue: async () => { const save = loadLocal(); const r = await backend.call('load', { save }); if (r.ok) { S.state = r.state; render(); } else toast(r.error, true); },
  export: () => { const save = loadLocal(); if (!save) return toast('Nothing to export yet.', true);
    const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(save)], { type: 'application/json' }));
    a.download = 'slime-gacha-save.json'; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); },
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-act]');
  if (!el || el.tagName === 'SELECT' || el.tagName === 'INPUT') return;
  const fn = A[el.dataset.act];
  if (!fn) return;
  if (el.tagName === 'A') e.preventDefault();
  if (el.disabled) return;
  e.stopPropagation();
  fn(el.dataset, el);
});
document.addEventListener('change', async (e) => {
  const t = e.target;
  if (t.dataset.sel) { S[t.dataset.sel] = t.value; render(); return; }
  if (t.dataset.ui) { S.ui[t.dataset.ui] = t.value; if (t.dataset.rerender) render(); return; }
  if (t.dataset.actChange === 'stance' && S.sel) { act('stance', { id: S.sel, stance: t.value }); return; }
  if (t.hasAttribute('data-import') && t.files[0]) {
    try { const save = JSON.parse(await t.files[0].text()); const r = await backend.call('load', { save });
      if (r.ok) { S.state = r.state; saveLocal(save); S.modal = null; toast('Save imported.'); render(); } else toast(r.error, true);
    } catch (err) { toast('That file is not a valid save.', true); }
  }
});
document.addEventListener('input', (e) => { const t = e.target; if (t.dataset.ui) { S.ui[t.dataset.ui] = t.value; if (t.dataset.rerender) render(); } });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') { if (S.modal) A.closemodal(); else if (S.sel) A.closesel(); } });

/* ---------------------------------------------------------------- boot */
/* Live time: let the wall clock move the colony while the page is open (every 30 s, when nothing is being edited). */
setInterval(async () => {
  if (!backend || !S.state || S.busy || S.modal || S.state.battle || S.state.clock.mode !== 'live') return;
  const el = document.activeElement;
  if (el && /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName)) return;
  const r = await backend.call('sync', {});
  if (!r.ok) return;
  const moved = r.state.tick !== S.state.tick;
  S.state = r.state;
  if (r.log && r.log.length) pushLog(r.log);
  if (r.save) saveLocal(r.save);
  if (moved || r.state.clock.expeditions.length || Object.keys(r.state.dungeon.delves).length) render();
}, 30000);

(async function boot() {
  const msg = (t) => { const el = document.getElementById('boot-msg'); if (el) el.textContent = t; };
  try {
    backend = await chooseBackend(msg);
    S.backendName = backend.name;
    const save = loadLocal();
    if (save) {
      const r = await backend.call('load', { save });
      if (r.ok) { S.state = r.state; pushLog(['Welcome back, Keeper.']); }
    }
    render();
  } catch (e) {
    document.getElementById('app').innerHTML = `<div class="welcome panel"><h2>Could not start the game</h2><p class="mute">${esc(e.message)}</p>
      <p>Run <code>python3 serve.py</code> in the project folder and open the printed address, or use the static build (see README).</p></div>`;
  }
})();
