/* Layered SVG slime (the "big avatar": slime card, pull reveal). Seven layers, each a <g> that can be swapped on its own:
     1 aura      rarity frame, rings, wings          (rarity)
     2 body      jelly body, class colours           (class, hybrid second colour, star shine)
     3 marks     evolution markings                  (stage: 0 none, 1 Greater runes, 2 Prime gem; capstone: cracks + crown)
     4 face      the emotion, on its own layer       (happy / angry / sad / miserable / sleeping ...)
     5 hat       class headgear                      (class; the hybrid's second class adds its horns/feature)
     6 weapon    class weapon, hybrid off-hand       (class; hybrid discipline)
     7 stars     star row, star ring, evolution badge, mastery stars
   Stars change the picture like this:  1 star = plain;  2 = a lit ring segment per star around the frame;  3 = + sparkles;
   4 = + brighter body shine;  5 = + a gold rim pulse and the star row turns gold. Rarity (not stars) decides the aura and wings.
   render(cfg) -> svg string.  cfg = { cls, rarity, stars, stage, emotion, hybrid (null | 'sword' | 'archery' | 'magic'), capstone, mastery, hybridMastery } */
const SVG_AV = (() => {
  const R = {
    common:    { label: 'Common',    border: '#94a3b8', bg1: '#1e293b', bg2: '#0f172a' },
    uncommon:  { label: 'Uncommon',  border: '#22c55e', bg1: '#064e3b', bg2: '#022c22' },
    rare:      { label: 'Rare',      border: '#38bdf8', bg1: '#0c4a6e', bg2: '#082f49' },
    epic:      { label: 'Epic',      border: '#c084fc', bg1: '#4c1d95', bg2: '#2e1065' },
    legendary: { label: 'Legendary', border: '#fbbf24', bg1: '#78350f', bg2: '#451a03' },
  };
  const C = {   // class colours: body gradient (accent, main, dark)
    barbarian: ['#fca5a5', '#ef4444', '#991b1b'], mage: ['#ddd6fe', '#8b5cf6', '#4c1d95'], medic: ['#a7f3d0', '#34d399', '#065f46'],
    rogue: ['#cbd5e1', '#64748b', '#1e293b'], ranger: ['#fef08a', '#eab308', '#713f12'], necromancer: ['#c4b5fd', '#6d28d9', '#2e1065'],
    bard: ['#fbcfe8', '#f472b6', '#9d174d'], paladin: ['#fef9c3', '#facc15', '#854d0e'], alchemist: ['#a5f3fc', '#06b6d4', '#155e75'],
    druid: ['#d9f99d', '#84cc16', '#3f6212'],
  };
  const DISC_CLASS = { sword: 'barbarian', archery: 'ranger', magic: 'mage' };     // the class whose weapon a hybrid's second discipline borrows

  const aura = (u, c, r) => {
    const m = R[c.rarity] || R.common;
    let x = '';
    if (c.rarity === 'rare') x = `<circle cx="100" cy="100" r="82" fill="none" stroke="${m.border}" stroke-width="1.5" stroke-dasharray="6 4" opacity=".7"/>`;
    if (c.rarity === 'epic') x = `<polygon points="100,10 122,78 190,100 122,122 100,190 78,122 10,100 78,78" fill="none" stroke="${m.border}" stroke-width="1.5" opacity=".65"/><circle cx="32" cy="52" r="3" fill="#e879f9"/><circle cx="168" cy="60" r="3.5" fill="#e879f9"/>`;
    if (c.rarity === 'legendary') x = `<path d="M22 95Q2 55 38 42Q22 70 40 78Q12 82 22 95Z" fill="#fde047" stroke="#f59e0b" stroke-width="1.5" opacity=".9"/><path d="M178 95Q198 55 162 42Q178 70 160 78Q188 82 178 95Z" fill="#fde047" stroke="#f59e0b" stroke-width="1.5" opacity=".9"/><circle cx="100" cy="100" r="85" fill="none" stroke="#fde047" stroke-width="2" stroke-dasharray="10 5 2 5" opacity=".85"/>`;
    return `${x}<circle cx="100" cy="100" r="76" fill="url(#${u}bg)" stroke="${m.border}" stroke-width="${c.rarity === 'legendary' ? 5 : 3.5}"/><circle cx="100" cy="100" r="70" fill="none" stroke="#fff" stroke-opacity=".12" stroke-width="1.5"/>`;
  };

  const body = (u, c, k, k2) => {
    const grow = 1 + 0.02 * (c.stars - 1), sleepy = c.emotion === 'sleeping';
    return `<g transform="translate(100 148) scale(${grow} ${sleepy ? grow * 0.9 : grow}) translate(-100 -148)">
      <ellipse cx="100" cy="147" rx="46" ry="11" fill="#000" opacity=".42"/>
      <path d="M52 126C52 75 76 62 100 62C124 62 148 75 148 126C148 145 130 148 100 148C70 148 52 145 52 126Z" fill="url(#${u}body)" stroke="${k2 ? '#fff' : k[2]}" stroke-width="2.5"/>
      <ellipse cx="78" cy="84" rx="13" ry="7" transform="rotate(-25 78 84)" fill="#fff" opacity="${c.stars >= 4 ? .62 : .45}"/><circle cx="68" cy="96" r="3.5" fill="#fff" opacity=".35"/>
      <path d="M64 138Q100 146 136 138" fill="none" stroke="#fff" stroke-width="2" opacity=".25" stroke-linecap="round"/></g>`;
  };

  const marks = (u, c, k, k2) => {
    let x = '';
    if (c.stage >= 1) x += `<path d="M57 115L70 118L62 125" fill="none" stroke="${k[0]}" stroke-width="2.5" stroke-linecap="round" opacity=".85"/><path d="M143 115L130 118L138 125" fill="none" stroke="${(k2 || k)[0]}" stroke-width="2.5" stroke-linecap="round" opacity=".85"/>`;
    if (c.stage >= 2) x += `<polygon points="100,72 106,80 100,88 94,80" fill="#fde047" stroke="#fff" stroke-width="1.2"/><circle cx="100" cy="128" r="14" fill="${k[0]}" opacity=".2"/>`;
    if (c.capstone) x += `<path d="M65 134L76 126L84 136M135 134L124 126L116 136" fill="none" stroke="#fde047" stroke-width="2"/><circle cx="72" cy="100" r="1.8" fill="#fff"/><circle cx="128" cy="96" r="2" fill="#fde047"/>`;
    return x;
  };

  const FACE = {
    happy: `<ellipse cx="70" cy="113" rx="6" ry="3.2" fill="#fb7185" opacity=".55"/><ellipse cx="130" cy="113" rx="6" ry="3.2" fill="#fb7185" opacity=".55"/>
      <circle cx="82" cy="105" r="5.5" fill="#0f172a"/><circle cx="118" cy="105" r="5.5" fill="#0f172a"/><circle cx="80" cy="103" r="2.2" fill="#fff"/><circle cx="116" cy="103" r="2.2" fill="#fff"/>
      <path d="M90 115Q100 125 110 115" fill="none" stroke="#0f172a" stroke-width="3.2" stroke-linecap="round"/>`,
    angry: `<path d="M72 96L91 103M128 96L109 103" stroke="#0f172a" stroke-width="3.8" stroke-linecap="round"/>
      <circle cx="82" cy="106" r="5.5" fill="#0f172a"/><circle cx="118" cy="106" r="5.5" fill="#0f172a"/><circle cx="82" cy="106" r="2.2" fill="#ef4444"/><circle cx="118" cy="106" r="2.2" fill="#ef4444"/>
      <path d="M88 122Q100 115 112 122Z" fill="#0f172a"/><polygon points="91,120 94,125 97,120" fill="#fff"/><polygon points="103,120 106,125 109,120" fill="#fff"/>
      <path d="M130 82L135 87L140 82M135 87V93" stroke="#ef4444" stroke-width="2" fill="none" stroke-linecap="round"/>`,
    sad: `<path d="M73 102L89 96M127 102L111 96" stroke="#0f172a" stroke-width="2.8" stroke-linecap="round"/>
      <circle cx="82" cy="107" r="5.5" fill="#0f172a"/><circle cx="118" cy="107" r="5.5" fill="#0f172a"/><circle cx="80" cy="105" r="2" fill="#fff"/><circle cx="116" cy="105" r="2" fill="#fff"/>
      <path d="M76 113Q73 121 76 124Q79 121 76 113Z" fill="#38bdf8"/><path d="M124 113Q121 121 124 124Q127 121 124 113Z" fill="#38bdf8"/>
      <path d="M91 123Q100 116 109 123" fill="none" stroke="#0f172a" stroke-width="3" stroke-linecap="round"/>`,
    miserable: `<path d="M60 85Q100 95 140 85Q144 68 100 64Q56 68 60 85Z" fill="#020617" opacity=".4"/>
      <rect x="76" y="110" width="9" height="30" rx="4" fill="#38bdf8" opacity=".85"/><rect x="115" y="110" width="9" height="30" rx="4" fill="#38bdf8" opacity=".85"/>
      <path d="M73 108Q81 100 89 108M111 108Q119 100 127 108" fill="none" stroke="#0f172a" stroke-width="3.5" stroke-linecap="round"/>
      <path d="M88 124Q100 114 112 124Q108 133 100 133Q92 133 88 124Z" fill="#450a0a" stroke="#0f172a" stroke-width="2"/>`,
    sleeping: `<path d="M73 107Q82 114 91 107M109 107Q118 114 127 107" fill="none" stroke="#0f172a" stroke-width="3.4" stroke-linecap="round"/>
      <ellipse cx="100" cy="122" rx="4" ry="3" fill="#0f172a" opacity=".8"/>
      <text x="136" y="82" font-size="14" font-weight="800" fill="#e2e8f0" opacity=".9">z</text><text x="147" y="70" font-size="10" font-weight="800" fill="#e2e8f0" opacity=".7">z</text>`,
  };

  const HAT = {
    barbarian: () => `<path d="M68 68Q45 52 52 36Q62 48 76 62Z" fill="#fef3c7" stroke="#475569" stroke-width="2"/><path d="M132 68Q155 52 148 36Q138 48 124 62Z" fill="#fef3c7" stroke="#475569" stroke-width="2"/><path d="M66 68Q100 44 134 68Z" fill="#475569" stroke="#94a3b8" stroke-width="2.5"/>`,
    mage: (t) => `<ellipse cx="100" cy="64" rx="42" ry="9" fill="#3b0764" stroke="${t}" stroke-width="2"/><path d="M68 63L102 18L118 32L132 63Z" fill="#581c87" stroke="${t}" stroke-width="2" stroke-linejoin="round"/><circle cx="102" cy="46" r="4" fill="#fde047"/>`,
    medic: (t) => `<path d="M74 64Q100 42 126 64Z" fill="#f8fafc" stroke="${t}" stroke-width="2"/><path d="M96 51H104V55H108V61H104V65H96V61H92V55H96Z" fill="#ef4444"/>`,
    druid: () => `<path d="M72 64Q55 42 46 30M58 46L46 48M64 54L58 38M128 64Q145 42 154 30M142 46L154 48M136 54L142 38" stroke="#78350f" stroke-width="4" stroke-linecap="round" fill="none"/><circle cx="82" cy="62" r="5" fill="#4ade80"/><circle cx="100" cy="60" r="6" fill="#f472b6"/><circle cx="118" cy="62" r="5" fill="#4ade80"/>`,
    rogue: (t) => `<path d="M60 72Q100 64 140 72L138 80Q100 72 62 80Z" fill="#0f172a" stroke="${t}" stroke-width="1.5"/><rect x="88" y="68" width="24" height="9" rx="2" fill="#94a3b8" stroke="#0f172a" stroke-width="1.5"/>`,
    ranger: (t) => `<path d="M64 68Q98 42 136 64L64 68Z" fill="#15803d" stroke="${t}" stroke-width="2"/><path d="M115 58Q138 35 148 26Q138 52 122 62Z" fill="#ef4444"/>`,
    necromancer: (t) => `<polygon points="70,66 78,42 90,60 100,36 110,60 122,42 130,66" fill="#1e1b4b" stroke="${t}" stroke-width="2"/><circle cx="100" cy="58" r="6" fill="#e2e8f0"/>`,
    bard: (t) => `<ellipse cx="96" cy="58" rx="34" ry="11" transform="rotate(-8 96 58)" fill="#db2777" stroke="${t}" stroke-width="2"/><path d="M118 52Q142 36 146 28Q134 48 122 56Z" fill="#fde047"/>`,
    paladin: () => `<ellipse cx="100" cy="40" rx="28" ry="6" fill="none" stroke="#fde047" stroke-width="4"/><polygon points="92,64 100,48 108,64" fill="#fde047" stroke="#78350f" stroke-width="1.5"/>`,
    alchemist: () => `<path d="M62 72Q100 66 138 72" stroke="#78350f" stroke-width="4" fill="none"/><circle cx="85" cy="68" r="10" fill="#38bdf8" stroke="#f59e0b" stroke-width="3.5"/><circle cx="115" cy="68" r="10" fill="#38bdf8" stroke="#f59e0b" stroke-width="3.5"/>`,
  };

  const weapon = (cls, big, edge) => {
    const e = edge || '#e2e8f0';
    return ({
      barbarian: `<line x1="154" y1="90" x2="146" y2="152" stroke="#78350f" stroke-width="5" stroke-linecap="round"/><path d="M152 96Q178 84 176 116Q162 114 150 108Z" fill="${big ? '#ef4444' : '#94a3b8'}" stroke="${e}" stroke-width="2"/>${big ? '<path d="M152 96Q128 84 130 116Q142 114 150 108Z" fill="#f97316" stroke="' + e + '" stroke-width="2"/>' : ''}`,
      mage: `<line x1="156" y1="82" x2="146" y2="152" stroke="#4c1d95" stroke-width="4.5" stroke-linecap="round"/><circle cx="157" cy="80" r="${big ? 11 : 8}" fill="#c084fc" stroke="#fde047" stroke-width="2"/>${big ? '<circle cx="157" cy="80" r="15" fill="none" stroke="#38bdf8" stroke-width="1.5" stroke-dasharray="4 3"/>' : ''}`,
      medic: `<line x1="154" y1="86" x2="146" y2="150" stroke="#10b981" stroke-width="4" stroke-linecap="round"/><circle cx="154" cy="84" r="8" fill="#ecfdf5" stroke="#10b981" stroke-width="2"/><path d="M151 84H157M154 81V87" stroke="#ef4444" stroke-width="2.5"/>`,
      druid: `<path d="M146 150Q158 118 150 88Q164 78 168 88" fill="none" stroke="#65a30d" stroke-width="5" stroke-linecap="round"/><circle cx="158" cy="85" r="6" fill="#4ade80"/>`,
      rogue: `<line x1="146" y1="138" x2="168" y2="96" stroke="#0f172a" stroke-width="4"/><polygon points="152,126 172,88 160,130" fill="#cbd5e1" stroke="${e}" stroke-width="1.5"/>`,
      ranger: `<path d="M148 82Q178 115 148 148" fill="none" stroke="#ca8a04" stroke-width="4.5" stroke-linecap="round"/><line x1="148" y1="84" x2="148" y2="146" stroke="#e2e8f0" stroke-width="1.2"/>`,
      necromancer: `<line x1="154" y1="82" x2="144" y2="152" stroke="#312e81" stroke-width="4.5"/><path d="M154 86Q186 82 178 106Q166 94 152 94Z" fill="#a855f7" stroke="${e}" stroke-width="1.5"/>`,
      bard: `<path d="M144 102Q144 134 156 134Q168 134 168 102" fill="none" stroke="#fbbf24" stroke-width="4"/><line x1="152" y1="102" x2="152" y2="132" stroke="#f8fafc" stroke-width="1"/><line x1="160" y1="102" x2="160" y2="132" stroke="#f8fafc" stroke-width="1"/>`,
      paladin: `<path d="M142 102H168V124Q155 142 142 124Z" fill="#facc15" stroke="#fff" stroke-width="2"/><path d="M155 107V130M147 116H163" stroke="#78350f" stroke-width="2.5"/>`,
      alchemist: `<path d="M150 96H160L168 124Q155 134 142 124Z" fill="#06b6d4" stroke="#e2e8f0" stroke-width="2"/><circle cx="155" cy="116" r="3" fill="#fff"/>`,
    })[cls] || '';
  };

  const star = (x, y, s, f) => `<g transform="translate(${x} ${y}) scale(${s})"><polygon points="0,-8 2.4,-2.5 8.3,-1.8 3.9,2.2 5.1,8 0,5 -5.1,8 -3.9,2.2 -8.3,-1.8 -2.4,-2.5" fill="${f}" stroke="#78350f" stroke-width="1.2"/></g>`;

  const stars = (c, m) => {
    const n = Math.max(1, Math.min(5, c.stars)), gold = n >= 5 ? '#fde047' : '#fbbf24';
    let x = '';
    for (let i = 0; i < 5; i++) {                                    // star ring: one lit segment of the frame per star
      const a0 = -90 + i * 72 + 5, a1 = -90 + (i + 1) * 72 - 5, p = (a) => `${100 + 76 * Math.cos(a * Math.PI / 180)} ${100 + 76 * Math.sin(a * Math.PI / 180)}`;
      x += `<path d="M${p(a0)}A76 76 0 0 1 ${p(a1)}" fill="none" stroke="${i < n ? gold : '#475569'}" stroke-width="${i < n ? 5 : 2}" stroke-linecap="round" opacity="${i < n ? 1 : .5}"/>`;
    }
    if (n >= 3) x += `<path d="M30 40l1.5 3.5 3.5 1.5-3.5 1.5L30 50l-1.5-3.5L25 45l3.5-1.5z" fill="#fff" opacity=".9"/><path d="M172 150l1.2 2.8 2.8 1.2-2.8 1.2-1.2 2.8-1.2-2.8-2.8-1.2 2.8-1.2z" fill="#fde047"/>`;
    if (n >= 5) x += `<circle cx="100" cy="100" r="79" fill="none" stroke="#fde047" stroke-width="1.6" opacity=".8"/>`;
    for (let i = 0; i < n; i++) x += star(100 + (i - (n - 1) / 2) * 17, 176 - Math.abs(i - (n - 1) / 2) * 2.5, 1, gold);
    if (c.stage > 0) {
      x += `<g transform="translate(34 34)"><circle r="14" fill="#0f172a" stroke="${m.border}" stroke-width="2"/>`
        + (c.stage === 1 ? '<path d="M-5 3L0-3L5 3" fill="none" stroke="#38bdf8" stroke-width="2.5" stroke-linecap="round"/>'
          : '<path d="M-5 5L0-1L5 5" fill="none" stroke="#c084fc" stroke-width="2.2" stroke-linecap="round"/><path d="M-5 0L0-6L5 0" fill="none" stroke="#fde047" stroke-width="2.2" stroke-linecap="round"/>') + '</g>';
    }
    if (c.mastery) x += star(168, 34, 1.5, '#ffd45a');
    if (c.hybridMastery) x += star(132, 34, 1.5, '#5fe0d0');
    return x;
  };

  function render(c) {
    const u = 'sv' + Math.random().toString(36).slice(2, 8) + '_', m = R[c.rarity] || R.common, k = C[c.cls] || C.barbarian;
    const hyb = c.hybrid ? DISC_CLASS[c.hybrid] : null, k2 = hyb ? C[hyb] : null;
    const trim = c.capstone ? '#fde047' : c.stage >= 2 ? '#e2e8f0' : '#94a3b8';
    const edge = c.capstone ? '#fde047' : '#e2e8f0';
    return `<svg viewBox="0 0 200 200" width="100%" height="100%" xmlns="http://www.w3.org/2000/svg" class="slime-svg" role="img" aria-label="${c.cls} slime" style="overflow:visible">
      <defs><radialGradient id="${u}bg" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="${m.bg1}"/><stop offset="1" stop-color="${m.bg2}"/></radialGradient>
      <linearGradient id="${u}body" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="${k[0]}"/><stop offset=".35" stop-color="${k[1]}"/><stop offset=".7" stop-color="${k2 ? k2[1] : k[2]}"/><stop offset="1" stop-color="${k2 ? k2[2] : k[2]}"/></linearGradient></defs>
      <g class="l-aura">${aura(u, c)}</g>
      <g class="l-body">${body(u, c, k, k2)}</g>
      <g class="l-marks">${marks(u, c, k, k2)}</g>
      <g class="l-face">${FACE[c.emotion] || FACE.happy}</g>
      <g class="l-hat">${(c.capstone ? '<path d="M78 32L88 18L100 28L112 18L122 32" fill="none" stroke="#fde047" stroke-width="3"/>' : '') + (HAT[c.cls] ? HAT[c.cls](trim) : '') + (hyb && HAT[hyb] && c.stage >= 1 ? '' : '')}</g>
      <g class="l-weapon">${weapon(c.cls, c.stage >= 2, edge)}${hyb ? `<g transform="translate(200 0) scale(-1 1)">${weapon(hyb, c.stage >= 2, edge)}</g>` : ''}</g>
      <g class="l-stars">${stars(c, m)}</g>
    </svg>`;
  }
  return { render, classes: Object.keys(C), rarities: Object.keys(R), emotions: Object.keys(FACE) };
})();
