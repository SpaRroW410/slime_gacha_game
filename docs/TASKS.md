# Task checklist

The remaining roadmap as working tasks. `[x]` done, `[~]` in progress, `[ ]` to do. Each has a short "done when".
The roadmap (`ROADMAP.md`) stays the milestone history; this file is what is left. Update both when something ships.

## Milestone
- [~] **1. Floor-50 playtest and balance** — harness `tools/playtest.py` and report `PLAYTEST_F50.md` are done; an AI bug that wasted opening turns on buffs is fixed.
  *Done when:* the real descent to floor 50 has been played through (with gear, elements, scouting) and the follow-ups below are closed.
- [x] **24. Floor threat smoothing (from the playtest)** — floors are pulled into a threat band around a curve (`dungeon._smooth`); `python3 tools/playtest.py --smoothness` is the regression check. Floor 32 ~63-82 -> ~45; floor 50 for commons ~78 -> ~63.
  *Done when:* met (mean deviation 0.16 against a 0.22 limit). The late-boss walls at levels ~52-63 come from the star/stage steps, not from threat.
- [x] **25. Time-to-floor-50 economy (from the playtest)** — a won Pit run pays the XP need over the runs a level should take (`config.pit_xp_per_run`): floor 50 in ~144 / ~182 / ~147 real hours at x3 for common / rare / legendary (was ~390 / ~960 / ~1,800).
  *Done when:* met; `tests/test_economy.py` pins the rule and the < 200 hour ceiling.

## Gameplay
- [x] **2. More specialization paths** — three new class paths into archery, each with a signature skill and a capstone: Medic+archery = Dawn Archer, Necromancer+archery = Plague Archer, Rogue+archery = Nightstalker (12 hybrids now). Three-way hybrids, evolving specializations and slimes asking for jobs are left as later ideas.  *Done when:* met; `tests/test_hybrids.py` covers resolution, skills and capstones.
- [x] **3. Spell mutation** — fused spells change form at set mastery levels (`spells.MUTATIONS`, effects from `fx.py`): stage 1 at required mastery +1, stage 2 at +3; heal/guard fusions share purifying forms. Academy lists the forms; the slime card marks the stage with ✦.  *Done when:* met; `tests/test_mutation.py`.
- [x] **4. Enemy resistances and elemental floors** — monster families are weak to / resist several elements (`bestiary.FAMILY_TRAITS`, `elements.matchup`, x1.5 / x0.7); every sixth non-boss floor from floor 3 is elemental (`dungeon.is_elemental_floor`): its terrain boosts one element +25% and dampens the opposing one -20%, for both sides.  *Done when:* met; intel (fully scouted floors list weak-to / resists, elemental floors name their element), Guide and `tests/test_resist.py`.
- [x] **5. Floor modifiers and shops between floors** — six floor modifiers (`modifiers.py`: Poison Fog, Darkness, Thin Air, Brittle Ground, Bloodlust, Sacred Spring) built from fx buffs/debuffs and poison, drawn from the seed on ~1 in 3 non-boss floors and revealed by scouting at 40%; wayside stops on floors 3, 8, 13 ... with a safe rest and a four-item shop (one-fight boons).  *Done when:* met; `tests/test_modifiers.py`.
- [x] **6. Retreat mid-descent** — `Game.retreat`: the one costed way out mid-segment (purple gel 2 + 1 per 5 floors, 12 morale each, stamina drained, 35%+ ambush that can kill). Cleared floors stay cleared; re-entry is from a checkpoint. The free exit after a boss is unchanged.  *Done when:* met; web button with confirm, CLI [r], Guide, `tests/test_reinforce.py::TestRetreat`.
- [x] **7. Several delves at once + rescue parties** — any number of parties can be in the Descent, a rescue or other expeditions at once, each with its own live timer (`tests/test_rescue.py::TestSeveralDelvesLive`); scouts that overrun their budget are stranded for 24h (`Game.stranded`) and a rescue party (`Game.rescue`, food + (4 + floor) hours, ambushable) can bring them home, else they are lost.  *Done when:* met.
- [ ] **8. Formations and front/back rows** — positions affect targeting and damage.  *Done when:* AI and manual arena respect rows.
- [ ] **9. New classes: Bard, Paladin, Alchemist, Druid** — four archetypes with 4 rarity skills, an evolution skill, 2 capstones and star attributes each.  *Done when:* all four pull, level, fight and appear in the Guide.
- [ ] **10. Construction time; Pantry and Hatchery** — upgrades take game time; two new buildings.  *Done when:* upgrades show in the away bar and the buildings have effects.
- [ ] **11. Gear set bonuses** — bonuses for matching sets.  *Done when:* shown in Armory and slime card, balanced.
- [ ] **12. Keeper achievements, titles and respec** — achievements list, titles, skill respec.  *Done when:* People > Keeper shows them and respec costs something.
- [ ] **13. Imbue statuses and revival items** — e.g. Barbarian fire-axe imbue as a timed status; consumable resurrection.  *Done when:* both use fx and are tested.

