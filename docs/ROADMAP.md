# Slime Gacha — roadmap, tasks and history

One file for where the game is going and where it has been. On 28 October 2026 it absorbed what used to be five files:
`ROADMAP.md` (milestones), `TASKS.md` (the task list), `MINDS.md` (slime minds), `PLAYTEST_F50.md` (the floor-50 playtest) and
`BALANCE.md` (the balance report). Kept apart: [`SDD.md`](SDD.md) (software design), [`STORY.md`](STORY.md) (lore; the game reads
its chapters) and [`MODDING.md`](MODDING.md) (writing plugins).

Legend: `[x]` done · `[~]` in progress · `[ ]` to do.

1. [Where things stand](#1-where-things-stand)
2. [Open tasks](#2-open-tasks)
3. [Done tasks](#3-done-tasks)
4. [Milestones](#4-milestones)
5. [Slime minds](#5-slime-minds)
6. [Floor-50 playtest](#6-floor-50-playtest)
7. [Balance report](#7-balance-report)
8. [Commit history, first to last](#8-commit-history-first-to-last)

## 1. Where things stand

As of 27 October 2026:
- **Version 1.001.** `main` is at the merge of PR #23 (slime minds, party pickers, the loading fix and this document) and is
  what GitHub Pages serves. The next pull request (troublemakers and the Keeper's shadow, task 66) is open.
- **Checks:** the unit tests pass (`python3 -m unittest discover -s tests`); 20 of 20 behaviour targets on 3 seeds
  (`python3 tools/minds_sim.py --seeds 3 --check`); playtest smoothness 0.129 against a 0.22 limit; balance report unchanged.
- **Next:** the real descent to floor 50 (task 1), then the mobile work (tasks 48-52).
- **Keeping this file current:** tick tasks here when they ship (the About tab's roadmap must list exactly the open ones - a test
  checks it), add a milestone line, and run `python3 tools/changelog.py` to refresh § 8.

## 2. Open tasks

### Milestone

- [~] **1. Floor-50 playtest and balance** — harness `tools/playtest.py` and report § 6 below are done; an AI bug that wasted opening turns on buffs is fixed.
  Re-run on the current code (equal star levels, formations, one-day sessions): floor 50 needs level 57 / 50 / 41 / 31 / 25 for common / uncommon / rare / epic / legendary, ~130-186 real hours at x3; smoothness 0.132 (limit 0.22).
  *Done when:* the real descent to floor 50 has been played through (with gear, elements, scouting) and the follow-ups below are closed. Left: extend the harness (or a hand playthrough) to gear, relics, elements and potions.

### Later

- [ ] **82. More passive skills** — Tailwind (the wind element mastered; task 79) is the first passive skill and lives in `passives.py`. Design more for other slimes: perks earned by mastering something (an element, a class capstone, a fighting style, a trade), always on, shown on the Fight tab.  *Done when:* a set of passives covers every class and element, each earned in a way the slime card explains, and the Guide lists them.

### Mobile (phase 2) — Capacitor route, from the QA and mobile planning report

- [ ] **48. Mobile M2: performance** — engine hot spots, smaller replies, in-place page updates, lazy rosters, startup measured on low-end phones.  *Done when:* Pyodide startup and big-colony turns are acceptable on a 2 GB Android phone and an iPhone SE.
- [ ] **49. Mobile M3: Capacitor shell** — native storage with atomic writes and rotating checksummed backups, lifecycle (save on pause, stop timers), store builds.  *Done when:* builds run on iOS and Android with safe saves.
- [ ] **50. Mobile M4: store prep and compliance** — odds screen, age-rating answers, privacy labels, listings, regional rules.  *Done when:* TestFlight and Play internal testing builds are submitted.
- [ ] **51. Mobile M5 (optional): monetization decision** — will real money buy gacha currency? If yes: server-side economy and receipts; if no: stay on-device.  *Done when:* the decision is made and recorded.
- [ ] **52. Mobile M6: beta and launch** — device testing, long sessions, crash reporting, release.  *Done when:* released.

## 3. Done tasks

### Milestone

- [x] **24. Floor threat smoothing (from the playtest)** — floors are pulled into a threat band around a curve (`dungeon._smooth`); `python3 tools/playtest.py --smoothness` is the regression check. Floor 32 ~63-82 -> ~45; floor 50 for commons ~78 -> ~63.
  *Done when:* met (mean deviation 0.16 against a 0.22 limit). The late-boss walls at levels ~52-63 come from the star/stage steps, not from threat.
- [x] **25. Time-to-floor-50 economy (from the playtest)** — a won Pit run pays the XP need over the runs a level should take (`config.pit_xp_per_run`): floor 50 in ~144 / ~182 / ~147 real hours at x3 for common / rare / legendary (was ~390 / ~960 / ~1,800).
  *Done when:* met; `tests/test_economy.py` pins the rule and the < 200 hour ceiling.

### Gameplay

- [x] **2. More specialization paths** — three new class paths into archery, each with a signature skill and a capstone: Medic+archery = Dawn Archer, Necromancer+archery = Plague Archer, Rogue+archery = Nightstalker (12 hybrids now). Three-way hybrids, evolving specializations and slimes asking for jobs are left as later ideas.  *Done when:* met; `tests/test_hybrids.py` covers resolution, skills and capstones.
- [x] **3. Spell mutation** — fused spells change form at set mastery levels (`spells.MUTATIONS`, effects from `fx.py`): stage 1 at required mastery +1, stage 2 at +3; heal/guard fusions share purifying forms. Academy lists the forms; the slime card marks the stage with ✦.  *Done when:* met; `tests/test_mutation.py`.
- [x] **4. Enemy resistances and elemental floors** — monster families are weak to / resist several elements (`bestiary.FAMILY_TRAITS`, `elements.matchup`, x1.5 / x0.7); every sixth non-boss floor from floor 3 is elemental (`dungeon.is_elemental_floor`): its terrain boosts one element +25% and dampens the opposing one -20%, for both sides.  *Done when:* met; intel (fully scouted floors list weak-to / resists, elemental floors name their element), Guide and `tests/test_resist.py`.
- [x] **5. Floor modifiers and shops between floors** — six floor modifiers (`modifiers.py`: Poison Fog, Darkness, Thin Air, Brittle Ground, Bloodlust, Sacred Spring) built from fx buffs/debuffs and poison, drawn from the seed on ~1 in 3 non-boss floors and revealed by scouting at 40%; wayside stops on floors 3, 8, 13 ... with a safe rest and a four-item shop (one-fight boons).  *Done when:* met; `tests/test_modifiers.py`.
- [x] **6. Retreat mid-descent** — `Game.retreat`: the one costed way out mid-segment (purple gel 2 + 1 per 5 floors, 12 morale each, stamina drained, 35%+ ambush that can kill). Cleared floors stay cleared; re-entry is from a checkpoint. The free exit after a boss is unchanged.  *Done when:* met; web button with confirm, CLI [r], Guide, `tests/test_reinforce.py::TestRetreat`.
- [x] **7. Several delves at once + rescue parties** — any number of parties can be in the Descent, a rescue or other expeditions at once, each with its own live timer (`tests/test_rescue.py::TestSeveralDelvesLive`); scouts that overrun their budget are stranded for 24h (`Game.stranded`) and a rescue party (`Game.rescue`, food + (4 + floor) hours, ambushable) can bring them home, else they are lost.  *Done when:* met.
- [x] **8. Formations and front/back rows** — every combatant stands in the front or back row (`Slime.row`, "auto" = casters and archers at the back; monsters by role): melee single-target blows reach only the front row while it stands (arrows, spells, area attacks and backstabs reach anyone), the back row takes x0.8 damage and a melee fighter there hits for x0.75. Set per slime on the party card and in Orders; the manual arena draws the rows and offers only reachable targets.  *Done when:* met; `tests/test_rows.py`, Guide.
- [x] **9. New classes: Bard, Paladin, Alchemist, Druid** — four archetypes with 4 rarity skills, an evolution skill, 2 capstones and star attributes each.  *Done when:* all four pull, level, fight and appear in the Guide.
- [x] **10. Construction time and the Hatchery** — upgrades take game time; a Hatchery building (the Pantry now lives in the Kitchen).  *Done when:* upgrades show in the away bar and the Hatchery has effects.
- [x] **11. Gear set bonuses** — bonuses for matching sets.  *Done when:* shown in Armory and slime card, balanced.
- [x] **12. Keeper achievements, titles and respec** — achievements list, titles, skill respec.  *Done when:* People > Keeper shows them and respec costs something.
- [x] **13. Imbue statuses and revival items** — e.g. Barbarian fire-axe imbue as a timed status; consumable resurrection.  *Done when:* both use fx and are tested.

### Content

- [x] **15. Campaign chapters from `STORY.md`** — story beats at floors and boss clears.  *Done when:* chapters trigger from data and are readable in game.

### Platform

- [x] **14. Named dungeon registry** — dungeons defined as data.  *Done when:* Descent, Pit, Rift and Quarry load from definitions and a new one can be added without code.
- [x] **16. Daily free pull on the real clock** — in both time modes, with offline catch-up.  *Done when:* the pull resets by wall clock everywhere.
- [x] **20. PWA manifest and service worker** — installable offline play.  *Done when:* installs on iPhone and Windows and works with no network.
- [x] **23. Mod loader (`plugins/`) with docs** — documented plugin API with an example.  *Done when:* an example plugin adds a class, a skill and an enemy.
- [x] **26. Occupations (jobs for slimes at home)** — slimes take a non-combat job in town: Chef (cooks meals that fill needs or give temporary buffs), Blacksmith (repairs, upgrades and forges gear), Trainer (coaches others' proficiency and sparring style), plus room for more (Herbalist, Scout, Librarian). Jobs run on the away clock, use the slime's stats and gain their own job levels; a working slime is not free for the Descent. Decided: jobs are **switchable**, done **in town**, **no wages** - the point is to make non-combat slimes useful. Reworked: appointments are made inside each building's own screen. Three trainers (sword/archery/magic, 2★+) in the Training Grounds, librarian in the Library, blacksmith (mends, forges weapons/relics slowly) in the Armory, brewer in the Alchemy Lab, chef (recipes, pantry, hunger counter) in the Kitchen, medic doctor in the new Hospital; 3-hour shifts with a bonus; idle chef/blacksmith/brewer/doctor forage for a shift and can be called back; Rest Area restores energy fast but HP at base rate. Idle slimes with no party forage on their own. Still open: whether job skill decays like proficiency.  *Done when:* at least Chef, Blacksmith and Trainer can be assigned in the web UI, show in the away bar, produce their output, persist in saves and are covered by tests and the Guide.
- [x] **27. Descent reinforcements and limited camping** — a party camping on floor N can be joined by another party that has cleared the floors below; they fight together. A 5-star mage proficient in two elements can instead *call* reinforcements straight to the floor for purple gel (cost +1 per 5 floors). Camping time is limited by the scout percentage and the floor (floor 3: 3 hours); there is always a chance of ambush while camping, and it drops when the floor below starts to clear (a reinforcing party is on the way).  *Done when:* a second party can reach a camping party and the two fight as one; the mage call works and costs gel; camp length and ambush chance follow floor and scout %; tests cover each rule.

### Interface

- [x] **18. CLI turn prompts for manual battles + optional flee** — terminal manual fights.  *Done when:* `main.py` can fight a wave simulation by hand; flee decided and documented.

### Quality

- [x] **21. Balance pass with a simulation harness** — extend `tools/playtest.py` to Pit depths, rarities, skills and capstones.  *Done when:* a report covers each system and numbers are tuned in `config.py`.
- [x] **22. Localisation** — string catalogs and a language switch.  *Done when:* UI, logs and Guide can be switched to a second language.

### QA report (phase 1) — from the QA and mobile planning report (https://claude.ai/artifact/4YYjeph6PAC4xW9A1qdHry, tested at commit 3cd06d8)

- [x] **34. C1 (critical): a bad save locks players out of the static build** — validate saves in `Game.from_dict`, catch every load error, offer start-fresh / restore-backup instead of a traceback.  Done: `Game.check_save` refuses junk (wrong shapes, newer format, negative time, absurd wallet) with a `SaveError`; `from_dict` can only raise `SaveError`; the session reports any stray error instead of dying; the page shows "Your save could not be loaded" with restore-backup / copy / import / start-new (the damaged save is kept), and a rotating backup is taken every five minutes of play.  *Done when:* met; `tests/test_save_safety.py` and a browser check.
- [x] **35. M1: reloading during a manual battle undoes permadeath** — `Game.flow` is memory-only.  *Done when:* reload mid-battle cannot revive dead slimes or refight the floor.
- [x] **36. M2: shown odds do not match the code** — purple is x3.57 not x5 and boosts uncommon; star odds and the 3-star minimum are not shown; Favor covers all ten pulls; README, `gacha.py` docstring and `docs/SDD.md` list old rates.  *Done when:* exact odds per pull button are shown and every doc agrees with the code.
- [x] **37. M3: free pulls repeat without limit** — the daily pull follows game days, which are free to skip; live mode can be gamed with the device clock.  *Done when:* one free pull per real day in both modes (see task 16).
- [x] **38. M4: two tabs overwrite each other (static build)** — last save wins.  *Done when:* a second tab is detected and warned or shares one game.
- [x] **39. M5: Import replaces the colony without asking** — any JSON loads as an empty colony.  *Done when:* import confirms, validates the file and backs up the current colony first.
- [x] **40. M6: failed saves are silent; no offline support** — storage errors are swallowed; no manifest or service worker.  *Done when:* a visible warning appears when saving fails and the page works offline (see task 20).
- [x] **41. M7: waiting gets very slow in big colonies** — `_healer_aura` rescans and recomputes `max_hp` per healer (+1 day: 0.4 s at 100 slimes, 11 s at 500).  *Done when:* +1 day under 1 s at 250 slimes in native Python.
- [x] **42. M8: every action sends and stores the full state and save** — 0.95 MB at 200 slimes; pull count unbounded.  *Done when:* replies carry deltas or are bounded, saves are written on a timer/pause, and pull count is capped.
- [x] **43. M9: time controls and active tab scroll out of view on phones** — header snaps back after each action.  *Done when:* the +1h/+4h/+1 day buttons and the active tab stay reachable at 375 px.
- [x] **44. M10: toast messages block taps** — they accept taps and cover the pull buttons.  *Done when:* toasts let taps through and sit clear of the main buttons.
- [x] **45. M11: slimes cannot be opened from the keyboard; dialogs lack roles** — slime cards are plain divs.  *Done when:* cards are focusable and open with Enter, dialogs have `role="dialog"` and trap focus.
- [x] **46. Minor bugs m1-m9** — Android back, light-theme contrast, star screen-reader text, small tap targets, constant animation, unguarded `syncLive`, no new-game backup, odd saved numbers, unchecked spell names.  *Done when:* each is fixed or consciously declined.

### Mobile (phase 2) — Capacitor route, from the QA and mobile planning report

- [x] **47. Mobile M1: mobile UX** — 44 pt / 48 dp targets, fixed time controls (the tab bar stays at the top: nine tabs scroll sideways and sit under the header; a bottom bar would cost a second row beside the time controls), scroll positions kept, safe areas, Android back, purple ten-pull confirm.  *Done when:* the game is comfortable on a 375 px phone.

### Slime minds (§ 5) — behave like people; harness `tools/minds_sim.py`

- [x] **53. Behaviour harness (T15)** — colony, legendary, recovery and grief scenarios with targets; `tests/test_minds.py` runs a small version.  *Done when:* met.
- [x] **54. Feuds cool off (T1)** — self-mending, apologies, friends make peace, time apart after a brawl, at most two brawls then a cold war.  *Done when:* met (68 brawls in 45 days hands-off, was 1,054).
- [x] **55. Feelings return to a baseline (T2)** — trait baselines, contentment over days, needs simmer but never boil; the feelings' dice are saved.  *Done when:* met (everyday joy about 9, was 0).
- [x] **56. Care makes friends, not rivals (T4)** — a failed talk means not yet, making up counts towards friendship, calmer trait odds.  *Done when:* met.
- [x] **57. Legendary outcomes (T3)** — 14-day record, settled / peace / cog / despair, 70% Keeper share, deepening despair, leaving with permission.  *Done when:* met.
- [x] **58. Goals people actually have (T7)** — a weighted pool (master a style, befriend, court, protect a mentee, explore, craft, rest, praise); grudges one candidate among many.  *Done when:* met (0-2 of 20 slimes want revenge, was 9-18); slimes at home or at a post grow closer, not only idle ones at noon.
- [x] **59. Meaning for every slime (T5)** — the record's purpose for all slimes, a Praise action, burnout for non-legendaries.  *Done when:* met (meaning.py: every slime keeps a week; an unseen worker burns out, a praised one does not).
- [x] **60. Grief that lasts and comes in waves (T6)** — tied to the "lost" memory, 1-3 weeks, reminders, the Memorial gathering.  *Done when:* met (grief.py: about 17 days alone, 7-8 with a friend and daily talks; anniversaries and places bring it back; gatherings at the Memorial Pond).
- [x] **61. Coping styles (T8)** and **friends comfort each other (T9)** — visible actions when a bad feeling passes 50; cuddle lines as a daily summary.  *Done when:* met (coping.py: nine styles by personality, friends cheer each other up, moods spread in parties away, cuddles summed up daily - at most 1 line a day, was up to 85).
- [x] **62. An inner voice that remembers (T10)** — talk lines from memories, goals and causes for every slime (legendaries already never repeat within a week).  *Done when:* met (voice.py: grief, the strongest memory, the goal, burnout or a good stretch, then a feeling; no line twice in a week for any slime).
- [x] **63. Daily rhythm and hobbies (T11)** — day parts, shared meals, hobbies by trait.  *Done when:* met (routine.py: meals together at 8, 13 and 19, evening hobbies at 20; idle time is not variety; praise breaks the grind).
- [x] **64. Relationship texture (T12), appraisal (T13), rituals (T14)** — bonds fade without time together, jealousy, apologies, per-trait reactions, hatch days.  *Done when:* met (relationships.py fading and jealousy, apologies for grudges, kind slimes forgive sooner, appraisal.py, rituals.py: hatch days, anniversaries, feasts).
- [x] **65. Why it feels this way (T16)** — top causes per feeling, a colony mood summary (the legendary card already shows its outcome and record).  *Done when:* met (emotions.note_cause and causes(); reasons under each feeling; Colony mood panel).
- [x] **66. Troublemakers and the Keeper's shadow** — the zero-cost rule for removing a troublemaker held up against the new minds: no grief beyond the partner's and best friend's half grief, a fair test (fought with more than 5% of the colony in 30 days, at least 2 slimes; snapped-at slimes not blamed), relief for its foes, fewer quarrels for a while after a removal (fear), and respect after the Keeper's talks.  *Done when:* met (zero morale and stress, half grief for partner and best friend only; quarrels x0.69-0.83 over the first 3 days after a removal, about half on day one).
- [x] **67. Descent strike forces** — a floor takes 1-5 parties by its place in the segment (1, 6, 11: one; 2, 7, 12: two; ... boss floors 5, 10, 15: five), chosen in a Strike force list on each party's Descent card; a mage's call adds one more beyond the limit.  *Done when:* met (`Game.force_cap` / `force_limit`, refused beyond them; the fight stays the turn-by-turn simulation).
- [x] **68. No waiting after a fight led by hand** — Descent floors and wave simulations fought by hand leave the party ready at once.  *Done when:* met (`Game._by_hand`; switching to auto halfway brings the wait back; the Pit's daily session budget is unchanged).
- [x] **69. Trainer rules** — a trainer must fight in the post's discipline (or have a natural knack for it) and only speeds up pupils whose own proficiency is lower.  *Done when:* met (`jobs.teaching_prof`, `trainer_bonus(pupil)`; the appointment list shows why a slime cannot hold the post).
- [x] **70. Call back from anywhere** — resting, foraging, hunting, studying and posted slimes show what they are doing and get a Call back button on cards, rows and in the Parties tab.  *Done when:* met.
- [x] **71. Pit and Rift sessions look after their party** — a Pit session in the web game (hours paid afterwards) killed a party of exhaustion because only HP and stamina were rested; now the session eats, sleeps and stops before anyone is exhausted.  *Done when:* met (`Game._field_hours`, `_field_meals`, `_needs_camp`, `_field_unfit`; the colony's tick leaves a session party's needs alone; reproduced and fixed with auto-care off in timed and turn mode).
- [x] **72. No taking command in the Pit** — the Pit is a farm and always fights automatically.  *Done when:* met.
- [x] **73. Trainers sharpen too** — each lesson that helps a pupil gives the trainer +0.15 proficiency.  *Done when:* met (`jobs.lesson`).
- [x] **74. Send several groups at once** — the Rift, Quarry and places share one sender: collapsible Parties and Individual slimes (search, class filter), many groups in one go, each its own expedition.  *Done when:* met (`send_groups`; at most 12 groups; a group that cannot go stays home).
- [x] **75. Calling slimes back for a trip** — busy slimes (resting, foraging, post, hunt, drill, asleep) can be picked and are called away at a cost (-6 morale, +12 anger); under 10% energy hidden, refusers greyed; expeditions now enforce refusals.  *Done when:* met (`Game.pull_in`, `recall` on Rift, Quarry, places, Pit and Descent entry).
- [x] **76. Trades on the slime** — the slime's detail panel lists every trade it has worked with its level and progress to the next, and cards show the post's level ("Doctor L3").  *Done when:* met.
- [x] **77. Guard against dropped buttons** — a page-wiring test checks that every button has a handler and every command the page sends exists (task 70-75's edit had dropped 17 handlers, among them Grant for requests, Talk and Praise).  *Done when:* met (`tests/test_web.py::TestUiWiring`).
- [x] **78. Dungeon time dilation** — time inside a dungeon runs faster than the lobby's, place by place (`Place.dilation`, 3.0 for the Descent, Pit, Rift, Quarry, Mossy Burrows, rescue and wave simulations; 1.0 for scouting, hunting, foraging, posts, drills, spars and stranded scouts). An activity of H dungeon hours costs the lobby clock ceil(H / rate), at least 1; the party inside burns food, energy and stamina and bonds at the dungeon rate; the live clock no longer speeds up when a party leaves.  *Done when:* met (`Game.lobby_hours`, `_spend(hours, kind)`, `NeedsEngine.scale_fn`, `_away_bonds`; the screens show "3h inside ≈ 1h here").
- [x] **79. Tailwind hastens rescues** — a slime that has mastered the wind element to the top level earns the Tailwind passive skill and shortens a rescue trip by 25% (up to 50% with two); an ordinary mage does not.  *Done when:* met (`passives.py`, `Game.rescue_speed`; passives show on the slime's Fight tab, locked ones with what it takes).
- [x] **80. Mages a little rarer in pulls** — pull weight 0.85 against 1.0 for the other magic classes.  *Done when:* met.
- [x] **81. Camps heal and rest in every mode** — a Pit or Rift session camp in turn mode no longer skips the sleepers' healing (the session now mends its own party), and a Descent camp in the web game restores energy as well as HP.  *Done when:* met (`Game._camp_hour`).
- [x] **83. Gear and relics told apart** — the two screens use different words (gear is *sold back*, a relic is *broken down*), the clashing names are changed (gear Wooden Bow, River Pebble, Dawn Shard; relics Wayfarer's Recurve, Gnarled Rod), and the Guide explains gear versus relics and how to get armor.  *Done when:* met (display names only: saves are unaffected).
- [x] **84. Eight more elements to fuse** — Mist (steam + wind), Geyser (steam + earth), Ash (lava + wind), Clay (mud + fire), Glass (sand + fire), Quicksand (sand + water), Glacier (ice + water) and Thunderstone (lightning + earth): tier-3 elements, each with its own two spell forms; the ones with three basics in them need all three mastered (the weakest component counts).  *Done when:* met (`elements.py`, `spells.MUTATIONS`; 21 recipes now).

### After floor 50 (art and sound)

- [x] **17. Animated battle arena** — replace `ARENA.render`.  *Done when:* units animate and statuses show without touching rules.
- [x] **19. Art pass: sprites, animated slimes, sound** — replace the CSS blobs, add sound effects.  *Done when:* every slime class and rarity has art and the main actions have sound.

## 4. Milestones

### M0 — Foundations (docs & scaffolding)
- [x] README
- [x] Story / lore (`STORY.md`)
- [x] Software design document (`SDD.md`)
- [x] Roadmap (this file)
- [x] Package skeleton, registry, config

### M1 — Core model
- [x] Slime, Stats, Needs, Personality
- [x] Archetype registry + 6 starting classes
- [x] Ability registry + built-in abilities
- [x] ResourceManager
- [x] JSON save / load

### M2 — Gacha
- [x] Rarity tiers + rates
- [x] Pity system (epic 10 / legendary 50) - built, then switched off so the stated rates are honest (`config.PITY_EPIC = PITY_LEGENDARY = 0`)
- [x] Single and ×10 pulls
- [x] Rarity/class stat scaling with per-slime variance

### M3 — Living slimes (AI)
- [x] Maslow needs engine (energy, food, safety, belonging, esteem)
- [x] Sleep cycle (auto-sleep / wake / manual)
- [x] Feeding (auto & manual)
- [x] Mood → power multiplier
- [x] Personality traits
- [x] Internal conflicts + mediation
- [x] Behaviour stances (attack / heal / defend / explore)

### M4 — Activities
- [x] Auto-hunt zones and timed hunts
- [x] Hunt rewards (gel / food / essence) + XP
- [x] Turn-based battle system with abilities, statuses, summons
- [x] Enemy registry + difficulty tiers
- [x] Battle loot & XP

### M5 — Growth
- [x] XP / levels
- [x] Ability unlocks by level
- [x] Evolution stages (Essence cost)
- [x] Merge with % XP transfer

### M6 — Interface & quality
- [x] Text menu UI
- [x] `--demo` scripted tour
- [x] Unit tests
- [x] Seeded determinism

### M7 — v0.2 rules update
- [x] Permadeath (starvation, hunts, brawls, battle) + graveyard / Memorial Pond
- [x] Colony grief on death
- [x] Rarity rates 90 / 9 / 0.9 / 0.09 (now 90 / 8 / 1.9 / 0.09 / 0.01 with the uncommon tier, M16)
- [x] 1–5★ rating, exponential falloff, steeper for higher rarity
- [x] Two gel currencies: white and purple (10 per pull, either)
- [x] Purple gel boosts rare odds (×5 weights on everything above common; exact odds on the Gacha tab since the QA pass)
- [x] Purple gel rare in hunts/dungeons (bosses best)
- [x] One free pull per game day
- [x] Fixed-size parties (multiple of 5), multiple parties, party hunt/battle
- [x] Save v2 with migration from v1
- [x] Tests for all of the above

### M8 — Dungeons
- [x] Rename currencies back to gel: white gel (common) / purple gel (rare)
- [x] Main dungeon "The Hollow Descent": endless floors, compounding difficulty, permadeath
- [x] Boss every 5 floors (Hollow Warden, then Parched King cycles) + first-clear purple-gel bounty
- [x] Floors cost game time; you can replay cleared floors
- [x] Grinding dungeon "The Gloop Pit": 5 depths scaled to party level, no permadeath, full XP per survivor
- [x] Multi-run grinding with optional auto-rest
- [x] Party rest command
- [x] Save v3 (`main_floor`), migration of old currency names
- [x] Tests for both dungeons

### M9 — Academy, elements & spell fusion
- [x] ~~Solo training grounds~~ (replaced in M10 by sparring)
- [x] Four basic elements + 13-element fusion tree (data-driven recipes)
- [x] Elemental wheel in battle (weakness / resist)
- [x] Elemental mastery from 3★, any class; slots + caps by stars; mage perks
- [x] Library: study elements, tier-1 spells, learn / forget, 4-spell limit
- [x] Spell lab: fuse two spells into a new (nameable) spell; success odds, costs, backfire
- [x] Discovered spells shared via the Library
- [x] Casting builds mastery; non-mage imbuing (attack-scaled spells)
- [x] Save v4 (custom spells, mastery, training)
- [x] Tests (32 new)

### M10 — Sparring, rest, buildings, bonds
- [x] Training reworked: sparring duels develop a fighting style (no XP, separate from the Gloop Pit)
- [x] Non-lethal duels: the loser drops to 1 HP
- [x] Three arenas and styles: Swordsmanship / Marksmanship / Spellcraft with combat perks
- [x] Rest Area: heals to full, capacity + speed by level, auto-admit for the wounded
- [x] Upgradable buildings: Rest Area, Training Grounds, Library, Barracks
- [x] Library levels: spell slots, study speed, research odds, Restricted Section (tier 3)
- [x] Bonds between slimes (sparring, battles, mediation, quarrels)
- [x] Compatibility score + party synergy (±10 % power)
- [x] Morale / fight readiness (power ×0.85–1.15, freezing when broken)
- [x] Council: keep-or-sacrifice ranking + merge suggestions with colony-morale cost
- [x] Merge changes: compatibility swings XP, bonds inherited, colony mourns
- [x] Save v5 and ~40 new tests

### M11 — Commitment, intel & consequences
- [x] Merging/sacrificing lowers morale (target, bystanders, friends) with compounding **sacrifice stress**
- [x] Hollow Descent in 5-floor segments: **no exit** until the boss falls or the whole party dies
- [x] Permanent death in the Descent; short-handed parties continue; in-dungeon camping with ambushes
- [x] Exploration party scouting: knowledge grows with time in the dungeon (diminishing returns)
- [x] Staged intel (counts → types → boss → abilities → weaknesses), deterministic floors, intel power bonus
- [x] Gloop Pit as a committed session (all runs or whole party down); auto-camping
- [x] Pit defeat: XP loss, morale loss, gear dropped; synergy-based recovery; Pit lost-and-found
- [x] Equipment (weapon / armor / charm), Armory building, gear drops
- [x] Save v6 and 32 new tests

### M12 — Browser edition
- [x] JSON command API (`webapi.py`) with render-ready snapshot and error envelope
- [x] Local server (`serve.py`, stdlib only, localhost) with `/api` and static hosting
- [x] Responsive, themable UI (dark/light): colony, gacha reveal, parties, dungeons, academy, town, council, records
- [x] Battle report viewer, confirmations for irreversible actions, toasts and event log
- [x] Browser auto-save (localStorage) + export/import
- [x] Static Pyodide build (`tools/build_web.py`): same Python in the page, offline-capable
- [x] API / server tests (12) and browser smoke tests (Playwright, local)

### M13 — Rules revision: progress, checkpoints, scouting, classes
- [x] Leave the Descent only after a boss floor (checkpoints every 5); may also push on
- [x] Per-slime dungeon progress; a party's entry floor is limited by its least-travelled member
- [x] Several parties can be inside at once and re-walk the same floors; boss bounty once per boss floor
- [x] Scouting by floor range (1–10 floors): 100 % or the whole party is lost; hidden time variance; up-front supplies
- [x] Per-floor knowledge (scouting, or having walked the floor) and staged intel
- [x] Specialization: hybrid classes from cross-training (Battlemage and 11 more, incl. Dawn Archer, Plague Archer, Nightstalker)
- [x] Outlook: experience shapes the slime (Duelist, Grinder, Delver, Pathfinder, Forager, Scholar)
- [x] Save v7 with migration from v6; web UI + CLI updated
- [x] 29 new tests

### After the prototype: where the old "Future" list went
The list kept here until October 2026 is now tracked as numbered tasks (§ 2 and § 3). Shipped since: rescue parties and
several delves (task 7), construction time and the Hatchery (10), enemy resistances and elemental floors (4), spell mutation
(3), imbue statuses and revival items (13), named dungeon registry (14), gear set bonuses (11), floor modifiers and shops (5),
retreat mid-descent (6), real-clock daily pull (16), formations (8), Bard / Paladin / Alchemist / Druid (9), campaign chapters
(15), art pass (19), PWA (20), balance harness (21), localisation framework (22), mod loader (23), relationships and offline
progress (M18, M19). Still open: reaching floor 50 for real (task 1). Ideas without a task yet: three-way hybrids and
evolving specializations, and whether job skill decays like proficiency.

### M14 — Floor-50 content
- [x] Terrain system with element effects, hazards, crit bonus
- [x] Bestiary: roles, families, ~50 monster moves, 71 monsters
- [x] Ten bosses (floors 5-50), final boss completes the Descent
- [x] Unique, mixed-family floors 1-50 (no consecutive terrain repeats)
- [x] Daily-changing Gloop Pit (terrain + featured families)
- [x] Web UI: terrain/title per floor, Today's Pit panel, victory banner
- [x] Art & sound: class headgear, SVG avatars, synthesized sound effects (task 19, M21-M22)

### M15 — Relics & the Wayfarer's Rift
- [x] Adventure dungeon: 1-5 slimes, monsters at party average + 1
- [x] Relic drops with harsh rarity odds, stars, mods
- [x] Durability, repair, shatter into materials
- [x] Levelling, star ascension (Lv10), rarity ascension with a new mod (5 stars, Lv10)
- [x] Slime-relic compatibility
- [x] Salvage: higher level = better materials
- [x] Ego relics (5-star legendary relic + 5-star legendary slime)
- [x] Web Rift tab, CLI menu [w], tests

### M16 — Slime ascension & economy
- [x] Uncommon rarity (five rarities)
- [x] Rarity ascension with white gel (10 / 100 / 1000 / 10000)
- [x] Star ascension with ascension stones (10 / 100 / 1000 / 10000), stones merge 100 > 1
- [x] Starfall Quarry, side drops, boss hoards
- [x] Merge rework: collected XP + diminishing stat share (20% > 1%)
- [x] Destruction Chamber building
- [x] Stamina attribute, star attributes per class
- [x] Rarity skills per class (Moon Slash, Aura Blade, ...)
- [x] Weapon proficiency, three-family memory, favourite weapon, named weapons, slimes repairing gear
- [x] Potions: Alchemy Lab, grades 1-5, temporary boosts, stamina potion, herbs
- [x] Four coloured herbs, combination potions, terrain-driven herb drops
- [x] Slime autonomy: 66% of stocks usable without asking

### M17 — Emotions & awakening
- [x] Thirteen emotions with battle effects (anger +ATK -DEF, sadness -SPD ...)
- [x] Events, needs and traits drive feelings; they fade; own RNG
- [x] 5-star legendaries awaken: they realise they are code (accept / despair; reworked in M23 into settled / peace / cog / despair)
- [x] Autonomy covers relics, gear and brewing
- [x] Art & sound (task 19, M21-M22)

### M18 — Relationships, budding & the Keeper
- [x] Explicit ties: friend, best friend, rival, mentor/mentee, couple (daily review)
- [x] Ties affect synergy, pre-battle feelings, mentee XP and grief
- [x] Budding: couples have children; lineage and family tree
- [x] Keeper levels, XP sources with daily caps
- [x] 16 Keeper skills in 4 branches, 4 daily abilities
- [x] Web Bonds and Keeper tabs, CLI [y] and [h]
- [x] Keeper achievements / titles, skill respec (task 12, M21)

### M19 — Time dilation, calmer UI, booklet
- [x] No feeding / petting / sleeping / talking / potions inside dungeons
- [x] Live (wall-clock) time: home x1, dungeons x3, presets, offline cap
- [x] Dungeon activities keep parties away on the wall clock; floor clear time from depth, level and knowledge
- [x] (i) tooltips, death-only dungeon subheadings, eight tabs with sub-tabs, tabbed slime card
- [x] Guide tab (booklet of attributes, with what raises / lowers them)

### M20 — Manual battles
- [x] Steppable battle engine; each party slime acts on its own turn
- [x] Hollow Descent, Gloop Pit and skirmishes (not Rift / Quarry / sparring)
- [x] Switch between manual and auto at any time (whole fight, one turn, later Pit runs)
- [x] Mini battle arena in the browser (text; renderer isolated for later animation)
- [x] Town > Merge & destroy: manual merge of any two free slimes (with preview) and the Destruction Chamber
- [x] No mediation for quarrels involving a slime that is away
- [x] Commander's gifts (purple gel) for Descent and skirmish parties; potion slots 2-6 by stars
- [x] Relic merge, gear scrap and gear merge in Town > Merge & destroy
- [x] Battle effect mechanics (bleed, stun, mark, shield, revive, delay, ...) - step 1 of the 60-skill plan
- [x] 24 rarity skills rebuilt on the new mechanics + 6 evolution skills (rank II at the second evolution) - step 2
- [x] Pure capstones (12) with class proficiency and decay - step 3
- [x] Hybrid signature upgrades and 9 hybrid capstones, second proficiency, drift from pure to hybrid - step 4 (60 skills complete)
- [x] Rename slimes and parties; Vice Keeper (delegated mediation and care inside groups, never merge/destroy)
- [x] Party leaders; Vice Keeper organises multi-party hunts and leads the group; challenges for the post (Keeper approves, duel decides)
- [x] Quarrels only between slimes that share a place (both home, or one party away together); they wait while one is away
- [x] Big colonies: Colony shows the top 10 as cards and the rest as a compact searchable list
- [x] Training facility (solo drills in the Blade Yard / Archery Range / Mana Pool for class proficiency, no star requirement); mages, medics and necromancers pulled at 3+ stars; rarity ascension keeps earned elemental mastery (growth paused)
- [x] Drill tiers (Basic / Advanced / Master) unlocked by the Training Grounds level
- [x] UI: the slime icon (three dots in a triangle) is the menu button; compact one-row header and tabs stay pinned while scrolling
- [x] Slime body shape follows rarity inside the round rarity ring (dome, eared, droplet, crowned, royal crown with halo)
- [x] Appointments in each building's own tab: 3 trainers (Training Grounds), librarian (Library), blacksmith (Armory), brewer (Alchemy), chef (Kitchen, recipes + pantry), doctor (new Hospital); 3-hour shifts, idle workers forage and can be called back; Rest Area = energy, Hospital = health (TASKS #26)
- [x] Hunts & foraging sub-tab in Dungeons; hunts give class proficiency and party bonds, a one-hour Dewdrop Pond and rare side materials
- [x] Total power breakdown on cards and parties; 100 white gel fuse into 1 purple gel; Academy layout fixed (two even columns, no phone overflow)
- [x] Rescue parties for overdue scouts (stranded for 24h); several delves at once with their own timers
- [x] Emergency Retreat from the Descent mid-segment: purple gel, morale, a deadly-risk flight
- [x] Floor modifiers (fog, darkness, ...) and wayside stops with a rest and a shop between floors
- [x] Enemy weaknesses and resistances per family; elemental floors (3, 9, 21, 27, 33, 39) that favour one element
- [x] Spell mutation: fused spells take new forms as mastery grows (✦ / ✦✦)
- [x] Foraging: slimes with no party and nothing to do hunt by themselves (toggle in Town > Jobs)
- [x] Descent reinforcements: parties on the same floor fight together, 5-star mage call for purple gel, camping limited by floor and scouting, ambush relief as a party closes in (TASKS #27)
- [x] Rarity ascension needs level 100 and 5 stars; grounded slimes can be let out
- [x] Merge / destroy only for slimes at home or resting; Council suggestions skip slimes in the field
- [x] Star attributes survive rarity ascension (kept via star_peak), scale with the new rarity, +10% per extra star
- [x] Animated arena, CLI turn prompts; no flee, by decision (tasks 17 and 18, M21)

### M21 — Content and QA pass (19-21 October 2026, direct pushes and PR #21)
- [x] Day plans for posts (eight 3-hour shifts, if-rules); reports held until the party is back; council mediation on top
- [x] Formations: front and back rows (task 8)
- [x] Bard, Paladin, Alchemist, Druid (9); timed upgrades and the Hatchery (10); gear set bonuses (11); achievements, titles, respec (12)
- [x] Imbue status and Phoenix Feather (13); named dungeon registry and Mossy Burrows (14); campaign chapters (15)
- [x] Free daily pull on the real calendar (16); animated arena (17); CLI manual fights (18); art and sound (19); PWA (20)
- [x] Balance harness (21); localisation framework (22, Spanish catalog removed); mod loader and `MODDING.md` (23)
- [x] QA report fixes: C1 and M1-M11 and the minor bugs (tasks 34-46); mobile M1 (47)
- [x] Floor-50 playtest re-run on the current rules (task 1, § 6)

### M22 — Minds, phase 1-2 (21-22 October 2026, PR #22)
- [x] SVG avatars with class gear that grows with rarity; evolution, hybrid weapon and mastery stars on the avatar
- [x] Sanity: a rarity-scaled mental reserve that caps mood; diminishing returns on talk and pet
- [x] Memory: grudges and thanks from real events shape quarrels and their stated reasons
- [x] Goals, own decisions with reasons, requests, trust, personality drift
- [x] Eight hybrids for the new classes; Bard and Druid train archery; scroll positions kept across renders

### M23 — Slime minds (27-28 October 2026, PR #23)
- [x] Behaviour harness `tools/minds_sim.py` with targets (task 53) - § 5
- [x] Feuds cool off (54); a usual mood and contentment (55); care makes friends, not rivals (56); legendary outcomes (57)
- [x] Everyday goals (58); meaning, burnout and Praise (59); grief that lasts (60); coping and comfort (61)
- [x] An inner voice that remembers (62); a day at home (63); texture, reactions and rituals (64); why it feels this way (65)
- [x] Send a whole party to Scouting, the Rift, the Quarry and Places
- [x] The static build never hangs at "Loading Python runtime": progress, a watchdog with safe mode, Repair, network-first offline copy
- [x] One planning document (this file) with the full commit history (`tools/changelog.py`)

### M25 — Strike forces and call-backs (27 October 2026)
- [x] Descent: 1-5 parties per floor by its place in the segment, a Strike force picker, one extra party by a mage's call (task 67)
- [x] No waiting after a Descent floor or wave simulation fought by hand (68)
- [x] Trainers: class and pupil rules (69); Call back everywhere a slime is away (70)
- [x] Pit and Rift sessions look after their party's needs, fixing deaths by exhaustion (71); no taking command in the Pit (72)
- [x] Trainers sharpen with every lesson (73); send several groups at once (74); call busy slimes away for a trip at a cost (75)

### M26 — Dungeon time (28 October 2026)
- [x] Per-place time dilation (x3 for every dungeon except scouting, hunting and foraging), round-up lobby cost, needs and bonds at the dungeon rate (78)
- [x] Gear and relics told apart: sell back vs break down, distinct names, a Guide section (83); eight more elements to fuse (84)
- [x] Tailwind, the first passive skill, hastens rescue parties (79); mages slightly rarer in pulls (80); camps heal and rest properly in every mode (81)

### M24 — Troublemakers and the Keeper's shadow (27 October 2026)
- [x] A troublemaker: came to blows with more than 5% of the colony (rounded down, at least 2 slimes) in 30 days, or disliked by most; one feud or being snapped at is not enough
- [x] Removing one: no morale, no stress, no grief except its partner's and best friend's at half; its foes breathe easier
- [x] Merging a liked slime starts grief just as destroying it does
- [x] The Keeper's shadow: fewer quarrels for 7 days after a removal (fear, by temperament), anxiety if it happens twice in a week; respect for 3 days after a talk or mediation (task 66)

## 5. Slime minds

How slimes feel, fight, bond and grieve, measured against how people behave in the same situations. The harness
`tools/minds_sim.py` runs seeded colonies for weeks and checks the targets below; `tests/test_minds.py` runs a small version
on every test run.

```bash
python3 tools/minds_sim.py                 # report (about 5 seconds)
python3 tools/minds_sim.py --seeds 3       # over three seeds
python3 tools/minds_sim.py --check         # exit 1 if a target fails
```

### Decisions (from the Keeper, October 2026)

1. Waking up to being code stays **legendary only** (5-star legendaries).
2. A slime **may leave** the colony, but **only with the Keeper's permission**.
3. The Keeper's care can fix **up to 70%**: it stands in for at most 70% of a slime's connection and purpose
   (`config.KEEPER_CARE_SHARE`). Enough to settle a slime, not to give it peace on its own.
4. Despair may go **darker than withdrawal**: self-neglect (it stops feeding itself; the Keeper must feed it by hand) and
   breakdowns, ending in a request to leave. Nothing beyond that.
5. Removing a **troublemaker** stays free: no morale cost, no sacrifice stress, and only its partner and best friend grieve
   it, at half depth. A troublemaker has come to blows with **more than 5% of the colony** (rounded down) in the last 30 days,
   not a fixed number of brawls; "brawling right now" no longer counts. After a removal the colony quarrels **less for a
   while**, out of fear of the Keeper; talks and mediation earn a little respect too.

### Targets

| Target | Scenario | What a person would do |
|---|---|---|
| feuds cool off | hands-off colony | a feud blows up once or twice, then people avoid each other or make up |
| anger is an episode | hands-off colony | anger at 30+ for at most a fifth of the time |
| sadness is an episode | hands-off colony | sadness at 30+ for at most a fifth of the time |
| good days happen | attentive Keeper | joy, calm and affection add up to 10+ on an ordinary hour |
| everyday joy | attentive Keeper | people who are looked after are mildly cheerful most of the time |
| care builds bonds | attentive Keeper | more friends than rivals |
| ordinary goals | hands-off colony | most slimes want something other than revenge |
| loved legendary is fine | legendary, loved | it absorbs the truth and carries on (settled or at peace) |
| lonely legendary despairs | legendary, alone | isolation is what breaks people |
| unloved worker is a cog | legendary, at a post, unseen | flat, going through the motions |
| despair can lift | recovery | company and care pull people back out |
| but not overnight | recovery | recovery takes days to weeks |
| grief lasts | partner dies, no support | one to three weeks |
| company shortens grief | the same, a friend at home and daily talks | under 15 days |
| friends look after each other | hands-off colony | friends notice when someone is down and cheer them up |
| bad feelings are acted on | hands-off colony | people do something with a bad feeling |
| unseen work burns out | a common at one post, unseen | the same post every day, nobody noticing: going through the motions |
| praise keeps the spark | the same, praised daily | recognition gives the same work meaning |
| most slimes are not burned out | hands-off colony | a varied colony life is not a grind |
| a removal calms the colony | 40 slimes, the worst fighter destroyed, 12 replays with and without the shadow | the others think twice before picking a fight for a few days (x0.85 or less over 3 days) |

### Before and after (seed 1, 20 slimes, 45 days)

| | Before | After |
|---|---|---|
| Brawls, hands-off | 1,054 (one feud: 131) | 68 (at most 2 per feud) |
| Anger at 30+, hands-off | 77% of the time | 4% |
| Sadness at 30+, hands-off | 72% | under 1% |
| Everyday joy, attentive | 0 | about 9 |
| Rivals vs friends, attentive (first test) | 26 vs 15, no best friends or couples | 5 vs 18 |
| Legendary, loved | despair | at peace |
| Legendary, working and unseen | despair | a cog |
| Despair after 30 days of care | never lifted | lifts in about a week |

### How it works

- **Feuds** (`ai.py`): spats mend on their own (kind slimes fastest, grumpy and proud slowest, grudges make it harder); once
  a day a guilty slime may apologise or a friend of both may make peace; after a brawl both keep apart for a day; a feud
  brawls at most twice, then becomes a 7-day cold war. A failed Keeper's talk means "not ready yet" (try again in 6 hours).
  Making up counts towards friendship and leaves both calm for a day.
- **Usual mood** (`emotions.py`): feelings settle to a baseline from traits plus contentment (a slow 0-100 that follows
  mood over days). Needs keep a feeling simmering (at most 60); only events push it higher.
- **Awakening** (`awakening.py`): a 14-day record of care, connection, purpose and hardship decides settled, peace, cog or
  despair, reviewed every 3 days. Despair deepens: withdrawal, then self-neglect, then breakdowns and a request to leave.
  A cog asks to be taken off its post, later to leave.
- **Meaning** (`meaning.py`): every slime keeps a week of care, connection, purpose and hardship (a legendary two weeks).
  Flat days while not lonely burn a slime out (muted joy and pride, mood capped, asks off its post); Praise, choice and
  variety bring the spark back.
- **Grief** (`grief.py`): those close to a slime that dies (is sacrificed, or leaves: half) grieve by tie - partner 90,
  best friend 70, mentor 50, friend 45, acquaintance 25 - fading 4 a day (+3 with a friend at home, +2 on a day the Keeper
  talks). It holds sadness and loneliness up, returns on weekly anniversaries and in the dungeon where it happened, and a
  gathering at the Memorial Pond eases it and brings the mourners closer.
- **Coping and comfort** (`coping.py`): a bad feeling at 50+ is acted on once a day in a style from personality (talk it
  out, help others, train, face it, sleep, comfort food, withdraw, snap at someone, or dwell); friends at home cheer up a
  friend who is down; fear and joy spread a little in parties away; cuddles go to friends and are summed up daily.
- **Voice** (`voice.py`): a talk answers from its grief, its strongest memory of someone, its goal, burnout or a good
  stretch, or its strongest feeling - never the same line twice in a week.
- **A day at home** (`routine.py`): meals together at 8, 13 and 19 (table-mates grow closer), an evening hobby at 20 from
  outlook or personality (time of its own: meaning; a shared hobby: closeness). Sitting idle is not an activity, and a
  praised day is not an unseen grind.
- **Texture, reactions, rituals**: bonds fade on days not shared, partners can be jealous, kind or guilty slimes apologise
  for old grudges and the kind forgive sooner (`relationships.py`, `memory.py`); a defeat shames the proud, frightens the
  timid, spurs the brave (`appraisal.py`); hatch days every 30 days (noticed when the Keeper remembers), couple
  anniversaries, and a feast at dinner after a boss falls (`rituals.py`).
- **Why** (`emotions.note_cause`): feelings keep their strongest reasons, shown on the Mind tab; settled feelings show their
  usual reason; the Colony tab lists who is struggling and why.
- **Goals** (`mind.py`): a weighted pool - get stronger, master a style, see a friend, make a new one, court someone, teach
  a mentee, explore, make something, take it easy, be noticed - shaped by traits, outlook, needs and ties; a grudge is one
  candidate. Thanks outlast minor grudges when memory is full. Slimes who share the colony's days (idle, resting, at a post)
  grow closer.
- **Leaving** (`mind.py`, `Game.depart`): only with the Keeper's yes; friends miss it, its gear stays, Records lists it.
- **Troublemakers** (`Game.unwelcome`): each slime remembers whom it came to blows with in the last 30 days (`Slime.fights`;
  a quarrel started by snapping counts only against the one who snapped). More different slimes than 5% of the colony
  (rounded down, never fewer than 2), or being disliked by most, makes a troublemaker. Merging or destroying one costs no
  morale or stress; its partner and best friend grieve at half depth, nobody else; those it fought with get calmer, a little
  more content, and their grudges against it halve. A liked slime is grieved whether merged or destroyed.
- **The Keeper's shadow** (`Game.wary`, `ConflictEngine.chance`): after a removal everyone's quarrel odds are halved, easing
  back over 7 days; slimes with fights of their own feel fear and hold back to x0.3 (timid most, grumpy and proud less,
  brave hardly), and a second removal within the week makes them anxious. A talk or a successful mediation makes a slime
  start quarrels x0.8 as often for 3 days. Grudges are not erased, only put off: over the whole week the colony has about
  10% fewer quarrels, over the first three days about 25% fewer.

### Still to do

Every task from the October 2026 plan (T1-T16, tasks 53-65) is done. Run `python3 tools/minds_sim.py --seeds 3 --check`
after any change to feelings, relationships or needs.

## 6. Floor-50 playtest

Generated with `python3 tools/playtest.py` (seeded, repeatable). It answers: *how strong must a party be to win each floor
of the Hollow Descent, and how long does it take to get there?* The reference party is the conservative case: one each of
Barbarian, Ranger, Mage, Medic and Rogue with **no gear, relics, potions, elements, bonds or morale effects**, stars following
the rarity's star-level table, evolved to the stage its level allows, class proficiency 100 (capstones usable for legendaries).
"Min level" is the lowest party level with a >= 70% win chance over 12 seeded fights per level tested ("scouted" adds the
intel bonus). "Pit runs" is how many Gloop Pit depth-3 runs a party needs to reach that level from level 1 under the real reward rule
(`config.pit_xp_per_run`, 2 game hours each); "real hours" assumes the Pit's x3 dungeon time (`places.py`) at live speed 1x. The Descent's own XP is not counted,
so this overstates the grind a little.

### What the playtest found (and what was done)

1. **A real AI bug (fixed).** At the start of a fight every slime with a set-up skill (Mark Prey, Arcane Focus, Sacred Ward,
   Berserker's Oath ...) spent its first turn buffing while the foes wiped the party in round one. Set-up skills (buffs, marks,
   debuffs, oaths) are now skipped when the party would win in under about 2.5 rounds. Floor 47 needed level 93 before and ~60
   after, floor 41 74 -> 42, floor 18 30 -> 20.
2. **Floor threat was lumpy (fixed in part).** Monster families differ wildly (five Stone Giants were several times a normal
   floor). Each floor's threat, (sum of enemy HP) x (sum of enemy damage), is now pulled into a band around a curve
   (`config.FLOOR_THREAT_TARGET`, bands 0.8-1.25 for ordinary floors, 0.9-1.3 for bosses; the enemy mix is unchanged, only stats
   are rescaled). Floor 32 went from ~63-82 to ~45, floor 50 from ~78 to ~63 for the common party.
3. **Floor 50 is reachable.** (Re-run after the equal star levels and formations; 24 seeded fights per level.) A common party needs about level 57 (51 scouted), uncommon 50, rare 41, epic 31, legendary 25; none is unwinnable at level 100. Commons dropped from ~63 because every rarity now earns its stars at levels 10/25/50/80 (commons used to wait for 30/60/100).
4. **Win rates are cliffs.** A party goes from 0% to 100% over two or three levels, and the late bosses (35, 40, 45, 50) sit at
   level ~52-63 for commons because levels 30 and 60 grant stars and the stage-2 multiplier: that is a design step, not a
   threat spike. Mean deviation of a floor from its neighbours is 0.16 (limit 0.22): `python3 tools/playtest.py --smoothness`.
5. **Enemy area attacks matter.** An area attack hits all five slimes, so a floor with four area users deals about twenty times
   a single hit per round. An "area-aware" threat measure did not predict the required level better than HP x damage, so the
   simple one is used.
6. **Time to floor 50 (fixed, task 25).** Pit XP used to follow the *level*, so a legendary at level 22 earned tiny rewards
   against an XP bill 16x larger: common needed ~580 runs (~390 real hours at x3) and legendary ~2,700 runs. A won Pit run now
   pays the XP a level costs divided by the runs a level should take (`PIT_RUNS_PER_LEVEL` = 3.5 for a common, +50% per rarity
   step, deeper depths pay more: 0.6 / 0.8 / 1 / 1.3 / 1.7). Result for floor 50: common ~217 runs (~144 real hours),
   rare ~273 (~182 h), legendary ~220 (~147 h): about a week of continuous dungeon time for any rarity (live mode keeps parties
   working while the page is closed), instead of months.

### Tables (floors 1, 5, 10 ... 50; run with `--step 1` for every floor)

#### Common

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 8 | 7 | 24 | 16 |
| 10 | BOSS | 11 | 10 | 35 | 23 |
| 15 | BOSS | 18 | 18 | 59 | 39 |
| 20 | BOSS | 25 | 24 | 84 | 56 |
| 25 | BOSS | 25 | 25 | 84 | 56 |
| 30 | BOSS | 31 | 31 | 105 | 70 |
| 35 | BOSS | 45 | 45 | 154 | 102 |
| 40 | BOSS | 50 | 50 | 171 | 114 |
| 45 | BOSS | 49 | 49 | 168 | 112 |
| 50 | BOSS | 57 | 51 | 196 | 130 |

#### Uncommon

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 6 | 6 | 26 | 17 |
| 10 | BOSS | 10 | 10 | 47 | 31 |
| 15 | BOSS | 15 | 15 | 73 | 49 |
| 20 | BOSS | 24 | 22 | 120 | 80 |
| 25 | BOSS | 19 | 18 | 94 | 63 |
| 30 | BOSS | 31 | 31 | 157 | 105 |
| 35 | BOSS | 44 | 42 | 225 | 150 |
| 40 | BOSS | 50 | 48 | 257 | 171 |
| 45 | BOSS | 43 | 40 | 220 | 147 |
| 50 | BOSS | 50 | 50 | 257 | 171 |

#### Rare

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 5 | 4 | 28 | 18 |
| 10 | BOSS | 9 | 8 | 56 | 37 |
| 15 | BOSS | 13 | 12 | 84 | 56 |
| 20 | BOSS | 18 | 17 | 119 | 79 |
| 25 | BOSS | 16 | 14 | 105 | 70 |
| 30 | BOSS | 25 | 25 | 168 | 112 |
| 35 | BOSS | 32 | 32 | 217 | 144 |
| 40 | BOSS | 40 | 39 | 273 | 182 |
| 45 | BOSS | 35 | 34 | 238 | 158 |
| 50 | BOSS | 41 | 41 | 280 | 186 |

#### Epic

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 2 | 2 | 8 | 5 |
| 10 | BOSS | 5 | 5 | 35 | 23 |
| 15 | BOSS | 11 | 11 | 87 | 58 |
| 20 | BOSS | 14 | 13 | 113 | 75 |
| 25 | BOSS | 12 | 11 | 96 | 64 |
| 30 | BOSS | 22 | 21 | 183 | 122 |
| 35 | BOSS | 31 | 31 | 262 | 175 |
| 40 | BOSS | 31 | 31 | 262 | 175 |
| 45 | BOSS | 31 | 31 | 262 | 175 |
| 50 | BOSS | 31 | 31 | 262 | 175 |

#### Legendary

| Floor | Boss | Min level, no intel | Min level, scouted | Pit runs to reach | ~real hours (x3) |
|---|---|---|---|---|---|
| 1 |  | 1 | 1 | - | - |
| 5 | BOSS | 1 | 1 | - | - |
| 10 | BOSS | 1 | 1 | - | - |
| 15 | BOSS | 6 | 5 | 52 | 35 |
| 20 | BOSS | 10 | 10 | 94 | 63 |
| 25 | BOSS | 10 | 10 | 94 | 63 |
| 30 | BOSS | 12 | 11 | 115 | 77 |
| 35 | BOSS | 25 | 25 | 252 | 168 |
| 40 | BOSS | 27 | 26 | 273 | 182 |
| 45 | BOSS | 20 | 19 | 199 | 133 |
| 50 | BOSS | 25 | 25 | 252 | 168 |

### Time to floor 50 (Pit runs only, no gear)

| Rarity | Min level at floor 50 | Pit runs | ~real hours (x3) |
|---|---|---|---|
| Common | 57 (51 scouted) | ~196 | ~130 |
| Uncommon | 50 | ~257 | ~171 |
| Rare | 41 | ~280 | ~186 |
| Epic | 31 | ~262 | ~175 |
| Legendary | 25 | ~252 | ~168 |

About a week of continuous dungeon time for any rarity, as intended by task 25. With the one-day session cap (12 runs of 2 hours per session) that is roughly 8-12 farming sessions per rarity step.

### Follow-ups

- Smoothness regression (`--smoothness`): mean deviation 0.132 against the 0.22 limit, still passing after formations, equal star levels and the XP changes.
- Still to do: playtest **with gear, relics, elements and potions** (the real game); the harness covers the conservative no-gear case only.
- Decide how much of the climb should come from the Descent itself (its floor XP is small next to the Pit now).
- Re-run this harness after every balance change and run `--smoothness` as the regression check.

*Re-checked 28 October 2026 on the current code: `--smoothness` mean deviation 0.129 (limit 0.22); the reference fights
are unchanged since the last full run (21 October), so the tables above still hold.*

## 7. Balance report

Seeded Pit fights, 12 trials per cell, no gear or potions.

### Pit depth (balanced party, common)

| level | depth 1 | depth 2 | depth 3 | depth 4 | depth 5 |
|---|---|---|---|---|---|
| 10 | 100% (2.3r) | 100% (2.4r) | 100% (2.9r) | 33% (4.0r) | 33% (6.7r) |
| 20 | 100% (2.5r) | 100% (2.8r) | 100% (2.8r) | 92% (2.8r) | 100% (3.1r) |
| 30 | 100% (2.2r) | 100% (2.2r) | 100% (2.2r) | 67% (3.3r) | 58% (3.3r) |
| 40 | 100% (2.2r) | 100% (2.4r) | 100% (2.8r) | 100% (2.6r) | 100% (2.8r) |

### Rarity at equal level (balanced party, Pit depth 3)

| level | common | uncommon | rare | epic | legendary |
|---|---|---|---|---|---|
| 10 | 100% | 100% | 100% | 100% | 100% |
| 25 | 100% | 100% | 100% | 100% | 100% |
| 40 | 100% | 100% | 100% | 100% | 100% |

### Classes (the class plus four balanced partners, rare, enemies 9 levels above the party)

| class | lv 15 | lv 30 | lv 45 | rounds @30 |
|---|---|---|---|---|
| barbarian | 100% | 75% | 92% | 2.8 |
| mage | 100% | 83% | 100% | 3.0 |
| medic | 100% | 83% | 100% | 2.8 |
| rogue | 100% | 83% | 92% | 2.8 |
| ranger | 100% | 83% | 92% | 2.8 |
| necromancer | 100% | 75% | 92% | 3.2 |
| bard | 100% | 75% | 100% | 3.3 |
| paladin | 100% | 83% | 92% | 2.6 |
| alchemist | 100% | 83% | 92% | 3.3 |
| druid | 100% | 83% | 100% | 3.4 |

### Capstones (legendary 5-star, proficiency 100 vs 0, level 25, enemies 19 levels above; rounds to win)

| class | with | without |
|---|---|---|
| barbarian | 100% (1.0r) | 100% (1.0r) |
| mage | 100% (1.0r) | 100% (1.0r) |
| medic | 100% (1.0r) | 100% (1.0r) |
| rogue | 100% (1.0r) | 100% (1.0r) |
| ranger | 100% (1.0r) | 100% (1.0r) |
| necromancer | 100% (1.3r) | 100% (1.3r) |
| bard | 100% (1.0r) | 100% (1.0r) |
| paladin | 100% (1.0r) | 100% (1.0r) |
| alchemist | 100% (1.0r) | 100% (1.1r) |
| druid | 100% (1.0r) | 100% (1.0r) |

### Reading the report

- **Classes** stay within about 10 points of each other at every level: no class is a trap or a must-have in a mixed party.
- **Pit depth 1-3** is a formality at level parity (about 2 rounds); only depth 4-5 near a stage cap (levels 10 and 30) bites.
- **Rarity** barely matters in the Pit at equal level; it matters in the Descent, where the playtest report (§ 6) is the guide.
- **Legendary 5-star** parties clear Pit waves in about one round even far above their level: the Pit stops being a test long before then.
  The Descent, not the Pit, is where capstones are tuned; if the Pit should stay relevant late, scale `dungeon.grind_level` with depth.

*Re-generated 28 October 2026 (`python3 tools/balance.py`): identical to the report above.*

## 8. Commit history, first to last

Every commit since the first, oldest first, grouped by the pull request (or direct push) that brought it in. Rebuilt by
`python3 tools/changelog.py`.

<!-- changelog:start -->

171 commits, oldest first. Generated by `python3 tools/changelog.py` at `3713aac`.

### Straight to the main line (2026-10-10)

- `0b230f6` 2026-10-10 — Initial commit

### Pull request #1 (merged 2026-10-14)

- `586386f` 2026-10-10 — Add offline slime gacha prototype with docs, engine, CLI and tests
- `5774976` 2026-10-10 — v0.2: permadeath, star ratings, silver/gold, daily free pull, parties
- `6f5c999` 2026-10-11 — v0.3: white/purple gel, rough main dungeon, grinding dungeon
- `c19e89f` 2026-10-11 — Friendlier currency names in status line
- `c6c0767` 2026-10-14 — v0.4: training grounds, elements, library and spell fusion
- `9a3e3dd` 2026-10-14 — v0.5: sparring styles, rest area, buildings, compatibility, morale, council
- `06b7766` 2026-10-14 — v0.6: no-exit delves, scouting intel, Pit penalties, equipment, sacrifice stress

### Pull request #2 (merged 2026-10-14)

- `005a677` 2026-10-14 — v0.7: browser edition (local server + static Pyodide build)
- `27e4923` 2026-10-14 — v0.8: per-slime progress, checkpoint exits, floor scouting, specialization, outlook
- `26e7e25` 2026-10-14 — Floor 50 content: terrains, bestiary, bosses, unique floors, daily Pit

### Merge without a pull request number: Merge remote-tracking branch 'origin/claude/slime-gacha-prototype' (merged 2026-10-16)

- `1a634cc` 2026-10-14 — Wayfarer's Rift adventure dungeon and relic system (durability, stars, mods, compatibility, ego)
- `26c81a9` 2026-10-14 — Slime ascension: five rarities, rarity/star ascension, stones, Starfall Quarry, merge rework, Destruction Chamber
- `b19c3da` 2026-10-14 — Stamina, star attributes, rarity skills, potions and Alchemy Lab, weapon families and proficiency
- `caf4d83` 2026-10-15 — Coloured herbs, combination potions, slime autonomy (66% of stocks)
- `2b43407` 2026-10-15 — Emotions with battle effects, awakening of 5-star legendaries, autonomy for relics/gear/brewing
- `b8db951` 2026-10-15 — Relationship tree with budding children, and the Keeper skill system

### Pull request #4 (merged 2026-10-16)

- `477f5fb` 2026-10-16 — Run Pyodide in a web worker so long sessions never freeze the page
- `a78557f` 2026-10-16 — No care inside dungeons; live (wall-clock) time with dilation; floor clear time from level, knowledge and depth
- `e8bcd7f` 2026-10-16 — Calmer UI (tabs with sub-tabs, info tooltips, tabbed slime card), Guide booklet, live time controls
- `e87b23f` 2026-10-16 — Pickers list only available slimes and parties (training, sparring, library, expeditions)
- `b869af3` 2026-10-16 — Add GitHub Pages workflow that builds and publishes the static edition

### Pull request #5 (merged 2026-10-17)

- `8f5ec30` 2026-10-16 — Move elements reference and hybrid-class list from the Academy to the Guide
- `990ecce` 2026-10-16 — Fix pickers: the slime or party a dropdown shows is the one the action uses (sparring, library, expeditions)
- `96d0950` 2026-10-16 — Manual turn-based battles: each slime acts on its own turn in the Descent, Pit and skirmishes; switch to auto any time; text battle arena
- `4d87bf5` 2026-10-16 — Dropdowns: every select's shown value is read at click time; XP per level scales with rarity and stars
- `02a8ea2` 2026-10-16 — Stars need level 10/30/60/100; rarity ascension resets stars to 1; XP per level doubles per rarity; stage caps 10/30/100
- `72088e8` 2026-10-16 — Star requirements scale with rarity (level and stones); star attributes boosted by rarity

### Pull request #6 (merged 2026-10-17)

- `6f8865c` 2026-10-16 — Level-100 balance: diminishing stat growth above level 50, Pit XP keeps pace with level cost
- `f2ad4e2` 2026-10-16 — Docs and Guide for level-100 balance

### Pull request #7 (merged 2026-10-17)

- `f808a59` 2026-10-16 — Town: Merge & destroy tab (manual merge with preview, destroy); no mediating quarrels of slimes that are away
- `f067495` 2026-10-16 — Commander's gifts (purple gel) for Descent/skirmish parties, potion slots by stars, relic merge and gear scrap/merge
- `c24d65f` 2026-10-16 — Battle effect mechanics (fx.py): bleed, stun, mark, buffs, shield, revive, delay, pierce, execute and more
- `378530c` 2026-10-16 — Arena shows unit statuses
- `5566378` 2026-10-16 — Rebuild the 24 rarity skills on the fx mechanics and add 6 evolution skills (rank II at second evolution)
- `6f56e11` 2026-10-17 — Pure capstones (12) with class proficiency and decay; fix info-badge style clash
- `a30d859` 2026-10-17 — Hybrid skills: upgraded signatures, 9 hybrid capstones scaled by a second proficiency, drift from pure to hybrid
- `3dccbd8` 2026-10-17 — Away timers: a bar and per-slime/party chips counting down hunts, study, dungeon trips and the Descent (real-time in live mode)
- `f479337` 2026-10-17 — Rename slimes and parties; Vice Keeper (delegated mediation and care inside groups, never merges or destroys)
- `6136267` 2026-10-17 — Party leaders, Vice Keeper hunts across parties, challenges for the post (Keeper approves, duel decides)

### Pull request #8 (merged 2026-10-17)

- `9346bcc` 2026-10-17 — Floor-50 playtest harness and report; AI no longer wastes opening turns on set-up skills in short fights; written task checklist
- `476a996` 2026-10-17 — Floor threat smoothing with a regression check in the playtest harness; refreshed floor-50 report
- `f9d695d` 2026-10-17 — Quarrels need a shared place and wait while one is away; big colonies show the top 10 as cards and the rest as a compact list with search
- `73dcc17` 2026-10-17 — Training facility (solo drills for class proficiency, no star requirement); mages are pulled at 3+ stars
- `e16b5d8` 2026-10-17 — Medics and necromancers are pulled at 3+ stars; rarity ascension keeps earned elemental mastery (growth paused until the stars catch up)
- `8a4422b` 2026-10-17 — Drill tiers (Basic, Advanced, Master) unlocked by the Training Grounds level
- `50b42f7` 2026-10-17 — Pit XP tied to the XP a level costs: floor 50 takes about 145-180 real hours at x3 for any rarity
- `8ea2c54` 2026-10-17 — Slime icon is the menu button; compact sticky header and sticky tabs
- `9149b6b` 2026-10-17 — Slime body shape follows rarity inside a round rarity ring
- `fb0d7e2` 2026-10-17 — Editable slime colour, duel pickers exclude each other, party-spar hint
- `3693b8f` 2026-10-17 — Roadmap: occupations (chef, blacksmith, trainer) as the next job feature

### Pull request #9 (merged 2026-10-17)

- `fa9fddf` 2026-10-17 — Merge only at home, star attributes kept through rarity ascension, roadmap: occupations decisions and Descent reinforcements
- `150b2ac` 2026-10-17 — Rarity ascension needs level 100 and 5 stars; Let out button for grounded slimes
- `76c81d6` 2026-10-17 — Descent reinforcements: limited camping, ambush relief, joint fights, mage call for purple gel
- `ddf03cc` 2026-10-17 — Mage call no longer requires the called party to have cleared the floor above
- `8c5db03` 2026-10-17 — Search boxes keep focus and cursor while typing (phone keyboard no longer closes)
- `e289e21` 2026-10-17 — Occupations: Chef, Blacksmith and Trainer in Town > Workshops (switchable, no wages, per-trade levels)
- `7824b78` 2026-10-17 — Jobs live in their own buildings (new Kitchen, Armory, Library, Training Grounds), add Librarian; idle party-less slimes forage on their own
- `ebdaeef` 2026-10-17 — Pulling 10 or more at once costs 10% less

### Pull request #10 (merged 2026-10-17)

- `861a5bf` 2026-10-17 — Separate Rift and Quarry sub-tabs labelled by prize; purple lure in the Gloop Pit (x1.5 XP, x3 gear)
- `c05a39f` 2026-10-17 — Three new class paths into archery: Dawn Archer, Plague Archer, Nightstalker (signature skills and capstones)
- `3f36353` 2026-10-17 — Spell mutation: fused spells change form at set mastery levels, with Academy listing and card markers
- `4b9e3d0` 2026-10-17 — Enemy weaknesses/resistances per family and elemental floors, shown in intel and the Guide
- `d83696b` 2026-10-17 — Floor modifiers (fx statuses over a floor, revealed by scouting) and wayside stops with a safe rest and shop
- `bc6141e` 2026-10-17 — Emergency retreat from the Descent: costed (purple gel, morale, stamina) and ambushable; free exit at checkpoints stays
- `079932c` 2026-10-17 — Rescue parties for overdue scouts (stranded for 24h); several delves at once covered with live-timer tests
- `ba165d7` 2026-10-17 — Economy tweaks: flat 3-gel party spar, Pit knock-outs cost morale only, farming dungeons drop a little extra, waking and brawls cost mood, training pickers tag sleeping/working/hurt slimes
- `7b13dad` 2026-10-17 — Appointments in each building's own tab: three trainers, librarian, blacksmith (forges), brewer, chef (recipes, pantry, hunger counter), doctor (new Hospital); 3-hour shifts with bonus, idle workers forage and can be called back; Rest Area restores energy, Hunts & foraging tab
- `78a548b` 2026-10-17 — Party sparring is now two parties fighting each other as teams (flat 3 gel): style XP, class proficiency and bonds inside each party raise synergy

### Pull request #11 (merged 2026-10-17)

- `fe377b7` 2026-10-17 — Hunts: proficiency and bonds, one-hour Dewdrop Pond, rare side materials, sleeper/worker handling and tags; free waking above half energy; total power with breakdown
- `796e429` 2026-10-17 — Fuse white into purple gel, Academy layout fix (even columns, no overflow), guide and docs
- `3fd0c6e` 2026-10-17 — Academy split into Training and Library sub-tabs; faster energy recharge; three-digit power tag beside slimes

### Pull request #12 (merged 2026-10-17)

- `e29c481` 2026-10-17 — About tab: version 1.001, game summary and mechanics, remaining roadmap
- `22ba63c` 2026-10-17 — Fix scouting form duplicated in the Descent tab (only the first floor was sent); hunts give mild XP that scales with the cost of a level
- `ee54042` 2026-10-17 — Hunt and Descent XP use a rarity multiplication factor like the Gloop Pit (level cost over extra fights per rarity step)
- `6d5777d` 2026-10-17 — Dungeons rework: wave simulation, scouting by any slime, rescue shortcut, one-time stranded amnesty
- `fbbb123` 2026-10-17 — Wave simulation: monster level range, number of waves, fixed XP by monster and level
- `02a3d4c` 2026-10-17 — Rescue: several parties (any number of rescuers) can go together, bigger force helps

### Pull request #13 (merged 2026-10-17)

- `b6c0547` 2026-10-17 — Slime faces: a mouth and eyes that follow mood, overridden by strong feelings
- `8900901` 2026-10-17 — Slimes can refuse posts and expeditions; wake-everybody button; appointment pickers list everyone in town with status tags
- `160c673` 2026-10-17 — Vice Keeper can hold a post in town (and a worker can become Vice Keeper); duties still reach slimes at home

### Pull request #14 (merged 2026-10-18)

- `1615ef4` 2026-10-17 — Phones: 16px fields stop Safari's focus zoom (page looked narrower than the screen); nothing may widen the page
- `2831ec4` 2026-10-17 — Serve cooked dishes by hand: serve all hungry, per-slime serve in the Kitchen, Serve a dish on the slime card

### Pull request #15 (merged 2026-10-18)

- `3d135fb` 2026-10-18 — Fix drills always going to the Blade Yard: use the shown yard, a new slime starts in its own, party drills use each member's own yard
- `25db08f` 2026-10-18 — Separate training and sparring facilities: per-yard pickers and in-training lists, no 'everyone drills', seven upgradable buildings with capacity, costly Party Arena

### Pull request #16 (merged 2026-10-18)

- `6501808` 2026-10-18 — Fix save export: use the live save (not only the browser copy), share sheet on phones, attached download link, copy-to-clipboard fallback
- `ec3cde4` 2026-10-18 — Scouting onward over scouted floors, Hospital ward with beds and faster healing, call back / rest / hospital buttons, no morale change for merging a nuisance, party training in the Party Arena
- `dd34571` 2026-10-18 — Party Training Yard (1 white gel), scouting opened by floors cleared by anyone, nuisance = brawled or disliked (not weak), quick-care buttons, what's new notice and backup reminder

### Pull request #17 (merged 2026-10-18)

- `24a4f89` 2026-10-18 — Turn mode keeps sessions timed (party away with hours left), wave simulation takes its time in live mode, dismiss from work in the profile, save export opens the share sheet inside the tap
- `3d4bf20` 2026-10-18 — Stars need the same levels for every rarity (10/25/50/80) with a ready-to-ascend note; parties inside the Descent, Pit, Rift, Quarry, scouting, waves and facilities listed with their timers

### Pull request #18 (merged 2026-10-18)

- `ecca424` 2026-10-18 — Farming sessions capped at one day (camping included) with the time shown before starting; hospital patients labelled as such

### Pull request #19 (merged 2026-10-18)

- `dae0a42` 2026-10-18 — Disband stays possible unless the party is away as a party (Descent, rescue, scouting, farming dungeons, waves, party sparring or training); members busy alone no longer block it

### Straight to the main line (2026-10-19)

- `131ce0e` 2026-10-19 — Council mediation on top, class filter, party members removable unless the party is away together, compact Away bar, tired slimes use a free Rest Area bed, feeding uses the pantry first, wrapping floor-modifier chip, sleep threshold choice
- `37372da` 2026-10-19 — Day plans for posts: eight 3-hour shifts (work/forage/sleep) and if-rules (no patients, pantry days, hurt count, low energy)

### Pull request #21 (merged 2026-10-22)

- `286dbc5` 2026-10-19 — Dungeon and sparring reports and hauls are held until the party is back, then the report opens by itself
- `8bd2080` 2026-10-21 — Formations: front and back rows for slimes and monsters (melee reaches the front row only, back row sheltered), row controls on the party card and in Orders, arena draws rows and offers reachable targets
- `8f4e615` 2026-10-21 — Add the QA report findings and the mobile plan to the task list, TASKS.md and the About roadmap (tasks 34-52)
- `569323c` 2026-10-21 — QA C1: damaged or foreign saves are refused with a message (SaveError), never a traceback; boot shows a recovery screen with backup restore, copy, import and start-new; rotating backup every five minutes
- `c4c9d00` 2026-10-21 — Re-run the floor-50 playtest on the current rules: refreshed tables for all five rarities and the time to floor 50
- `3f0e0c0` 2026-10-21 — Add Bard, Paladin, Alchemist and Druid classes
- `8f5ed45` 2026-10-21 — Timed building upgrades and the Hatchery
- `f0e1621` 2026-10-21 — Gear set bonuses
- `c56d86d` 2026-10-21 — Keeper achievements, titles and skill respec
- `c1de8f2` 2026-10-21 — Imbue status (Flame Brand) and Phoenix Feather revival items
- `b235e6f` 2026-10-21 — Named dungeon registry: places as data, Mossy Burrows
- `2916d36` 2026-10-21 — Campaign chapters from STORY.md
- `90d6f50` 2026-10-21 — Free daily pull follows the real calendar (also closes QA M3)
- `ff0f9c0` 2026-10-21 — Animated battle arena (CSS, inside ARENA.render)
- `cd9b66a` 2026-10-21 — CLI: fight Pit runs and wave simulations by hand (no flee, documented)
- `4276d93` 2026-10-21 — Art pass: class headgear on slimes and synthesized sound effects
- `8de4507` 2026-10-21 — PWA: manifest, icons and offline service worker
- `f5026fd` 2026-10-21 — Balance harness (tools/balance.py) and report
- `6f908b6` 2026-10-21 — Mod loader: register(), ENABLED, safe loading, example pack and MODDING.md
- `c869559` 2026-10-21 — Localisation: i18n layer and Spanish catalog
- `d81f002` 2026-10-21 — QA M1: a reload mid-battle fights the battle out instead of undoing it
- `a04bad9` 2026-10-21 — QA M2: exact odds shown on the Gacha tab; README, SDD and gacha docstring corrected
- `14eb3c1` 2026-10-21 — QA M4: detect a second tab and pause the stale one
- `160f42a` 2026-10-21 — QA M5: importing a save is previewed, confirmed and keeps the old colony as a backup
- `3513e18` 2026-10-21 — QA M6: visible warning when the browser cannot keep the save
- `e29eb03` 2026-10-21 — QA M7: +1 day at 250 slimes in 0.7 s (healer aura, quarrel scan, compatibility caches)
- `f69d470` 2026-10-21 — QA M8: bounded pulls and colony size, saves written on a timer and when the page is hidden
- `decd291` 2026-10-21 — Fix test helper for the pull cap
- `c44b088` 2026-10-21 — QA M9/M10: time controls in a fixed bottom bar, toasts let taps through; shorter What's new
- `4ba490a` 2026-10-21 — QA M11: keyboard access for cards, dialog roles and focus trap
- `b163ad5` 2026-10-21 — QA minor bugs: Back button, stars text, contrast, tap targets, calmer animation, guarded live sync, spell name checks
- `6c2c1bd` 2026-10-21 — Mobile M1: per-tab scroll, purple ten-pull confirm, safe areas
- `a2191db` 2026-10-21 — Remove the Spanish catalog; keep the localisation framework

### Pull request #22 (merged 2026-10-22)

- `6c6895b` 2026-10-21 — Hats sit lower on the head (clear of face and rarity crowns); brighter slime bodies
- `cebb70e` 2026-10-21 — Avatar redraw: SVG class gear that grows with rarity (hat, item, aura, wings), faces kept
- `a8ce4b5` 2026-10-21 — Sanity: a rarity-scaled mental reserve that caps mood; diminishing returns on talk and pet
- `21bf02e` 2026-10-21 — Slime memory: grudges and thanks from real events shape quarrel odds and stated reasons
- `b8a35bd` 2026-10-21 — Slime minds (phase 2): goals, own decisions with reasons, requests, trust, personality drift
- `3900b19` 2026-10-21 — Balance disciplines: Bard and Druid train at the Archery Range (3 sword / 3 archery / 4 magic)
- `1824d92` 2026-10-21 — Eight hybrids for the new classes (signature skills and capstones); avatars show evolution, hybrid weapon and mastery stars
- `22969c0` 2026-10-21 — Keep scroll positions and the typing box across renders (top bar, tab bar, lists, dialogs)

### Pull request #23 (merged 2026-10-27)

- `90caa71` 2026-10-27 — Minds harness: colony, legendary, recovery and grief scenarios with behaviour targets (tools/minds_sim.py)
- `be510b4` 2026-10-27 — Feuds cool off: spats mend on their own, apologies and friends make peace, time apart after a brawl, at most two brawls then a cold war
- `49a2009` 2026-10-27 — Feelings settle back to a usual mood: trait baselines and a slow contentment, needs simmer but never boil
- `c798b04` 2026-10-27 — Care makes friends, not rivals: a failed talk means not yet, making up counts towards friendship, calmer trait odds
- `e50a0c9` 2026-10-27 — Awakened legendaries read their whole life: settled, at peace, a cog or in despair; despair deepens; leaving needs the Keeper
- `fd57383` 2026-10-27 — Minds docs and regression test: behaviour targets run with the unit tests; decisions, before/after and remaining tasks recorded
- `902401e` 2026-10-27 — About roadmap lists the open Slime minds tasks (58-65); What's new describes the change
- `8cda741` 2026-10-27 — Send a whole party to Scouting, the Wayfarer's Rift, the Starfall Quarry and Places
- `90fdb7c` 2026-10-27 — Goals people actually have: a weighted pool of everyday wishes instead of revenge by default
- `2b05dfb` 2026-10-27 — Meaning for every slime: a week's record, burnout for flat days, and a Praise action
- `e6abc4a` 2026-10-27 — Grief that lasts: one to three weeks by tie, in waves, eased by friends, talks and a gathering at the Memorial Pond
- `7c1ed5f` 2026-10-27 — Coping and comfort: slimes act on bad feelings in their own way, friends cheer each other up, cuddles summed up daily
- `ab7fd69` 2026-10-27 — An inner voice that remembers: talks come from a slime's grief, memories, goal and days, and never repeat within a week
- `ae5f74e` 2026-10-27 — A day at home: meals together, evening hobbies, and a fairer measure of a grind
- `f3a7995` 2026-10-27 — Relationships with texture, personal reactions, and rituals: fading ties, jealousy, apologies, hatch days, feasts
- `66f4444` 2026-10-27 — Why it feels this way: feelings keep their reasons, shown under each one, and a Colony mood panel lists who is struggling and why
- `dcc9da3` 2026-10-27 — Never hang at 'Loading Python runtime': download progress, a stall watchdog with safe-mode fallback, Repair, network-first offline copy
- `6432299` 2026-10-27 — One planning document: ROADMAP.md absorbs TASKS, MINDS, PLAYTEST_F50 and BALANCE, with the full commit history (tools/changelog.py)
- `43c6026` 2026-10-27 — Commit history in ROADMAP.md includes the merge commit itself

### Pull request #24 (merged 2026-10-27)

- `81cf321` 2026-10-27 — Troublemakers judged fairly, removed at no cost, and the Keeper's shadow
- `fdf8f2a` 2026-10-27 — Commit history in ROADMAP.md includes the troublemaker change
- `d165eba` 2026-10-27 — Council: merge suggestions right after quarrels, then collapsible Keep / Flexible / Merge groups
- `4c74934` 2026-10-27 — Commit history in ROADMAP.md includes the Council layout change

### Pull request #25 (merged 2026-10-28)

- `def4b75` 2026-10-27 — Descent strike forces, no waiting after a fight by hand, trainer rules, call back everywhere
- `02b7354` 2026-10-27 — Commit history in ROADMAP.md includes the strike force change
- `65a3df2` 2026-10-27 — Pit sessions look after their party, no taking command in the Pit, sending several groups, call busy slimes away
- `b443251` 2026-10-27 — Commit history in ROADMAP.md includes the session needs and sender change

### Pull request #26 (merged 2026-10-31)

- `278ac7b` 2026-10-31 — Restore the handlers dropped by the sender edit (Grant a request, Talk, Praise ...), add Trades
- `a7dff8b` 2026-10-31 — Commit history in ROADMAP.md includes the handler fix

### Not merged yet: branch `claude/elegant-meitner-beippt`

- `ec7bdf3` 2026-10-31 — Dungeon time: x3 inside every dungeon but not hunting or foraging, set place by place
- `1d18e57` 2026-10-31 — Commit history in ROADMAP.md includes the dungeon time change
- `99d1f69` 2026-10-31 — Scouting back on lobby time; rescue speed needs the Tailwind passive (wind mastered), not just a mage
- `98b2e7a` 2026-10-31 — Commit history in ROADMAP.md includes the Tailwind change
- `31466d8` 2026-10-31 — Tell gear and relics apart: sell back vs break down, distinct names, a Guide section
- `e1435ab` 2026-10-31 — Commit history in ROADMAP.md includes the gear and relic wording change
- `3713aac` 2026-10-31 — Eight more elements to fuse: Mist, Geyser, Ash, Clay, Glass, Quicksand, Glacier, Thunderstone

<!-- changelog:end -->
