"""The About page: version, a summary of the game and its mechanics, and the remaining roadmap.

The roadmap list mirrors the unchecked items of docs/TASKS.md (a test keeps the two in step)."""
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
        "Six classes - barbarian, mage, medic, rogue, ranger, necromancer - each with its own skills, discipline and stats. "
        "Rarity (common to legendary) shows as the slime's shape and ring; its body colour is yours to choose.",
        "Needs: energy, food, safety, belonging, esteem. Neglect is lethal; contentment gives more power.",
        "Skills: class skills by level, 24 rarity skills, 6 evolution skills, 12 pure and 12 hybrid capstones, star attributes, "
        "elemental spells (fusable, and they change form as mastery grows).",
        "Total power (001-999 tag in the Colony) sums stats, skills, attributes, mastery, styles and proficiency, times mood and morale.",
        "Slimes have personalities, friendships, couples, mentors and rivals; they quarrel when they share a place, and brawls leave "
        "them grounded until mediated. Legendary 5-star slimes may start to suspect they are code.",
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
        "Turn mode: time passes when you say so (+1h, +4h, +1 day). Live mode: the real clock moves the colony (dungeons run faster), "
        "with a capped catch-up for when you were away.",
        "The away bar counts down every hunt, study, drill, shift and delve. Saves live in your browser or a save file you can export; "
        "the in-game Guide has the numbers behind every mechanic.",
    ]),
]

# id, group, title, what it will do - keep in step with the unchecked items of docs/TASKS.md
ROADMAP: List[Dict[str, object]] = [
    dict(id=1, group="Milestone", title="Floor-50 playtest and balance", status="in progress",
         text="A real play-through of the whole Descent to floor 50, then fix what it finds. The harness and report exist."),
    dict(id=8, group="Gameplay", title="Formations and front/back rows", status="planned",
         text="Positions that change who can be targeted and how much damage is taken."),
    dict(id=9, group="Gameplay", title="New classes: Bard, Paladin, Alchemist, Druid", status="planned",
         text="Four more classes with their own skills, evolutions, capstones and star attributes."),
    dict(id=10, group="Gameplay", title="Construction time and the Hatchery", status="planned",
         text="Building upgrades that take game time (shown in the away bar), and a Hatchery building."),
    dict(id=11, group="Gameplay", title="Gear set bonuses", status="planned", text="Bonuses for wearing matching sets."),
    dict(id=12, group="Gameplay", title="Keeper achievements, titles and respec", status="planned",
         text="An achievements list, titles, and a (costly) way to respec Keeper skills."),
    dict(id=13, group="Gameplay", title="Imbue statuses and revival items", status="planned",
         text="Timed elemental imbues (the barbarian's fire axe) and consumable resurrection."),
    dict(id=15, group="Content", title="Campaign chapters", status="planned",
         text="Story beats at floors and boss clears, from the story notes."),
    dict(id=14, group="Platform", title="Named dungeon registry", status="planned",
         text="Dungeons defined as data, so a new one can be added without code."),
    dict(id=16, group="Platform", title="Daily free pull on the real clock", status="planned",
         text="The daily pull resets by wall clock in both time modes, with offline catch-up."),
    dict(id=20, group="Platform", title="Installable offline app (PWA)", status="planned",
         text="A manifest and service worker so it installs on iPhone and Windows and works with no network."),
    dict(id=23, group="Platform", title="Mod loader (plugins)", status="planned",
         text="A documented plugin API with an example adding a class, a skill and an enemy."),
    dict(id=18, group="Interface", title="Terminal manual battles and fleeing", status="planned",
         text="Fight a wave simulation by hand in the terminal edition; decide and document fleeing."),
    dict(id=21, group="Quality", title="Balance pass with a simulation harness", status="planned",
         text="Extend the playtest tool to Pit depths, rarities, skills and capstones, and tune the numbers."),
    dict(id=22, group="Quality", title="Localisation", status="planned", text="String catalogs and a language switch."),
    dict(id=17, group="After floor 50", title="Animated battle arena", status="later",
         text="Units that animate and show statuses, without touching the rules."),
    dict(id=19, group="After floor 50", title="Art and sound", status="later",
         text="Sprites and animated slimes in place of the CSS blobs, plus sound effects."),
]


# The one-line note shown once after an update (the page remembers the id it has shown). Change id and text with each release.
WHATS_NEW = dict(id="2026-10-20",
                 text="Farming sessions (Pit, Rift, Quarry) now last at most one day, camping included, and show how long they take before you start; "
                      "hospital patients are labelled 'hospital' instead of 'resting'.")


def build() -> Dict[str, object]:
    return dict(version=config.VERSION, name="Slime Gacha - Pick Me Up, Little Goo!", summary=SUMMARY,
                sections=SECTIONS, roadmap=ROADMAP, save_version=config.SAVE_VERSION, whats_new=WHATS_NEW)
