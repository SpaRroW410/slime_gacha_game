"""The About page: version, a summary of the game and its mechanics, and the remaining roadmap.

The roadmap list mirrors the open tasks in docs/ROADMAP.md § 2 (a test keeps the two in step)."""
from typing import Dict, List

from . import config

SUMMARY = ("Slime Gacha is an offline slime-raising game. You are the Keeper of the Last Gacha Well: pull slimes, look after "
           "their needs and feelings, grow them through levels, stars and rarities, build a colony, and send parties into "
           "dangerous dungeons - the permadeath Hollow Descent among them. It plays in a browser (on a computer "
           "or a phone) or in a terminal, with no network and no accounts; everything is saved on your own device.")

SECTIONS: List[Dict[str, object]] = [
    dict(title="The core loop", icon="🔁", items=[
        "Pull slimes at the Gacha Well (a free pull every day, or white / purple gel; ten at once is 10% cheaper).",
        "Look after them: feed, pet, let them sleep, settle quarrels. Needs, feelings and morale change how strong they are.",
        "Grow them: XP and levels, evolution stages, stars (ascension stones) and rarity (white gel, at level 100 and 5 stars).",
        "Form parties, train in the Academy, build the town, and push deeper into the dungeons for loot and permanent progress.",
    ]),
    dict(title="Slimes", icon="🫧", items=[
        "Ten classes - barbarian, mage, medic, rogue, ranger, necromancer, bard, paladin, alchemist, druid - each with its own skills, discipline and stats. "
        "Rarity (common to legendary) shows as the slime's shape and ring; its body colour is yours to choose.",
        "Needs: energy, food, safety, belonging, esteem. Neglect is lethal; contentment gives more power.",
        "Skills: class skills by level, 40 rarity skills, 10 evolution skills, 20 pure and 20 hybrid capstones, star attributes, "
        "elemental spells (fusable, and they change form as mastery grows).",
        "Total power (001-999 tag in the Colony) sums stats, skills, attributes, mastery, styles and proficiency, times mood and morale.",
        "Slimes have personalities, friendships, couples, mentors and rivals; they quarrel when they share a place, and brawls leave "
        "them grounded until mediated; most spats mend on their own. Legendary 5-star slimes come to realise they are code, and "
        "take it as their life so far allows: settled, at peace, a cog in the machine, or in despair.",
    ]),
    dict(title="Parties and battles", icon="⚔", items=[
        "Parties of up to five (you choose the size). Synergy comes from how well the members get on.",
        "Battles are turn-based with real status effects (bleed, stun, shields, marks, buffs, revive and more). Fight automatically "
        "or take command and choose every slime's action; switch between the two at any time.",
        "Elements matter: water > fire > wind > earth > water, plus family weaknesses and resistances, terrain and elemental floors.",
        "Sparring (duels, and two parties fighting as teams) builds fighting styles, class proficiency and bonds, without risk.",
    ]),
    dict(title="Dungeons", icon="🕳", items=[
        "Hollow Descent: 50 floors in order, permadeath, leave for free only after a boss floor. Scout floors for intel (and be "
        "rescued if you overrun), camp (limited by floor and scouting), meet floor modifiers and wayside stops, call reinforcements, "
        "or pay for an emergency retreat. Every slime must have cleared the floor above to enter a floor.",
        "Gloop Pit: the XP farm (a new theme every day; knock-outs cost morale, never XP).",
        "Wayfarer's Rift: relics. Starfall Quarry: ascension stones. Nobody dies in the farming dungeons, and they drop a little extra now and then.",
        "Hunts and foraging: free resource trips of one to eight hours; they also sharpen proficiency, and a party that hunts together bonds.",
    ]),
    dict(title="Academy and Town", icon="🏠", items=[
        "Academy: drills and sparring (with three trainers), the Library (study elements, learn spells, fuse them) and specializations.",
        "Buildings: Rest Area (energy), Hospital (health), Training Grounds, Library, Barracks, Armory, Alchemy Lab, Kitchen, "
        "Destruction Chamber. Their levels set how many slimes can be appointed and how well.",
        "Appointments: trainers, librarian, blacksmith (forges), brewer, chef (recipes, pantry) and doctor work three-hour shifts "
        "for a small bonus; idle ones forage and can be called back.",
        "Merge and destroy slimes (only at home), scrap and merge gear and relics, fuse 100 white gel into 1 purple gel.",
    ]),
    dict(title="You, the Keeper", icon="🧑‍🌾", items=[
        "Keeper XP from tending, pulling, winning, scouting and more gives skill points for passive bonuses and active powers.",
        "A Vice Keeper can stand in for you inside groups, lead hunts and settle quarrels; party leaders give small bonuses.",
        "Commander's gifts (purple gel) are the one way to reach a party deep in the Descent.",
    ]),
    dict(title="Time and saving", icon="⏱", items=[
        "Turn mode: time passes when you say so (+1h, +4h, +1 day). Live mode: the real clock moves the colony (time inside a dungeon runs faster, place by place), "
        "with a capped catch-up for when you were away.",
        "The away bar counts down every hunt, study, drill, shift and delve. Saves live in your browser or a save file you can export; "
        "the in-game Guide has the numbers behind every mechanic.",
    ]),
]

# id, group, title, what it will do - keep in step with the open tasks in docs/ROADMAP.md § 2
ROADMAP: List[Dict[str, object]] = [
    dict(id=1, group="Milestone", title="Floor-50 playtest and balance", status="in progress",
         text="A real play-through of the whole Descent to floor 50, then fix what it finds. The harness and report exist."),
    dict(id=82, group="Later", title="More passive skills", status="planned",
         text="Tailwind (wind mastered) is the first passive; more for other slimes, each earned by mastering something."),
    dict(id=48, group="Mobile", title="Mobile performance", status="planned",
         text="Faster turns, smaller replies, in-place updates, startup on low-end phones."),
    dict(id=49, group="Mobile", title="Capacitor shell", status="planned",
         text="Native saves with backups, app lifecycle, store builds."),
    dict(id=50, group="Mobile", title="Store prep and compliance", status="planned",
         text="Odds screen, age ratings, privacy labels, listings."),
    dict(id=51, group="Mobile", title="Monetization decision (optional)", status="planned",
         text="Whether real money buys gacha currency decides how much moves to a server."),
    dict(id=52, group="Mobile", title="Beta and launch", status="planned",
         text="Device testing, long sessions, crash reporting, release."),
]


# The one-line note shown once after an update (the page remembers the id it has shown). Change id and text with each release.
WHATS_NEW = dict(id="2026-10-28-dungeon-time",
                 text="Dungeon time: inside a dungeon, time runs 3x faster than in the lobby (each place has its own number, so it can be tuned one by one; scouting, hunting, foraging and jobs stay on lobby time). A 3-hour floor now costs 1 hour on the clock, but the party inside eats, tires, mends and grows closer 3x as fast, and the live clock no longer speeds up when someone leaves. Rescue parties get faster with a slime that has the new Tailwind passive skill: master the wind element to the top level to earn it (an ordinary mage does not). Passive skills show on the Fight tab, with what it takes to unlock the locked ones. Mages are a little rarer in pulls than the other magic classes. Screens show both clocks: \"3h inside = 1h here\".")


def build() -> Dict[str, object]:
    return dict(version=config.VERSION, name="Slime Gacha - Pick Me Up, Little Goo!", summary=SUMMARY,
                sections=SECTIONS, roadmap=ROADMAP, save_version=config.SAVE_VERSION, whats_new=WHATS_NEW)