## Content
- [ ] **15. Campaign chapters from STORY.md** — story beats at floors and boss clears.  *Done when:* chapters trigger from data and are readable in game.

## Platform
- [ ] **14. Named dungeon registry** — dungeons defined as data.  *Done when:* Descent, Pit, Rift and Quarry load from definitions and a new one can be added without code.
- [ ] **16. Daily free pull on the real clock** — in both time modes, with offline catch-up.  *Done when:* the pull resets by wall clock everywhere.
- [ ] **20. PWA manifest and service worker** — installable offline play.  *Done when:* installs on iPhone and Windows and works with no network.
- [ ] **23. Mod loader (`plugins/`) with docs** — documented plugin API with an example.  *Done when:* an example plugin adds a class, a skill and an enemy.
- [x] **26. Occupations (jobs for slimes at home)** — slimes take a non-combat job in town: Chef (cooks meals that fill needs or give temporary buffs), Blacksmith (repairs, upgrades and forges gear), Trainer (coaches others' proficiency and sparring style), plus room for more (Herbalist, Scout, Librarian). Jobs run on the away clock, use the slime's stats and gain their own job levels; a working slime is not free for the Descent. Decided: jobs are **switchable**, done **in town**, **no wages** - the point is to make non-combat slimes useful. Reworked: appointments are made inside each building's own screen. Three trainers (sword/archery/magic, 2★+) in the Training Grounds, librarian in the Library, blacksmith (mends, forges weapons/relics slowly) in the Armory, brewer in the Alchemy Lab, chef (recipes, pantry, hunger counter) in the Kitchen, medic doctor in the new Hospital; 3-hour shifts with a bonus; idle chef/blacksmith/brewer/doctor forage for a shift and can be called back; Rest Area restores energy fast but HP at base rate. Idle slimes with no party forage on their own. Still open: whether job skill decays like proficiency.  *Done when:* at least Chef, Blacksmith and Trainer can be assigned in the web UI, show in the away bar, produce their output, persist in saves and are covered by tests and the Guide.
- [x] **27. Descent reinforcements and limited camping** — a party camping on floor N can be joined by another party that has cleared the floors below; they fight together. A 5-star mage proficient in two elements can instead *call* reinforcements straight to the floor for purple gel (cost +1 per 5 floors). Camping time is limited by the scout percentage and the floor (floor 3: 3 hours); there is always a chance of ambush while camping, and it drops when the floor below starts to clear (a reinforcing party is on the way).  *Done when:* a second party can reach a camping party and the two fight as one; the mage call works and costs gel; camp length and ambush chance follow floor and scout %; tests cover each rule.

## Interface
- [ ] **18. CLI turn prompts for manual battles + optional flee** — terminal manual fights.  *Done when:* `main.py` can fight a skirmish by hand; flee decided and documented.

## Quality
- [ ] **21. Balance pass with a simulation harness** — extend `tools/playtest.py` to Pit depths, rarities, skills and capstones.  *Done when:* a report covers each system and numbers are tuned in `config.py`.
- [ ] **22. Localisation** — string catalogs and a language switch.  *Done when:* UI, logs and Guide can be switched to a second language.

## After floor 50 (art and sound)
- [ ] **17. Animated battle arena** — replace `ARENA.render`.  *Done when:* units animate and statuses show without touching rules.
- [ ] **19. Art pass: sprites, animated slimes, sound** — replace the CSS blobs, add sound effects.  *Done when:* every slime class and rarity has art and the main actions have sound.
