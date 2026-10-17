# Task checklist

The remaining roadmap as working tasks. `[x]` done, `[~]` in progress, `[ ]` to do. Each has a short "done when".
The roadmap (`ROADMAP.md`) stays the milestone history; this file is what is left. Update both when something ships.

## Milestone
- [~] **1. Floor-50 playtest and balance** — harness `tools/playtest.py` and report `PLAYTEST_F50.md` are done; an AI bug that wasted opening turns on buffs is fixed.
  *Done when:* the real descent to floor 50 has been played through (with gear, elements, scouting) and the follow-ups below are closed.
- [ ] **24. Floor threat smoothing (from the playtest)** — make floors with many area attackers (32, 35, 40, 45) fit the difficulty curve; area-aware threat measure or a cap on area users per floor.
  *Done when:* the reference party's required level never jumps more than ~15 over its neighbours; regression check added to the harness.
- [ ] **25. Time-to-floor-50 economy (from the playtest)** — rework Pit XP / Descent XP so the climb takes weeks, not months.
  *Done when:* a common party reaches floor 50 in a target number of real hours at the x3 dungeon rate, and legendary parties are not 4x slower than that.

## Gameplay
- [ ] **2. More specialization paths** — three-way hybrids, evolving specializations, slimes asking for jobs.  *Done when:* at least two new hybrid paths exist with skills and capstones, tested.
- [ ] **3. Spell mutation** — fused spells evolve with mastery (effects from `fx.py`).  *Done when:* a researched spell changes form at set mastery levels, with UI.
- [ ] **4. Enemy resistances and elemental floors** — several resistances per enemy; floors that favour specific elements.  *Done when:* bestiary, intel text and Guide show them; elemental floors playable.
- [ ] **5. Floor modifiers and shops between floors** — poison fog, darkness, a shop or rest stop between floors.  *Done when:* modifiers use fx statuses and scouting reveals them.
- [ ] **6. Retreat or checkpoint mid-descent** — a costed way out that keeps the no-exit identity.  *Done when:* rule, UI and tests agree.
- [ ] **7. Several delves at once + rescue parties** — one party per dungeon; rescues for overdue scouts.  *Done when:* two parties can delve at once in live mode with correct timers.
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

## Interface
- [ ] **18. CLI turn prompts for manual battles + optional flee** — terminal manual fights.  *Done when:* `main.py` can fight a skirmish by hand; flee decided and documented.

## Quality
- [ ] **21. Balance pass with a simulation harness** — extend `tools/playtest.py` to Pit depths, rarities, skills and capstones.  *Done when:* a report covers each system and numbers are tuned in `config.py`.
- [ ] **22. Localisation** — string catalogs and a language switch.  *Done when:* UI, logs and Guide can be switched to a second language.

## After floor 50 (art and sound)
- [ ] **17. Animated battle arena** — replace `ARENA.render`.  *Done when:* units animate and statuses show without touching rules.
- [ ] **19. Art pass: sprites, animated slimes, sound** — replace the CSS blobs, add sound effects.  *Done when:* every slime class and rarity has art and the main actions have sound.
