# Slime minds

How slimes feel, fight, bond and grieve, measured against how people behave in the same situations. The harness
`tools/minds_sim.py` runs seeded colonies for weeks and checks the targets below; `tests/test_minds.py` runs a small version
on every test run.

```bash
python3 tools/minds_sim.py                 # report (about 5 seconds)
python3 tools/minds_sim.py --seeds 3       # over three seeds
python3 tools/minds_sim.py --check         # exit 1 if a target fails
```

## Decisions (from the Keeper, October 2026)

1. Waking up to being code stays **legendary only** (5-star legendaries).
2. A slime **may leave** the colony, but **only with the Keeper's permission**.
3. The Keeper's care can fix **up to 70%**: it stands in for at most 70% of a slime's connection and purpose
   (`config.KEEPER_CARE_SHARE`). Enough to settle a slime, not to give it peace on its own.
4. Despair may go **darker than withdrawal**: self-neglect (it stops feeding itself; the Keeper must feed it by hand) and
   breakdowns, ending in a request to leave. Nothing beyond that.

## Targets

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

## Before and after (seed 1, 20 slimes, 45 days)

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

## How it works

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
- **Goals** (`mind.py`): a weighted pool - get stronger, master a style, see a friend, make a new one, court someone, teach
  a mentee, explore, make something, take it easy, be noticed - shaped by traits, outlook, needs and ties; a grudge is one
  candidate. Thanks outlast minor grudges when memory is full. Slimes who share the colony's days (idle, resting, at a post)
  grow closer.
- **Leaving** (`mind.py`, `Game.depart`): only with the Keeper's yes; friends miss it, its gear stays, Records lists it.

## Still to do

Task 65 in `docs/TASKS.md` (meaning for every slime, grief, everyday goals, coping, comfort between friends, an inner
voice, daily rhythm, relationship texture, appraisal, rituals, a "why it feels this way" view).
