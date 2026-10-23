<drac2>

TYPE = "Battle Familiar"
SPELL_NAME = "Battle Familiar"
SPELL_DESC = """You conjure a familiar imbued with magical might. The familiar appears in an unoccupied space within range, resembles an animal of your choice but is a Celestial, Fey, or Fiend (your choice), and uses the Battle Familiar stat block. When you cast this spell, choose the Brute, Flyer, or Stalker form. The choice determines certain details in the stat block.

The familiar is an ally to you and your allies. It rolls its own Initiative and acts on its own turn.

If you have a familiar from the Find Familiar spell when you cast this spell, you empower your existing familiar rather than conjuring a new one. For the duration, your familiar can attack in addition to taking other actions as normal, and your familiar's game statistics are replaced by the Battle Familiar stat block, but it retains its creature type, alignment, Hit Points, Hit Point Dice, and any features granted by the Find Familiar spell. Your familiar gains a number of Temporary Hit Points equal to the Hit Points of the battle familiar."""

MIN_LEVEL = 2
DURATION = 600

NATIVE_EFFECT = "Battle Familiar: Original Native Data"
META_KEY = "battle_familiar_data"

using(init_add="f48672c2-8f25-4170-ba39-d5f6ffd38bd3")

args = argparse(&ARGS&)

c = combat()
ch = character()

true, false, null = True, False, None

if not (c and c.me):
    return """embed -title "Woopsie!" -desc "You're not in initiative!" """

open_b = "<"+"drac2"+">"
close_b = "</"+"drac2"+">"

pf = ctx.prefix

# ============================================================================
# LOAD METADATA
# ============================================================================

raw_meta = c.get_metadata(META_KEY, "{}")
meta = load_json(raw_meta)

# ============================================================================
# LOAD CHARACTER PREFERENCES
#
# Stored as JSON in the character cvar "battlefamiliar".
#
# {
#     "name": "Artemis's Battle Familiar",
#     "ctype": "celestial",
#     "choice": "brute"
# }
# ============================================================================

prefs = load_json(ch.get_cvar("battlefamiliar", "{}"))
familiar_data = load_json(ch.get_cvar("familiarData", "{}"))

if not familiar_data:
    familiar_data = {}

# ============================================================================
# END / REVERT BATTLE FAMILIAR
# ============================================================================

