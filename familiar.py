<drac2>

SVAR_GROUP = "familiar_group"
ELEMENT_CVAR = "familiar_element"
FAMILIAR_DATA_CVAR = "familiarData"
DEFAULT_GROUP_TEMPLATE = "{name}'s Familiars"

true, false, null = True, False, None

args = argparse(&ARGS&)
c = combat()
ch = character()
pf = ctx.prefix
footer_text = f"{ctx.prefix+ctx.alias} | Made by vaguely_happy"

open_b = "<"+"drac2"+">"
close_b = "</"+"drac2"+">"

# ============================================================================
# RAW ARGUMENT TOKENISING
#
# argparse gives easy access to named values, but we also need to forward every
# unrelated argument to i madd. This keeps the alias open-ended for normal Avrae
# monster-add flags without needing to know all of them here.
# ============================================================================

raw_args = """&*&"""

def read_cli(src):
    tokens = []
    buf = ""
    quote = null
    i = 0

    while i < len(src):
        chn = src[i]

        if quote:
            if chn == "\\" and i + 1 < len(src):
                i += 1
                buf += src[i]
            elif chn == quote:
                quote = null
            else:
                buf += chn

        else:
            if chn in ['"', "'"]:
                quote = chn
            elif chn in [" ", "\t", "\n", "\r"]:
                if buf:
                    tokens.append(buf)
                    buf = ""
            else:
                buf += chn

        i += 1

    if buf:
        tokens.append(buf)

    return tokens

def strip_flag(token):
    if token.startswith("--"):
        return token[2:]
    if token.startswith("-"):
        return token[1:]
    return ""

def split_equals(token):
    if "=" not in token:
        return [token, null]

    idx = token.find("=")
    return [token[:idx], token[idx + 1:]]

def cli_quote(value, always=false):
    text = str(value)
    needs_quote = always or not text

    for chn in ['"', " ", "\t", "\n", "\r"]:
        if chn in text:
            needs_quote = true

    if needs_quote:
        return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'

    return text

def is_falsey_text(value):
    return str(value).lower() in ["0", "false", "no", "off", "none", "null"]

def is_truthy_text(value):
    return str(value).lower() in ["1", "true", "yes", "on"]

def group_from_template(template):
    return str(template).replace("{name}", name).replace("{character}", name)

