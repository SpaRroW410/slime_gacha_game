/* Localisation. Catalogs map the English text to a translation (gettext style): web/lang_<code>.js calls I18N.add(code, name, map).
   Keys may contain {n}-style placeholders ("{n}h left"). I18N.apply(root) translates the rendered page (text nodes and title /
   aria-label / placeholder attributes); I18N.tr(text) translates one message (toasts, the event log). Anything missing from a catalog
   stays English, so a language can grow a little at a time. A leading emoji or symbol is kept as it is. */
const I18N = {
  lang: (() => { try { return localStorage.getItem('slimegacha.lang') || 'en'; } catch (e) { return 'en'; } })(),
  langs: { en: 'English' }, cats: {}, pats: {},
  add(code, name, map) {
    this.langs[code] = name; this.cats[code] = map;
    this.pats[code] = Object.keys(map).filter((k) => k.includes('{'))
      .map((k) => ({ re: new RegExp('^' + k.replace(/[.*+?^$()|[\]\\]/g, '\\$&').replace(/\{(\w+)\}/g, '(?<$1>.+?)') + '$'), out: map[k] }));
  },
  set(code) { this.lang = this.langs[code] ? code : 'en'; try { localStorage.setItem('slimegacha.lang', this.lang); } catch (e) { /* ignore */ } },
  one(s, cat, pats) {
    if (cat[s] != null) return cat[s];
    for (const p of pats) { const m = p.re.exec(s); if (m) return p.out.replace(/\{(\w+)\}/g, (_, k) => this.tr(m.groups[k])); }
    return null;
  },
  tr(text) {
    const cat = this.cats[this.lang];
    if (!cat || !text) return text;
    const s = String(text), core = s.trim();
    if (!core) return s;
    const pats = this.pats[this.lang];
    let r = this.one(core, cat, pats);
    if (r == null) {
      const m = /^([^\p{L}\p{N}{]*)([\s\S]*)$/u.exec(core);
      if (m && m[1] && m[2]) { const t = this.one(m[2], cat, pats); if (t != null) r = m[1] + t; }
    }
    return r == null ? s : s.replace(core, r);
  },
  apply(root) {
    if (!this.cats[this.lang] || !root) return;
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, { acceptNode: (n) => (n.parentElement && /^(SCRIPT|STYLE|TEXTAREA)$/.test(n.parentElement.tagName) ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT) });
    const nodes = []; while (w.nextNode()) nodes.push(w.currentNode);
    for (const n of nodes) { const t = this.tr(n.nodeValue); if (t !== n.nodeValue) n.nodeValue = t; }
    root.querySelectorAll('[title],[aria-label],[placeholder]').forEach((el) => {
      for (const a of ['title', 'aria-label', 'placeholder']) { const v = el.getAttribute(a); if (v) { const t = this.tr(v); if (t !== v) el.setAttribute(a, t); } }
    });
  },
};