if "end" in args:

    target_name = args.last("t")

    if not target_name:
        return """embed
-title "Woopsie!"
-desc "`end` requires a target.

For example:
`!battle end -t "Archimedes (Battle)"`"
"""

    battle = c.get_combatant(target_name)

    if not battle:
        return f"""embed
-title "Woopsie!"
-desc "I couldn't find `{target_name}` in initiative."
"""

    battle_name = battle.name
    battle_key = battle_name.lower()

    if battle_key not in meta:
        return f"""embed
-title "Woopsie!"
-desc "`{battle_name}` does not have Battle Familiar restoration data."
"""

    saved = meta[battle_key]

    original_name = saved["name"]
    monster_name = saved["monster_name"]
    original_group = saved["group"]
    original_note = saved["note"]
    original_init = saved["init"]
    original_max_hp = saved["max_hp"]

    if c.get_combatant(original_name, strict=True):
        return f"""embed
-title "Woopsie!"
-desc "`{original_name}` is already in initiative, so I can't restore another combatant with that name."
"""

    # ------------------------------------------------------------------------
    # RESTORE ORIGINAL COMBATANT
    # ------------------------------------------------------------------------

    if monster_name:

        safe_monster = monster_name.replace('"', '\\"')
        safe_original = original_name.replace('"', '\\"')

        restore_command = f'{pf}i madd "{safe_monster}" -name "{safe_original}"'

        if original_group:
            safe_group = original_group.replace('"', '\\"')
            restore_command += f' -group "{safe_group}"'

    else:

        fallback = saved["fallback"]

        original_stat_block = {
            "hp": original_max_hp,
            "ac": fallback["ac"],
            "pb": fallback["pb"],

            "strength": fallback["strength"],
            "dexterity": fallback["dexterity"],
            "constitution": fallback["constitution"],
            "intelligence": fallback["intelligence"],
            "wisdom": fallback["wisdom"],
            "charisma": fallback["charisma"],

            "type": fallback["type"],
            "p": True,
            "note": original_note
        }

        if original_group:
            original_stat_block["group"] = original_group

        restore_command = init_add.build_init_add(
            original_name,
            original_init,
            original_stat_block
        )

    # ------------------------------------------------------------------------
    # POST-RESTORE TRANSFER
    # ------------------------------------------------------------------------

    restore_code = f"""{open_b}
c = combat()

true, false, null = True, False, None

META_KEY = {dump_json(META_KEY)}
NATIVE_EFFECT = {dump_json(NATIVE_EFFECT)}

battle = c.get_combatant({dump_json(battle_name)}, strict=True)
original = c.get_combatant({dump_json(original_name)}, strict=True)

if not battle or not original:
    return '-title "Battle Familiar Error" -desc "Could not locate both combatants during restoration."'

meta = load_json(c.get_metadata(META_KEY, "{{}}"))
saved = meta.get({dump_json(battle_key)})

if not saved:
    return '-title "Battle Familiar Error" -desc "Restoration metadata disappeared before the transfer completed."'

# ---------------------------------------------------------------------------
# STATE
# ---------------------------------------------------------------------------

original.set_init(saved["init"])

if saved["max_hp"] != null:
    original.set_maxhp(saved["max_hp"])

if battle.hp != null:
    original.set_hp(min(battle.hp, saved["max_hp"]))

# Battle Familiar THP disappears when the spell ends.
original.set_temp_hp(0)

if saved["group"]:
    original.set_group(saved["group"])

original.set_note(saved["note"])

# ---------------------------------------------------------------------------
# TRANSFER CURRENT IEFFECTS
# ---------------------------------------------------------------------------

source_effects = [
    e for e in battle.effects
    if e.name not in ["Battle Familiar", NATIVE_EFFECT]
]

new_effects = []

for e in source_effects:

    pe = {{}}

    for k, v in e.effect.items():

        if k in [
            "resistances",
            "immunities",
            "vulnerabilities",
            "ignored_resistances"
        ]:
            pe[k] = [str(x) for x in v]

        elif k in [
            "save_adv",
            "save_dis",
            "check_adv",
            "check_dis"
        ]:
            pe[k] = list(v)

        else:
            pe[k] = v

    tick_id = e.tick_on_combatant_id

    if tick_id == battle.id:
        tick_id = original.id

    ne = original.add_effect(
        e.name,
        duration=e.remaining,
        concentration=e.conc,
        end=e.ticks_on_end,
        desc=e.desc,
        passive_effects=pe,
        attacks=e.attacks,
        buttons=e.buttons,
        tick_on_combatant_id=tick_id
    )

    new_effects.append(ne)

# Restore effect parenting.
for i, e in enumerate(source_effects):

    if not e.parent:
        continue

    for j, possible_parent in enumerate(source_effects):

        if possible_parent == e.parent:
            new_effects[i].set_parent(new_effects[j])
            break

# ---------------------------------------------------------------------------
# CUSTOM-COMBATANT FALLBACK NATIVE DATA
# ---------------------------------------------------------------------------

if not saved["monster_name"]:

    fallback = saved["fallback"]

    passive = {{}}

    if fallback["resistances"]:
        passive["resistances"] = fallback["resistances"]

    if fallback["immunities"]:
        passive["immunities"] = fallback["immunities"]

    if fallback["vulnerabilities"]:
        passive["vulnerabilities"] = fallback["vulnerabilities"]

    if fallback["ignored_resistances"]:
        passive["ignored_resistances"] = fallback["ignored_resistances"]

    if fallback["attacks"] or passive:
        original.add_effect(
            NATIVE_EFFECT,
            passive_effects=passive,
            attacks=[{{"attack": a}} for a in fallback["attacks"]],
            desc="Internal restoration of the original custom familiar's native attacks and damage defences."
        )

# ---------------------------------------------------------------------------
# METADATA CLEANUP
# ---------------------------------------------------------------------------

meta.pop({dump_json(battle_key)}, null)

if meta:
    c.set_metadata(META_KEY, dump_json(meta))
else:
    c.delete_metadata(META_KEY)

return '-title "Battle Familiar Ends" -desc "{original_name} returns to its normal form."'
{close_b}"""

    safe_battle = battle_name.replace('"', '\\"')

    return f"""multiline
{restore_command}
{pf}tembed {restore_code}
{pf}i remove "{safe_battle}"
"""

