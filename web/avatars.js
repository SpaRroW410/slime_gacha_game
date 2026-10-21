/* Slime avatars. The body and the face stay CSS (so moods and feelings keep showing); the class gear is SVG drawn in a
   64 x 64 box over the slime and grows with rarity:
     common     a basic hat
     uncommon   + the class item (weapon, tool)
     rare       a better hat and item
     epic       the elite hat, a coloured aura and particles
     legendary  + a stronger item, wings and sparkles
   Gear never covers the face: hats stay above y = 27 (the eyes start near y = 31) and items stay right of x = 47.
   AV.gear(cls, rarity) returns { back, front } SVG strings (back sits behind the body, front on top). A class without
   gear here (a mod) gets {} and the avatar falls back to its emoji. */
const AV = (() => {
  const TIER = { common: 0, uncommon: 1, rare: 2, epic: 3, legendary: 4 };
  const steel = '#b7c0cc', steelD = '#6f7887', gold = '#f4c542', goldD = '#c98d1c', wood = '#94612f', woodD = '#5e3b1a';

  /* hats: [basic, better, elite] */
  const HAT = {
    barbarian: [
      `<path d="M18 25c0-8 6-12 14-12s14 4 14 12z" fill="${steel}"/><rect x="17" y="24" width="30" height="3" rx="1.5" fill="${steelD}"/>
       <path d="M19 19c-5-1-7-6-6-10 3 2 5 4 7 7zM45 19c5-1 7-6 6-10-3 2-5 4-7 7z" fill="#f1e6cf"/>`,
      `<path d="M17 25c0-9 7-13 15-13s15 4 15 13z" fill="${steel}"/><rect x="16" y="24" width="32" height="3" rx="1.5" fill="${steelD}"/>
       <rect x="30.5" y="13" width="3" height="12" fill="${steelD}"/><path d="M18 18c-7-1-10-8-8-14 4 3 7 6 9 10zM46 18c7-1 10-8 8-14-4 3-7 6-9 10z" fill="#f4ead6" stroke="#bfae8c" stroke-width=".8"/>`,
      `<path d="M16 25c0-10 7-14 16-14s16 4 16 14z" fill="#a33b2a"/><rect x="15" y="23.5" width="34" height="3.5" rx="1.7" fill="${gold}"/>
       <path d="M20 12l3-7 3 6 3-8 3 8 3-8 3 8 3-6 3 7z" fill="${gold}" stroke="${goldD}" stroke-width=".8"/>
       <path d="M17 17c-8-1-11-9-9-15 5 3 8 7 10 11zM47 17c8-1 11-9 9-15-5 3-8 7-10 11z" fill="#ffd27a" stroke="#d07a1e" stroke-width=".8"/>
       <circle cx="32" cy="18" r="2.3" fill="#ff5a3c"/>`,
    ],
    mage: [
      `<path d="M32 2l11 20H21z" fill="#7a63e0"/><rect x="16" y="21" width="32" height="5" rx="2.5" fill="#4d3fa3"/><circle cx="33" cy="11" r="1.6" fill="#ffe27a"/>`,
      `<path d="M30 0c4 2 13 13 15 22H19z" fill="#6a52d6"/><rect x="14" y="21" width="36" height="5" rx="2.5" fill="#3f3290"/>
       <path d="M27 12l1 2 2 .3-1.5 1.4.4 2.1-1.9-1-1.9 1 .4-2.1-1.5-1.4 2-.3z" fill="#ffe27a"/><circle cx="36" cy="16" r="1.2" fill="#ffe27a"/><circle cx="33" cy="7" r="1" fill="#fff"/>`,
      `<path d="M29 0c6 2 15 13 17 22H18z" fill="#2c2f86"/><rect x="13" y="21" width="38" height="5.5" rx="2.7" fill="${gold}"/>
       <circle cx="29" cy="13" r="1.3" fill="#fff"/><circle cx="35" cy="9" r="1" fill="#9fd4ff"/><circle cx="36" cy="16" r="1.6" fill="#ff9be8"/>
       <path d="M30 2c-3 1-5 3-5 5" stroke="#9fd4ff" stroke-width="1" fill="none"/><circle cx="32" cy="23.7" r="2" fill="#7fe0ff"/>`,
    ],
    medic: [
      `<rect x="19" y="15" width="26" height="10" rx="4" fill="#fff" stroke="#d9dee5"/><path d="M30.5 16.5h3v7h-3zM28.5 18.5h7v3h-7z" fill="#e5484d"/>`,
      `<path d="M17 25c0-8 6-12 15-12s15 4 15 12z" fill="#fff" stroke="#d9dee5"/><rect x="16" y="23" width="32" height="3" rx="1.5" fill="#7fd6a8"/>
       <path d="M30 14.5h4v7h-4zM28.5 16h7v4h-7z" fill="#e5484d"/>`,
      `<path d="M17 25c0-8 6-12 15-12s15 4 15 12z" fill="#eafff3" stroke="#9fe3bf"/><rect x="16" y="23" width="32" height="3" rx="1.5" fill="${gold}"/>
       <path d="M24 13l3-6 3 5 2-7 2 7 3-5 3 6z" fill="#5fd39a" stroke="#2f9d68" stroke-width=".8"/><path d="M30 15h4v6.5h-4zM28.7 16.3h6.6v3.9h-6.6z" fill="#e5484d"/>`,
    ],
    rogue: [
      `<path d="M16 22c2-5 9-7 16-7s14 2 16 7l-2 4H18z" fill="#3b4250"/><path d="M46 21c4 0 7 2 9 5-3 0-6-1-8-2z" fill="#3b4250"/>`,
      `<path d="M12 30C11 14 21 7 32 7s21 7 20 23l-4-2c-1-9-7-13-16-13s-15 4-16 13z" fill="#353b48"/><path d="M20 15c3-3 7-4 12-4s9 1 12 4" stroke="#4d5566" stroke-width="2" fill="none"/>`,
      `<path d="M10 32C9 13 20 5 32 5s23 8 22 27l-5-3c-1-10-7-15-17-15s-16 5-17 15z" fill="#2a2140"/><path d="M15 26c2-9 8-14 17-14s15 5 17 14" stroke="#9a6bff" stroke-width="1.4" fill="none"/>
       <path d="M30 5l2-4 2 4z" fill="#9a6bff"/>`,
    ],
    ranger: [
      `<path d="M17 25c0-7 7-11 15-11s15 4 15 11z" fill="#4f8a4a"/><path d="M43 18c4-6 8-8 11-8-2 4-5 7-10 10z" fill="#e8d36b"/>`,
      `<path d="M15 26c1-9 8-14 17-14s16 5 17 14z" fill="#8a5a33"/><rect x="15" y="23" width="34" height="3" rx="1.5" fill="#5e3b1a"/>
       <path d="M42 16c5-7 10-9 14-9-2 5-6 8-12 11z" fill="#e8d36b"/><path d="M40 17c4-6 9-8 12-8" stroke="#c95b3a" stroke-width="1.2" fill="none"/>`,
      `<path d="M13 29C13 15 21 9 32 9s19 6 19 20l-4-2c-1-7-6-11-15-11s-14 4-15 11z" fill="#2f7a46"/><rect x="16" y="22" width="32" height="3" rx="1.5" fill="${gold}"/>
       <path d="M44 14c6-8 11-10 15-10-2 6-7 9-13 12z" fill="#ffe27a"/><path d="M29 12l3-5 3 5-3 2z" fill="${gold}"/>`,
    ],
    necromancer: [
      `<path d="M20 25l2-8 4 4 3-7 3 6 3-6 3 7 4-4 2 8z" fill="#7b4ba3"/>`,
      `<path d="M18 25l2-10 4 5 3-9 5 7 5-7 3 9 4-5 2 10z" fill="#c9cdd6" stroke="#8a90a0" stroke-width=".8"/><circle cx="32" cy="21" r="2" fill="#8d5cff"/>`,
      `<path d="M17 25l2-11 4 5 3-10 6 8 6-8 3 10 4-5 2 11z" fill="#d8dbe2" stroke="#7a8090" stroke-width=".8"/>
       <circle cx="32" cy="12" r="4.2" fill="#f4f1e8"/><circle cx="30.4" cy="11.6" r="1.1" fill="#2a1d3a"/><circle cx="33.6" cy="11.6" r="1.1" fill="#2a1d3a"/><rect x="30.3" y="14.6" width="3.4" height="1.6" fill="#f4f1e8"/>
       <circle cx="22" cy="21" r="1.5" fill="#b07cff"/><circle cx="42" cy="21" r="1.5" fill="#b07cff"/>`,
    ],
    bard: [
      `<path d="M16 24c1-6 8-9 16-9 7 0 13 3 15 8z" fill="#e0679d"/><circle cx="32" cy="14.5" r="1.8" fill="#b8457a"/>`,
      `<path d="M15 24c1-7 9-10 17-10 8 0 14 3 16 9z" fill="#c8384a"/><path d="M38 15c4-6 9-9 14-9-2 4-6 8-12 10z" fill="#f4d35e"/><rect x="16" y="22.5" width="32" height="2.5" rx="1.2" fill="#7d1f2c"/>`,
      `<path d="M12 24c2-8 10-12 20-12s18 4 20 11z" fill="#7a2e6e"/><rect x="13" y="22" width="38" height="3" rx="1.5" fill="${gold}"/>
       <path d="M36 13c3-9 10-13 18-13-3 6-8 11-15 14z" fill="#ff9bd2"/><path d="M38 14c5-7 11-10 17-10-3 5-9 9-15 11z" fill="#ffe27a" opacity=".85"/>`,
    ],
    paladin: [
      `<path d="M19 25c0-8 6-12 13-12s13 4 13 12z" fill="${steel}"/><rect x="18" y="23.5" width="28" height="3" rx="1.5" fill="${steelD}"/><circle cx="32" cy="13" r="1.8" fill="${steelD}"/>`,
      `<path d="M17 27c0-10 7-15 15-15s15 5 15 15z" fill="#c7ccd6"/><rect x="17" y="24.5" width="30" height="2.5" rx="1" fill="#5a6270"/>
       <rect x="30.5" y="12" width="3" height="12" fill="#8a93a3"/><path d="M29 12c0-5 2-8 3-9 1 1 3 4 3 9z" fill="#d9454a"/>`,
      `<path d="M17 27c0-10 7-15 15-15s15 5 15 15z" fill="${gold}" stroke="${goldD}"/><rect x="17" y="24.5" width="30" height="2.5" rx="1" fill="${goldD}"/>
       <path d="M17 19c-6-2-9-6-10-11 4 1 8 3 10 6zM47 19c6-2 9-6 10-11-4 1-8 3-10 6z" fill="#fff6d6" stroke="${goldD}" stroke-width=".7"/>
       <ellipse cx="32" cy="7" rx="9" ry="2.4" fill="none" stroke="#ffe27a" stroke-width="1.6"/>`,
    ],
    alchemist: [
      `<rect x="17" y="18" width="30" height="5" rx="2.5" fill="#5b4a3a"/><circle cx="25" cy="20.5" r="4" fill="#7fd6e3" stroke="#c99a3f" stroke-width="1.6"/><circle cx="39" cy="20.5" r="4" fill="#7fd6e3" stroke="#c99a3f" stroke-width="1.6"/>`,
      `<path d="M23 15l9-13 9 13z" fill="#3f7fb3"/><rect x="15" y="14" width="34" height="3" rx="1.5" fill="#2c5f8a"/>
       <rect x="17" y="19" width="30" height="5" rx="2.5" fill="#5b4a3a"/><circle cx="25" cy="21.5" r="4" fill="#9ff0f5" stroke="#c99a3f" stroke-width="1.6"/><circle cx="39" cy="21.5" r="4" fill="#9ff0f5" stroke="#c99a3f" stroke-width="1.6"/>`,
      `<path d="M21 15c3-9 8-14 13-15-1 4 2 10 9 15z" fill="#245a8f"/><rect x="13" y="13.5" width="38" height="3.5" rx="1.7" fill="${gold}"/>
       <circle cx="35" cy="8" r="1.4" fill="#ffe27a"/><circle cx="30" cy="11" r="1" fill="#9ff0f5"/>
       <rect x="17" y="19" width="30" height="5" rx="2.5" fill="#4a3829"/><circle cx="25" cy="21.5" r="4.2" fill="#b8fff2" stroke="${gold}" stroke-width="1.8"/><circle cx="39" cy="21.5" r="4.2" fill="#b8fff2" stroke="${gold}" stroke-width="1.8"/>`,
    ],
    druid: [
      `<path d="M32 16c-1-5 1-9 5-11 0 4-2 8-5 11z" fill="#4fae4a"/><path d="M32 16c-3-3-7-4-10-3 2 3 6 4 10 3z" fill="#6fcf5a"/><rect x="31.2" y="15" width="1.6" height="6" fill="#3f7d3a"/>`,
      `<path d="M17 23c4-4 9-6 15-6s11 2 15 6" stroke="#4f8f3a" stroke-width="3" fill="none"/>
       <circle cx="20" cy="21" r="2.4" fill="#ff9bc4"/><circle cx="26" cy="18" r="2.4" fill="#ffe27a"/><circle cx="32" cy="17" r="2.4" fill="#fff"/><circle cx="38" cy="18" r="2.4" fill="#ffb15c"/><circle cx="44" cy="21" r="2.4" fill="#ff9bc4"/>`,
      `<path d="M22 22c-4-5-6-11-3-17M24 15c-4-1-7-3-8-6M42 22c4-5 6-11 3-17M40 15c4-1 7-3 8-6" stroke="#8a5a33" stroke-width="2.4" fill="none" stroke-linecap="round"/>
       <path d="M17 23c4-4 9-6 15-6s11 2 15 6" stroke="#3f8f3a" stroke-width="3" fill="none"/><path d="M20 6c-2-3-1-6 2-7 1 3 0 5-2 7zM44 6c2-3 1-6-2-7-1 3 0 5 2 7z" fill="#6fcf5a"/>
       <circle cx="26" cy="18" r="2.2" fill="#ffe27a"/><circle cx="32" cy="17" r="2.4" fill="#fff"/><circle cx="38" cy="18" r="2.2" fill="#ff9bc4"/>`,
    ],
  };

  /* class items held at the right side: [basic, better, legendary] */
  const ITEM = {
    barbarian: [
      `<rect x="52" y="30" width="2.6" height="28" rx="1.2" fill="${wood}" transform="rotate(20 53 44)"/><path d="M53 29c5 0 8 3 8 8-3-1-6-2-8-4z" fill="${steel}" stroke="${steelD}" stroke-width=".8"/>`,
      `<rect x="52" y="27" width="2.8" height="32" rx="1.4" fill="${woodD}" transform="rotate(18 53 43)"/><path d="M54 25c6 0 9 4 9 9-4-1-7-2-9-5zM52 26c-5 1-7 4-7 8 3-1 6-3 7-5z" fill="${steel}" stroke="${steelD}" stroke-width=".8"/>`,
      `<rect x="52" y="25" width="3" height="34" rx="1.5" fill="${woodD}" transform="rotate(18 53 43)"/><path d="M54 22c7 0 10 5 10 11-5-1-8-3-10-6zM52 23c-6 1-8 5-8 10 4-1 7-3 8-6z" fill="${gold}" stroke="#d0461e" stroke-width="1"/>
       <path d="M58 21c2-3 1-6-1-8 4 1 6 5 4 9zM46 22c-2-3-1-5 1-7-4 1-5 4-3 7z" fill="#ff7a2e" opacity=".9"/>`,
    ],
    mage: [
      `<rect x="52" y="34" width="2.4" height="22" rx="1.2" fill="${wood}" transform="rotate(14 53 45)"/><circle cx="55.5" cy="33" r="2.8" fill="#c39bff"/>`,
      `<rect x="53" y="22" width="2.6" height="36" rx="1.3" fill="${woodD}"/><circle cx="54.3" cy="21" r="4" fill="#6fd3ff" stroke="#c9a14b" stroke-width="1.2"/>`,
      `<rect x="53" y="20" width="2.8" height="38" rx="1.4" fill="#3a2a6a"/><path d="M54.4 10l3 6 6 1-4.5 4 1 6-5.5-3-5.5 3 1-6-4.5-4 6-1z" fill="${gold}" stroke="#fff3b0" stroke-width=".6"/><circle cx="54.4" cy="18.5" r="2.4" fill="#9fe8ff"/>`,
    ],
    medic: [
      `<path d="M53 42h6v3l2 3v8h-10v-8l2-3z" fill="#e8f7ff" stroke="#9cc" stroke-width=".7"/><rect x="51" y="49" width="10" height="7" rx="1.5" fill="#5fd39a"/><rect x="53" y="40" width="6" height="2.4" fill="${woodD}"/>`,
      `<rect x="48" y="42" width="15" height="12" rx="2.5" fill="#a0673a" stroke="#6b3f1f"/><rect x="52.5" y="39.5" width="6" height="3" rx="1.2" fill="none" stroke="#6b3f1f" stroke-width="1.2"/><path d="M54.3 44.5h2.4v7h-2.4zM52 46.8h7v2.4h-7z" fill="#fff"/>`,
      `<rect x="48" y="42" width="15" height="12" rx="2.5" fill="#fff" stroke="${gold}" stroke-width="1.2"/><path d="M54.3 44.5h2.4v7h-2.4zM52 46.8h7v2.4h-7z" fill="#e5484d"/>
       <path d="M55 36c-1.5-2-4.5-1-3.5 1.5L55 41l3.5-3.5c1-2.5-2-3.5-3.5-1.5z" fill="#ff7aa8"/>`,
    ],
    rogue: [
      `<path d="M56 30l2 2-6 18-2-1z" fill="#d8dee8" stroke="#8b95a5" stroke-width=".6"/><rect x="48" y="48" width="6" height="2.4" rx="1" fill="${woodD}" transform="rotate(-70 51 49)"/>`,
      `<path d="M57 26l2.6 2.2-7 22-2.4-1z" fill="#e3e8f0" stroke="#7d8798" stroke-width=".6"/><rect x="47.5" y="49" width="7" height="2.6" rx="1" fill="#3b4250" transform="rotate(-68 51 50)"/>`,
      `<path d="M57 24l2.8 2.4-7.6 23-2.6-1z" fill="#d6c8ff" stroke="#9a6bff" stroke-width=".8"/><path d="M8 30l-2.6 2 7 20 2.4-1z" fill="#d6c8ff" stroke="#9a6bff" stroke-width=".8"/>
       <circle cx="57" cy="24" r="1.4" fill="#c49bff"/>`,
    ],
    ranger: [
      `<path d="M54 28c7 6 7 22 0 28" stroke="${wood}" stroke-width="2.4" fill="none"/><path d="M54 28v28" stroke="#e8e0cc" stroke-width=".8"/>`,
      `<path d="M53 24c9 7 9 27 0 34" stroke="${woodD}" stroke-width="2.6" fill="none"/><path d="M53 24v34" stroke="#f2ecdc" stroke-width=".8"/><path d="M45 41h10" stroke="#8a5a33" stroke-width="1.2"/><path d="M55 41l-3-2v4z" fill="${steel}"/>`,
      `<path d="M53 22c10 8 10 29 0 36" stroke="${gold}" stroke-width="2.8" fill="none"/><path d="M53 22v36" stroke="#fff6c8" stroke-width=".8"/>
       <path d="M44 40h12" stroke="#7fe08a" stroke-width="1.4"/><path d="M56.5 40l-3-2.2v4.4z" fill="#b8ffbf"/><path d="M60 26c2-2 4-2 5-1-2 1-3 2-5 1zM61 51c2 0 3 1 4 3-2 0-3-1-4-3z" fill="#7fe08a"/>`,
    ],
    necromancer: [
      `<circle cx="56" cy="50" r="5" fill="#f4f1e8"/><circle cx="54.2" cy="49.5" r="1.3" fill="#2a1d3a"/><circle cx="57.8" cy="49.5" r="1.3" fill="#2a1d3a"/><rect x="54" y="53.5" width="4" height="2" fill="#f4f1e8"/>`,
      `<rect x="54" y="24" width="2.6" height="34" rx="1.3" fill="#3a2a4a"/><circle cx="55.3" cy="22" r="5" fill="#f4f1e8"/><circle cx="53.5" cy="21.6" r="1.2" fill="#2a1d3a"/><circle cx="57.1" cy="21.6" r="1.2" fill="#2a1d3a"/>`,
      `<rect x="54" y="22" width="2.8" height="36" rx="1.4" fill="#2a1d3a"/><circle cx="55.4" cy="20" r="5.4" fill="#f4f1e8"/><circle cx="53.5" cy="19.6" r="1.3" fill="#8d5cff"/><circle cx="57.3" cy="19.6" r="1.3" fill="#8d5cff"/>
       <path d="M4 40c0-5 3-8 6-8s6 3 6 8l-2 3-2-2-2 2-2-2-2 2z" fill="#e7e2ff" opacity=".85"/><circle cx="8.5" cy="38" r=".9" fill="#2a1d3a"/><circle cx="11.5" cy="38" r=".9" fill="#2a1d3a"/>`,
    ],
    bard: [
      `<circle cx="55" cy="47" r="6" fill="#f6e2b8" stroke="#b07a3a" stroke-width="1.6"/><circle cx="50" cy="45" r="1.2" fill="${gold}"/><circle cx="60" cy="45" r="1.2" fill="${gold}"/><circle cx="55" cy="53" r="1.2" fill="${gold}"/>`,
      `<ellipse cx="54" cy="50" rx="6.5" ry="7.5" fill="#c9843f" stroke="#7d4a1d"/><circle cx="54" cy="50" r="2" fill="#5a3415"/><rect x="53" y="28" width="2.4" height="16" fill="#7d4a1d"/><rect x="52" y="26" width="4.4" height="4" rx="1" fill="#5a3415"/>`,
      `<path d="M50 56V28c6 0 12 6 12 14v14z" fill="none" stroke="${gold}" stroke-width="2.6"/><path d="M53 30v24M56 32v22M59 37v17" stroke="#fff3c4" stroke-width=".7"/>
       <path d="M6 30v-6l4-1v6" stroke="#ff7ab8" stroke-width="1.2" fill="none"/><circle cx="5" cy="30" r="1.6" fill="#ff7ab8"/><circle cx="9" cy="29" r="1.6" fill="#ff7ab8"/>`,
    ],
    paladin: [
      `<path d="M50 38h12v8c0 6-3 9-6 11-3-2-6-5-6-11z" fill="#9aa4b4" stroke="#5a6270"/><path d="M56 40v15M51.5 45h9" stroke="#d9454a" stroke-width="2"/>`,
      `<path d="M49 38h13v8c0 7-3 10-6.5 12-3.5-2-6.5-5-6.5-12z" fill="#b8c0cc" stroke="#5a6270"/><path d="M55.5 40v16M50.5 45.5h10" stroke="#d9454a" stroke-width="2"/>
       <rect x="6" y="20" width="2.6" height="26" rx="1" fill="#dfe4ec" stroke="#8a93a3" stroke-width=".6"/><rect x="3" y="43" width="8.6" height="2.4" rx="1" fill="${goldD}"/>`,
      `<path d="M48 36h15v9c0 8-4 12-7.5 14-3.5-2-7.5-6-7.5-14z" fill="${gold}" stroke="${goldD}" stroke-width="1.2"/><path d="M55.5 39v17M50 45h11" stroke="#fff" stroke-width="2"/>
       <rect x="6" y="16" width="2.8" height="30" rx="1" fill="#fffbe8" stroke="${goldD}" stroke-width=".6"/><rect x="2.5" y="43" width="10" height="2.6" rx="1" fill="${goldD}"/>`,
    ],
    alchemist: [
      `<path d="M54 38h4v5l4 8c1 3-1 5-3 5h-6c-2 0-4-2-3-5l4-8z" fill="#e8fbff" stroke="#8ab" stroke-width=".7"/><path d="M51.5 50h9l1 2c0 2-1 3-2.5 3h-6c-1.5 0-2.5-1-2.5-3z" fill="#b06bff"/>`,
      `<path d="M54 36h4v5l4 8c1 3-1 5-3 5h-6c-2 0-4-2-3-5l4-8z" fill="#e8fbff" stroke="#8ab" stroke-width=".7"/><path d="M51.5 48h9l1 2c0 2-1 3-2.5 3h-6c-1.5 0-2.5-1-2.5-3z" fill="#4fd89a"/>
       <path d="M4 46h4v4l3 5c0 2-1 3-2.5 3h-5C2 58 1 57 1 55l3-5z" fill="#e8fbff" stroke="#8ab" stroke-width=".7"/><path d="M1.7 53h8.6l.4 2c0 1.5-1 2.5-2.2 2.5H3.5C2.3 57.5 1.3 56.5 1.3 55z" fill="#ff6b8a"/>`,
      `<path d="M47 46h16l-2 12H49z" fill="#3b3f4a" stroke="#1e2128"/><ellipse cx="55" cy="46" rx="8" ry="2.4" fill="#6bff9e"/>
       <circle cx="52" cy="42" r="1.8" fill="#9dffbf"/><circle cx="57" cy="39" r="1.4" fill="#9dffbf"/><circle cx="55" cy="35" r="1" fill="#c8ffd9"/>
       <path d="M4 44h4v4l3 5c0 2-1 3-2.5 3h-5C2 56 1 55 1 53l3-5z" fill="#e8fbff" stroke="${gold}" stroke-width=".8"/><path d="M1.7 51h8.6l.4 2c0 1.5-1 2.5-2.2 2.5H3.5C2.3 55.5 1.3 54.5 1.3 53z" fill="#b06bff"/>`,
    ],
    druid: [
      `<path d="M55 40c5 2 7 7 6 12-5-2-7-7-6-12z" fill="#5fbf4a"/><path d="M55.5 41l5 10" stroke="#3f7d3a" stroke-width=".8"/>`,
      `<path d="M55 24c-2 10 1 22-1 34" stroke="#7a4f27" stroke-width="2.6" fill="none" stroke-linecap="round"/><path d="M55 24c4-3 8-2 9 1-4 1-7 1-9-1zM54 32c-4-2-7-1-8 1 3 1 6 1 8-1z" fill="#5fbf4a"/>`,
      `<path d="M55 22c-2 11 1 24-1 36" stroke="#6b4423" stroke-width="2.8" fill="none" stroke-linecap="round"/><circle cx="55" cy="21" r="4" fill="#b8ff9c" opacity=".9"/>
       <path d="M55 26c5-3 9-2 10 1-4 1-8 1-10-1zM54 34c-5-2-8-1-9 1 3 1 7 1 9-1z" fill="#5fdf4a"/><path d="M6 24c2-1 4 0 4 2-2 1-3 0-4-2zM8 50c2-1 4 0 4 2-2 1-3 0-4-2z" fill="#9fef7a"/>`,
    ],
  };

  const AURA = { barbarian: '#ff6a3d', mage: '#8f7bff', medic: '#5fe0a0', rogue: '#9a6bff', ranger: '#7fe08a', necromancer: '#a56bff',
    bard: '#ff8fcf', paladin: '#ffd65a', alchemist: '#6bffd0', druid: '#9fef7a' };
  const WING = { paladin: ['#fffbe8', '#e0b341'], medic: ['#effff6', '#7fd6a8'], necromancer: ['#3a2450', '#a56bff'], rogue: ['#2a2140', '#9a6bff'],
    barbarian: ['#ff9a4d', '#d0461e'], mage: ['#c9bcff', '#6a52d6'], ranger: ['#bff0b0', '#4f8a4a'], bard: ['#ffd0ea', '#e0679d'],
    alchemist: ['#c9fff3', '#3f9fb3'], druid: ['#d9ffc4', '#4f8f3a'] };

  const aura = (cls, strong) => `<radialGradient id="au-${cls}-${strong ? 2 : 1}"><stop offset="45%" stop-color="${AURA[cls]}" stop-opacity="${strong ? .55 : .38}"/><stop offset="100%" stop-color="${AURA[cls]}" stop-opacity="0"/></radialGradient>
    <circle cx="32" cy="36" r="${strong ? 36 : 32}" fill="url(#au-${cls}-${strong ? 2 : 1})"/>`;
  const sparks = (cls, n) => [[6, 12], [58, 10], [3, 52], [60, 60], [16, 4], [48, 2]].slice(0, n)
    .map(([x, y]) => `<path d="M${x} ${y - 3}l.9 2.1 2.1.9-2.1.9-.9 2.1-.9-2.1-2.1-.9 2.1-.9z" fill="${AURA[cls]}"/>`).join('');
  const wings = (cls) => { const [f, s] = WING[cls] || ['#fff', '#ccc'];
    return `<path d="M12 44C4 42-1 34 0 24c3 3 6 4 9 4-2 2-3 5-2 7 2 0 4 1 5 3-2 1-3 3 0 6z" fill="${f}" stroke="${s}" stroke-width=".8"/>
      <path d="M2 30c3 1 5 1 7 1M1 36c3 1 6 1 8 0" stroke="${s}" stroke-width=".6" fill="none"/>
      <path d="M52 44c8-2 13-10 12-20-3 3-6 4-9 4 2 2 3 5 2 7-2 0-4 1-5 3 2 1 3 3 0 6z" fill="${f}" stroke="${s}" stroke-width=".8"/>
      <path d="M62 30c-3 1-5 1-7 1M63 36c-3 1-6 1-8 0" stroke="${s}" stroke-width=".6" fill="none"/>`; };

  /* Evolution, hybrid and mastery marks (all small, away from the face):
       stage 1 "Greater"  a cape behind the body and one rank chevron (bottom left)
       stage 2 "Prime"    a longer cape, gold shoulder spikes and two chevrons
       hybrid             the second discipline's weapon in the other hand (left side)
       class mastery      a gold star top right;  hybrid mastery: a teal star top left (proficiency 100) */
  const DISC_ITEM = {
    sword: `<rect x="9" y="30" width="2.4" height="22" rx="1" fill="#e3e8f0" stroke="#8a93a3" stroke-width=".6" transform="rotate(-12 10 41)"/><rect x="5" y="49" width="9" height="2.4" rx="1" fill="${goldD}" transform="rotate(-12 10 50)"/>`,
    archery: `<path d="M12 30c-8 6-8 22 0 28" stroke="#c99a3f" stroke-width="2.4" fill="none"/><path d="M12 30v28" stroke="#f2ecdc" stroke-width=".8"/>`,
    magic: `<rect x="9" y="34" width="2.4" height="24" rx="1.2" fill="#5e3b1a"/><circle cx="10.2" cy="32" r="4" fill="#8fe3ff" stroke="#c9a14b" stroke-width="1.1"/><circle cx="9" cy="30.8" r="1.1" fill="#fff"/>`,
  };
  const star = (x, y, c) => `<path d="M${x} ${y - 4.2}l1.4 3 3.2.4-2.4 2.2.7 3.2-2.9-1.7-2.9 1.7.7-3.2-2.4-2.2 3.2-.4z" fill="${c}" stroke="#fff6c8" stroke-width=".5"/>`;
  const rank = (n) => Array.from({ length: n }, (_, i) => `<path d="M5 ${59 - i * 4}l5-3.2 5 3.2" stroke="${gold}" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"/>`).join('');
  const cape = (cls, stage) => { const c = AURA[cls]; return stage >= 2
    ? `<path d="M16 38L4 62l14-5 6 5zM48 38l12 24-14-5-6 5z" fill="${c}" stroke="#1d1d2a" stroke-opacity=".35" stroke-width=".8"/><path d="M16 38L8 56l9-3zM48 38l8 18-9-3z" fill="#fff" fill-opacity=".18"/>`
    : `<path d="M17 40L8 58l11-3 4 4zM47 40l9 18-11-3-4 4z" fill="${c}" stroke="#1d1d2a" stroke-opacity=".35" stroke-width=".8"/>`; };
  const spikes = () => `<path d="M13 40l-5-8 8 3zM51 40l5-8-8 3z" fill="${gold}" stroke="${goldD}" stroke-width=".8"/>`;

  function gear(cls, rarity, o = {}) {
    if (!HAT[cls]) return {};
    const t = TIER[rarity] ?? 0, stage = o.stage || 0;
    const hat = HAT[cls][t <= 1 ? 0 : t === 2 ? 1 : 2];
    const item = t === 0 ? '' : ITEM[cls][t <= 2 ? (t === 1 ? 0 : 1) : t === 3 ? 1 : 2];
    const back = (stage ? cape(cls, stage) : '') + (t >= 3 ? aura(cls, t === 4) + (t === 4 ? wings(cls) : '') : '');
    const front = hat + item + (t >= 3 ? sparks(cls, t === 4 ? 6 : 3) : '') + (stage >= 2 ? spikes() : '') + (stage ? rank(stage) : '')
      + (o.disc && DISC_ITEM[o.disc] ? DISC_ITEM[o.disc] : '') + (o.cm ? star(54, 8, '#ffd45a') : '') + (o.hm ? star(10, 8, '#5fe0d0') : '');
    const svg = (cl, inner) => inner ? `<svg class="${cl}" viewBox="0 0 64 64" aria-hidden="true">${inner}</svg>` : '';
    return { back: svg('gear-back', back), front: svg('gear-front', front) };
  }
  return { gear, classes: Object.keys(HAT) };
})();