def embed_quote(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'

def embed_msg(title, desc, thumb=""):
    out = f"""embed
-title {embed_quote(title)}
-desc {embed_quote(desc)}
-footer {embed_quote(footer_text)}
"""

    if thumb:
        out += f"-thumb {embed_quote(thumb)}\n"

    return out

tokens = read_cli(raw_args)
passthrough = []

raw_familiar_data = get("familiarData", "")

if not raw_familiar_data:
    raw_familiar_data = ch.get_cvar("familiarData", "{}")

familiar_data = load_json(raw_familiar_data or "{}")

if not familiar_data:
    familiar_data = {}

familiar_type = null
familiar_name = null
familiar_image = null
group_flag = false
group_value = null
element = null

i = 0
while i < len(tokens):
    token = tokens[i]
    pair = split_equals(token)
    flag_token = pair[0]
    inline_value = pair[1]
    flag = strip_flag(flag_token).lower()

    if flag in ["type", "name", "image", "img", "thumb", "group", "element", "damage", "dc"]:
        value = inline_value

        if value == null and i + 1 < len(tokens) and not tokens[i + 1].startswith("-"):
            value = tokens[i + 1]
            i += 1

        if flag == "type":
            familiar_type = value
        elif flag == "name":
            familiar_name = value
        elif flag in ["image", "img", "thumb"]:
            familiar_image = value
        elif flag == "group":
            group_flag = true
            group_value = value
        elif flag in ["element", "damage"]:
            element = value

    else:
        passthrough.append(token)

    i += 1

if not familiar_type:
    familiar_type = args.last("type", familiar_data.get("type"))

if not familiar_name:
    familiar_name = args.last("name", familiar_data.get("name"))

if not familiar_image:
    familiar_image = args.last("image", args.last("img", args.last("thumb", familiar_data.get("image", ""))))

if not element:
    element = args.last("element", args.last("damage"))

# ============================================================================
# GROUP PREFERENCE
#
# -group with a value uses that group name.
# -group without a value uses the svar/default group name.
# A server variable named familiar_group can also opt characters in:
#   true/on/yes/1              -> use the default group name
#   any other non-false value  -> use that text as the group name
#   false/off/no/0            -> disabled
#
# Group name templates can use {name} or {character}.
# ============================================================================

group_svar = get_svar(SVAR_GROUP, "")
group_name = ""

if group_flag:
    if group_value and is_falsey_text(group_value):
        group_name = ""
    elif group_value:
        group_name = group_from_template(group_value)
    elif group_svar and not is_falsey_text(group_svar) and not is_truthy_text(group_svar):
        group_name = group_from_template(group_svar)
    else:
        group_name = group_from_template(DEFAULT_GROUP_TEMPLATE)

elif group_svar and not is_falsey_text(group_svar):
    if is_truthy_text(group_svar):
        group_name = group_from_template(DEFAULT_GROUP_TEMPLATE)
    else:
        group_name = group_from_template(group_svar)

# ============================================================================
# ELEMENTAL FAMILIAR CHOICE
# ============================================================================

valid_elements = ["acid", "cold", "fire", "lightning", "thunder"]
saved_element = ch.get_cvar(ELEMENT_CVAR, "")

if element:
    element = str(element).lower()

    if element not in valid_elements:
        return embed_msg(
            "Woopsie!",
            "Elemental Familiar damage must be Acid, Cold, Fire, Lightning, or Thunder.",
            familiar_image
        )

    ch.set_cvar(ELEMENT_CVAR, element)

elif saved_element:
    element = saved_element.lower()

if element and element not in valid_elements:
    element = ""

pb = int(proficiencyBonus)
spellbook_dc = ch.spellbook.dc if ch.spellbook.dc else 8 + pb
spell_dc = int(args.last("dc", spellbook_dc))
char_level = int(ch.levels.total_level)


# ============================================================================
# FAMILIAR DETAILS
# ============================================================================

feats_text = ch.get_cvar("feats", "").lower()
has_familiar_friend = "familiar friend" in feats_text
has_elemental_familiar = "elemental familiar" in feats_text
has_soothing_familiar = "soothing familiar" in feats_text
has_warlike_familiar = "warlike familiar" in feats_text

detail_lines = [
    "Type: `" + str(familiar_type) + "`",
    "Name: `" + str(familiar_name) + "`"
]

if familiar_image:
    detail_lines.append("Image: set")

feature_lines = []

if has_familiar_friend:
    feature_lines.append("Familiar Friend: +" + str(2 * char_level) + " maximum and current HP")

if has_elemental_familiar:
    if element:
        feature_lines.append("Elemental Familiar: " + element.title() + " resistance and Energy Pulse, DC " + str(spell_dc))
    else:
        feature_lines.append("Elemental Familiar: choose Acid, Cold, Fire, Lightning, or Thunder with `-element`")

if has_soothing_familiar:
    feature_lines.append("Soothing Familiar: Healing Beacon action")

if has_warlike_familiar:
    feature_lines.append("Warlike Familiar: Intercept Attack, AC bonus +" + str(pb))

if feature_lines:
    detail_lines.append("")
    detail_lines.append("Features:")
    detail_lines += feature_lines

details_desc = "\n".join(detail_lines)

stored_familiar_data = {
    "type": familiar_type,
    "name": familiar_name
}

if familiar_image:
    stored_familiar_data["image"] = familiar_image

ch.set_cvar("familiarData", dump_json(stored_familiar_data))

if not c:
#    if not familiar_type or not familiar_name:
#        return embed_msg(
#            "Familiar",
#            (
#                "You have no familiar set.\n\n"
#                "Use `!familiar -type <type> -name <name> [args]`.\n\n"
#                "For example:\n"
#                "`!familiar -type owl -name Archimedes`"
#            ),
#            familiar_image
#        )
#
    return embed_msg(
        str(familiar_name),
        details_desc,
        familiar_image
    )
    

if not familiar_type or not familiar_name:
    return embed_msg(
        "Woopsie!",
        (
            "Use `!familiar -type <type> -name <name> [args]`.\n\n"
            "For example:\n"
            "`!familiar -type owl -name Archimedes`\n"
            "`!familiar -type owl -name Archimedes -group`"
        ),
        familiar_image
    )





# ============================================================================
# BUILD COMMANDS
# ============================================================================

summon_parts = [
    f"{pf}i madd",
    cli_quote(familiar_type, true),
    "-h",
    "-name",
    cli_quote(familiar_name, true)
]

if group_name:
    summon_parts += ["-group", cli_quote(group_name, true)]

summon_parts += [cli_quote(t) for t in passthrough]
summon_command = " ".join(summon_parts)

post_code = f"""{open_b}
c = combat()
ch = character()

true, false, null = True, False, None

familiar_name = {dump_json(familiar_name)}
familiar_type = {dump_json(familiar_type)}
group_name = {dump_json(group_name)}
familiar_image = {dump_json(familiar_image)}
footer_text = {dump_json(footer_text)}
element = {dump_json(element)}
spell_dc = {spell_dc}
char_level = {char_level}
pb = {pb}

def embed_args(title, desc, thumb=""):
    def embed_quote(value):
        return '"' + str(value).replace("\\\\", "\\\\\\\\").replace('"', '\\\\"') + '"'

    out = '-title ' + embed_quote(title) + ' -desc ' + embed_quote(desc)
    out += ' -footer ' + embed_quote(footer_text)

    if thumb:
        out += ' -thumb ' + embed_quote(thumb)

    return out

if not c:
    return embed_args(
        "Familiar Error",
        "You are no longer in initiative.",
        familiar_image
    )

familiar = c.get_combatant(familiar_name, strict=True)

if not familiar:
    return embed_args(
        "Familiar Error",
        "I could not find `" + familiar_name + "` after the add command.",
        familiar_image
    )

if not familiar_image:
    try:
        familiar_image = familiar.image
    except:
        familiar_image = ""

# ---------------------------------------------------------------------------
# GROUP
# ---------------------------------------------------------------------------

if group_name:
    if c.me:
        c.me.set_group(group_name)
    familiar.set_group(group_name)

# ---------------------------------------------------------------------------
# FEATS
#
# Feat information is expected in the character cvar "feats". If it is absent,
# this alias assumes the character has no familiar-related feats.
# ---------------------------------------------------------------------------

feats_text = ch.get_cvar("feats", "").lower()
has_familiar_friend = "familiar friend" in feats_text
has_elemental_familiar = "elemental familiar" in feats_text
has_soothing_familiar = "soothing familiar" in feats_text
has_warlike_familiar = "warlike familiar" in feats_text

applied = []

if group_name:
    applied.append("Group: `" + group_name + "`")

# ---------------------------------------------------------------------------
# FAMILIAR FRIEND
# ---------------------------------------------------------------------------

if has_familiar_friend:
    bonus_hp = 2 * char_level

    if familiar.max_hp != null:
        familiar.set_maxhp(familiar.max_hp + bonus_hp)

    if familiar.hp != null:
        familiar.set_hp(familiar.hp + bonus_hp)

    applied.append("Familiar Friend: +" + str(bonus_hp) + " maximum and current HP")

# ---------------------------------------------------------------------------
# ELEMENTAL FAMILIAR
# ---------------------------------------------------------------------------

if has_elemental_familiar:
    if element:
        damage_type = element.title()

        energy_pulse = {{
            "_v": 2,
            "name": "Energy Pulse",
            "automation": [
                {{
                    "type": "target",
                    "target": "each",
                    "effects": [
                        {{
                            "type": "save",
                            "stat": "dex",
                            "dc": spell_dc,
                            "fail": [
                                {{
                                    "type": "damage",
                                    "damage": "2d4 [" + element + "]"
                                }}
                            ],
                            "success": []
                        }}
                    ]
                }},
                {{
                    "type": "text",
                    "text": (
                        "As a Bonus Action, you command your familiar to take "
                        "a Reaction and unleash elemental energy in a 5-foot "
                        "Emanation. Creatures that fail the save take 2d4 "
                        + damage_type + " damage, and Medium or smaller "
                        "creatures that fail also fall Prone."
                    )
                }}
            ]
        }}

        familiar.add_effect(
            "Elemental Familiar",
            desc=(
                "Resistance: " + damage_type + "\\n"
                "Energy Pulse: 5-foot Emanation, Dexterity save DC "
                + str(spell_dc)
                + ", 2d4 "
                + damage_type
                + " damage on a failure. Medium or smaller creatures that "
                "fail have the Prone condition."
            ),
            passive_effects={{"resistances": [element]}},
            attacks=[{{"attack": energy_pulse}}]
        )

        applied.append("Elemental Familiar: " + damage_type + " resistance and Energy Pulse")

    else:
        applied.append("Elemental Familiar: choose Acid, Cold, Fire, Lightning, or Thunder with `-element`")

# ---------------------------------------------------------------------------
# SOOTHING FAMILIAR
# ---------------------------------------------------------------------------

if has_soothing_familiar:
    healing_beacon = {{
        "_v": 2,
        "name": "Healing Beacon",
        "automation": [
            {{
                "type": "target",
                "target": "each",
                "effects": [
                    {{
                        "type": "ieffect2",
                        "name": "Soothing Familiar",
                        "desc": (
                            "Positive energy fills a 5-foot Emanation "
                            "originating from the familiar while it is within "
                            "120 feet of its summoner. Whenever an ally in "
                            "that Emanation rolls a die to determine Hit "
                            "Points restored, that ally can treat a roll of "
                            "1 or 2 as a 3.\\n\\nHelp: use -mi 3 when "
                            "applying healing dice within the aura."
                        ),
                        "buttons": [
                            {{
                                "label": "Leave Soothing Familiar",
                                "verb": "leaves Soothing Familiar",
                                "style": 2,
                                "automation": [
                                    {{
                                        "type": "remove_ieffect"
                                    }}
                                ]
                            }}
                        ]
                    }}
                ]
            }},
            {{
                "type": "text",
                "title": "Healing Beacon",
                "text": (
                    "Marked targets are in the familiar's 5-foot healing "
                    "Emanation. Use -mi 3 when applying healing dice within "
                    "the aura."
                )
            }}
        ]
    }}

    familiar.add_effect(
        "Soothing Familiar",
        desc=(
            "Healing Beacon: Positive energy fills a 5-foot Emanation "
            "originating from this familiar while it is within 120 feet of "
            "its summoner. Use the Healing Beacon action with `-t <target>` "
            "to mark creatures currently in the aura."
        ),
        attacks=[{{"attack": healing_beacon}}]
    )

    applied.append("Soothing Familiar: Healing Beacon action")

# ---------------------------------------------------------------------------
# WARLIKE FAMILIAR
# ---------------------------------------------------------------------------

if has_warlike_familiar:
    intercept_attack = {{
        "_v": 2,
        "name": "Intercept Attack",
        "verb": "uses Intercept Attack",
        "activation_type": 4,
        "automation": [
            {{
                "type": "counter",
                "counter": "Intercept Attack",
                "amount": "0",
                "errorBehaviour": "ignore"
            }},
            {{
                "type": "target",
                "target": "each",
                "effects": [
                    {{
                        "type": "damage",
                        "damage": "-{{lastCounterRequestedAmount}} [heal]",
                        "fixedValue": true
                    }}
                ]
            }},
            {{
                "type": "text",
                "title": "Intercept Attack",
                "text": (
                    "When a creature is hit by an attack roll, this familiar "
                    "can take a Reaction to add +" + str(pb) + " to that "
                    "creature's AC against the attack, potentially causing it "
                    "to miss. The target regains the amount supplied with "
                    "`-amt`."
                )
            }}
        ]
    }}

    familiar.add_effect(
        "Warlike Familiar",
        desc=(
            "Intercept Attack: When a creature is hit by an attack roll, this "
            "familiar can take a Reaction to add +" + str(pb) + " to that "
            "creature's AC against the attack. Use the action with "
            "`-t <target> -amt <damage prevented>`."
        ),
        attacks=[{{"attack": intercept_attack}}]
    )

    applied.append("Warlike Familiar: Intercept Attack, AC bonus +" + str(pb))

combat_details = [
    "Type: `" + str(familiar_type) + "`",
    "Name: `" + str(familiar_name) + "`"
]

if familiar_image:
    combat_details.append("Image: set")

desc = "\\n".join(combat_details)
desc += "\\n\\n`" + familiar_name + "` was added to initiative."

if applied:
    desc += "\\n\\nApplied:\\n" + "\\n".join(applied)

return embed_args("Familiar Added", desc, familiar_image)
{close_b}"""

return f"""multiline
{summon_command}
{pf}tembed {post_code}
"""

</drac2>