# ============================================================================
# CAST
# ============================================================================

spell_level = args.last("l", MIN_LEVEL, int)
ignore = args.last("i")

warlike_counters = [
    cc for cc in ch.consumables
    if cc.name.lower().startswith("warlike familiar")
]
warlike_counter = warlike_counters[0] if warlike_counters else null
use_warlike_counter = (
    not ignore
    and warlike_counter
    and warlike_counter.value > 0
)

if spell_level < MIN_LEVEL:
    return f"""embed
-title "Woopsie!"
-desc "{SPELL_NAME} must be cast using a spell slot of level {MIN_LEVEL} or higher."
"""

# ============================================================================
# REMEMBERED FORM CHOICE
# ============================================================================

choice = args.last(
    "choice",
    prefs.get("choice", ""),
    str
).lower()

if choice not in ["brute", "flyer", "stalker"]:
    return """embed
-title "Woopsie!"
-desc "Choose a form with:
`-choice Brute`
`-choice Flyer`
or
`-choice Stalker`.

Your choice will be remembered for this character."
"""

form = choice.title()

spellcasting_ability = str(args.last("mod",familiar_data.get("mod", ""))).lower()

if spellcasting_ability and spellcasting_ability not in ["int", "wis", "cha"]:
    return """embed
-title "Woopsie!"
-desc "Spellcasting ability must be Intelligence, Wisdom, or Charisma: `-mod int|wis|cha`."
"""

if spellcasting_ability:
    spellcasting_bonus = ch.stats.get_mod(spellcasting_ability)
    sab = spellcasting_bonus + int(proficiencyBonus)
    sdc = 8 + spellcasting_bonus + int(proficiencyBonus)
    familiar_data["mod"] = spellcasting_ability
    ch.set_cvar("familiarData", dump_json(familiar_data))
else:
    sab = int(ch.spellbook.sab)
    sdc = int(args.last("dc", ch.spellbook.dc))

# Warlock pact-slot convenience retained from the Summon Beast alias.
warlock = ch.levels.get("Warlock")

min_slot = max(
    MIN_LEVEL,
    ((warlock >= 9) + (warlock >= 7) + (warlock >= 5) + (warlock >= 3) + 1)
)

spell_level = args.last("l", min_slot, int)

if spell_level < MIN_LEVEL:
    return f"""embed
-title "Woopsie!"
-desc "{SPELL_NAME} must be cast at level {MIN_LEVEL} or higher."
"""

# ============================================================================
# REMEMBERED CREATURE TYPE
# ============================================================================

ctype = args.last(
    "ctype",
    prefs.get("ctype", "celestial"),
    str
).lower()

if ctype not in ["celestial", "fey", "fiend"]:
    return """embed
-title "Woopsie!"
-desc "Creature type must be Celestial, Fey, or Fiend."
"""

creature_type = ctype.title()

# ============================================================================
# REMEMBERED FAMILIAR NAME
#
# This is the preferred name for a NEW summon.
#
# If the player has never chosen a name, the default includes the summoning
# character's name so different characters naturally produce distinct names.
# ============================================================================

preferred_name = args.last(
    "name",
    prefs.get("name", f"{name}'s Battle Familiar"),
    str
)

# ============================================================================
# STORE CHARACTER PREFERENCES
#
# We save the resolved choices. This means:
#
#   !battle -choice brute -name "Bitey" -ctype fey
#
# followed later by:
#
#   !battle
#
# will reuse Brute, Bitey, and Fey for this character.
#
# For an upgraded existing familiar, preferred_name is still remembered for
# future fresh summons, but the Battle version remains "<original> (Battle)".
# ============================================================================

prefs["choice"] = choice
prefs["ctype"] = ctype
prefs["name"] = preferred_name

ch.set_cvar("battlefamiliar", dump_json(prefs))

# ============================================================================
# CASTING RESOURCE
# ============================================================================

if not ignore:

    if use_warlike_counter:
        warlike_counter.mod(-1, strict=true)

    else:
        if not ch.spellbook.get_slots(spell_level):
            return f"""embed
-title "Woopsie!"
-desc "You don't have any level {spell_level} spell slots left!"
-f "Spell Slots|{ch.spellbook.slots_str(spell_level)}"
"""

        if not ch.spellbook.can_cast(SPELL_NAME, spell_level):
            return f"""embed
-title "Woopsie!"
-desc "You don't have {SPELL_NAME} prepared!"
"""

        ch.spellbook.use_slot(spell_level)

# ============================================================================
# STAT BLOCK
# ============================================================================

battle_hp = (
    30 if choice == "brute" else 20
) + (5 * (spell_level - 2))

battle_ac = 11 + spell_level + (2 if choice == "brute" else 0)

multiattack = max(1, spell_level // 2)

if choice == "flyer":
    speed = "40 ft., Fly 30 ft. (hover), Swim 30 ft."
else:
    speed = "40 ft., Swim 30 ft."

battle_desc = (
    f"{form} Battle Familiar\n"
    f"Condition Immunities: Charmed, Frightened\n"
    f"Speed: {speed}\n"
    f"Darkvision 60 ft.; Passive Perception 11\n"
    f"Multiattack: {multiattack} Rend attack"
    f"{'s' if multiattack != 1 else ''}.\n"
    f"Rend: +{sab} to hit; 1d8 + {3 + spell_level} Force damage."
)

# ============================================================================
# REND
# ============================================================================

rend_attack = {
    "_v": 2,
    "name": "Rend",
    "automation": [
        {
            "type": "target",
            "target": "each",
            "effects": [
                {
                    "type": "attack",
                    "attackBonus": sab,
                    "hit": [
                        {
                            "type": "damage",
                            "damage": f"1d8 + 3 + {spell_level} [force]"
                        }
                    ],
                    "miss": [],
                    "adv": "0"
                }
            ]
        },
        {
            "type": "text",
            "text": (
                "*Melee Attack Roll:* Bonus equals your spell attack modifier, "
                "reach 5 ft. "
                f"*Hit:* 1d8 + 3 + {spell_level} Force damage."
            )
        }
    ]
}

attacks = [rend_attack]

# ============================================================================
# TARGET?
# ============================================================================

target_name = args.last("t")
existing = null

if target_name:

    existing = c.get_combatant(target_name)

    if not existing:
        return f"""embed
-title "Woopsie!"
-desc "I couldn't find `{target_name}` in initiative."
"""

# UPGRADE EXISTING FAMILIAR
# ============================================================================

if existing:

    original_name = existing.name
    battle_name = f"{original_name} (Battle)"
    battle_key = battle_name.lower()

    if c.get_combatant(battle_name, strict=True):
        return f"""embed
-title "Woopsie!"
-desc "`{battle_name}` already exists in initiative."
"""

    if battle_key in meta:
        return f"""embed
-title "Woopsie!"
-desc "Restoration metadata already exists for `{battle_name}`."
"""

    monster_name = existing.monster_name

    saved = {
        "name": original_name,
        "monster_name": monster_name,

        "init": existing.init,
        "initmod": existing.initmod,

        "hp": existing.hp,
        "max_hp": existing.max_hp,
        "temp_hp": existing.temp_hp or 0,

        "group": existing.group,
        "note": existing.note or "",

        "fallback": null,

        "spell_level": spell_level,
        "form": form,
        "battle_hp": battle_hp
    }

    # ------------------------------------------------------------------------
    # CUSTOM / GENERIC FALLBACK
    # ------------------------------------------------------------------------

    if not monster_name:

        native_attacks = [a.raw for a in existing.attacks]

        native_resist = [str(x) for x in existing.resistances.resist]
        native_immune = [str(x) for x in existing.resistances.immune]
        native_vuln = [str(x) for x in existing.resistances.vuln]
        native_neutral = []

        native_effect = existing.get_effect(NATIVE_EFFECT, strict=True)

        if native_effect:

            for interaction in native_effect.attacks:
                if "attack" in interaction:
                    native_attacks.append(interaction["attack"])

            npe = native_effect.effect

            native_resist += [
                str(x) for x in npe.get("resistances", [])
            ]

            native_immune += [
                str(x) for x in npe.get("immunities", [])
            ]

            native_vuln += [
                str(x) for x in npe.get("vulnerabilities", [])
            ]

            native_neutral += [
                str(x) for x in npe.get("ignored_resistances", [])
            ]

        saved["fallback"] = {
            "ac": existing.ac,
            "pb": proficiencyBonus,

            "strength": existing.stats.strength,
            "dexterity": existing.stats.dexterity,
            "constitution": existing.stats.constitution,
            "intelligence": existing.stats.intelligence,
            "wisdom": existing.stats.wisdom,
            "charisma": existing.stats.charisma,

            "type": existing.creature_type or "creature",

            "attacks": native_attacks,

            "resistances": native_resist,
            "immunities": native_immune,
            "vulnerabilities": native_vuln,
            "ignored_resistances": native_neutral
        }

    meta[battle_key] = saved
    c.set_metadata(META_KEY, dump_json(meta))

    # ------------------------------------------------------------------------
    # BATTLE VERSION
    #
    # Group is retained when transforming an existing familiar because it is
    # part of that combatant's existing initiative state.
    # ------------------------------------------------------------------------

    battle_stat_block = {
        "hp": existing.max_hp,
        "ac": battle_ac,
        "pb": proficiencyBonus,

        "strength": 16,
        "dexterity": 16,
        "constitution": 12,
        "intelligence": 8,
        "wisdom": 13,
        "charisma": 10,

        "type": existing.creature_type or "creature",
        "p": True,

        "note": existing.note or ""
    }

    if existing.group:
        battle_stat_block["group"] = existing.group

    summon_command = init_add.build_init_add(
        battle_name,
        existing.init,
        battle_stat_block
    )

    # ------------------------------------------------------------------------
    # TRANSFER ORIGINAL -> BATTLE
    # ------------------------------------------------------------------------

    transfer_code = f"""{open_b}
c = combat()

true, false, null = True, False, None

NATIVE_EFFECT = {dump_json(NATIVE_EFFECT)}

source = c.get_combatant({dump_json(original_name)}, strict=True)
dest = c.get_combatant({dump_json(battle_name)}, strict=True)

if not source or not dest:
    return '-title "Battle Familiar Error" -desc "Could not locate both combatants during transformation."'

# ---------------------------------------------------------------------------
# RETAIN HP
# ---------------------------------------------------------------------------

if source.max_hp != null:
    dest.set_maxhp(source.max_hp)

if source.hp != null:
    dest.set_hp(source.hp)

dest.set_temp_hp(max(source.temp_hp or 0, {battle_hp}))

# ---------------------------------------------------------------------------
# TRANSFER LIVE IEFFECTS
# ---------------------------------------------------------------------------

source_effects = [
    e for e in source.effects
    if e.name != NATIVE_EFFECT
]

new_effects = []

for e in source_effects:

    pe = {{}}

    for k, v in e.effect.items():

        if k in [
            "resistances",
            "immunities",
            "vulnerabilities",
            "ignored_resistances"
        ]:
            pe[k] = [str(x) for x in v]

        elif k in [
            "save_adv",
            "save_dis",
            "check_adv",
            "check_dis"
        ]:
            pe[k] = list(v)

        else:
            pe[k] = v

    tick_id = e.tick_on_combatant_id

    if tick_id == source.id:
        tick_id = dest.id

    ne = dest.add_effect(
        e.name,
        duration=e.remaining,
        concentration=e.conc,
        end=e.ticks_on_end,
        desc=e.desc,
        passive_effects=pe,
        attacks=e.attacks,
        buttons=e.buttons,
        tick_on_combatant_id=tick_id
    )

    new_effects.append(ne)

# Restore effect parenting.
for i, e in enumerate(source_effects):

    if not e.parent:
        continue

    for j, possible_parent in enumerate(source_effects):

        if possible_parent == e.parent:
            new_effects[i].set_parent(new_effects[j])
            break

# ---------------------------------------------------------------------------
# BATTLE FAMILIAR EFFECT
#
# The initiative list only needs to show the effect name.
# All explanatory information lives in desc and therefore belongs to the
# individual combatant's status information.
# ---------------------------------------------------------------------------

rend = {dump_json(rend_attack)}

dest.add_effect(
    "Battle Familiar",
    duration={DURATION},
    desc={dump_json(battle_desc)},
    attacks=[{{"attack": rend}}]
)

return '-title "{battle_name}" -desc "{original_name} is empowered as a {form} Battle Familiar.\\n\\n**THP:** {battle_hp}\\n**AC:** {battle_ac}\\n**Rend:** +{sab} to hit, 1d8 + {3 + spell_level} Force\\n**Multiattack:** {multiattack}"'
{close_b}"""

    safe_original = original_name.replace('"', '\\"')

    return f"""multiline
{summon_command}
{pf}tembed {transfer_code}
{pf}i remove "{safe_original}"
"""

# ============================================================================
# FRESH SUMMON
# ============================================================================

summon_name = preferred_name

# ---------------------------------------------------------------------------
# GROUP
#
# Unlike Summon Beast, no group is created or inherited by default.
# A group is only added if the player explicitly supplied -group.
# ---------------------------------------------------------------------------

group_name = args.last("group")

stat_block = {
    "hp": battle_hp,
    "ac": battle_ac,
    "pb": proficiencyBonus,

    "strength": 16,
    "dexterity": 16,
    "constitution": 12,
    "intelligence": 8,
    "wisdom": 13,
    "charisma": 10,

    "type": creature_type.lower(),

    "p": True,

    "note": (
        f"Battle Familiar ({form})\n"
        f"Creature Type: {creature_type}"
    )
}

if group_name:
    stat_block["group"] = group_name

# Battle Familiar rolls its own initiative.
# DEX 16 = +3.
familiar_init = vroll("1d20+3").total

summon_command = init_add.build_init_add(
    summon_name,
    familiar_init,
    stat_block
)

# ---------------------------------------------------------------------------
# FRESH-SUMMON BATTLE FAMILIAR EFFECT
#
# build_tembed handles the granted Rend attack.
# Keep the visible effect name concise.
# ---------------------------------------------------------------------------

if use_warlike_counter:
    resource_field = {
        "title": warlike_counter.name,
        "desc": str(warlike_counter)
    }
else:
    resource_field = {
        "title": "Spell Slots",
        "desc": (
            f"{ch.spellbook.slots_str(spell_level)} "
            f"{'(-1)' if not ignore else ''}"
        )
    }

embed_args = {
    "title": f"{name} summons a {form} Battle Familiar!",
    "desc": SPELL_DESC,

    "fields": [
        {
            "title": "Battle Familiar",
            "desc": (
                f"{creature_type} | {form}\n"
                f"AC {battle_ac} | HP {battle_hp}\n"
                f"Rend +{sab} | 1d8 + {3 + spell_level} Force\n"
                f"Multiattack: {multiattack}"
            )
        },
        {
            "title": "Condition Immunities",
            "desc": "Charmed, Frightened"
        },
        resource_field
    ],

    "footer": f"{ctx.prefix+ctx.alias}",
    "color": color,
    "thumb": image
}

embed = init_add.build_tembed(
    **embed_args,
    init_name=summon_name,
    attacks=attacks,
    effect_name="Battle Familiar",
    extra_effects=[]
)

return f"""multiline
{summon_command}
{embed}
"""

</drac2>
