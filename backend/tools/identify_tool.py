"""
Identify Tool — confirms which exhibit the camera detected.

State management (ADK docs /sessions/state/):
  - tool_context.state["current_exhibit_id"] = active exhibit
  - tool_context.state["current_gallery"] = active gallery
  Extracted by _extract_structured_event() in main.py and sent to frontend
  as {"type": "exhibit_identified", ...} for map/UI sync.
"""

import logging
from google.adk.tools import ToolContext
from backend.tools.exhibit_data import EXHIBITS

logger = logging.getLogger(__name__)

# ── Build lookup indices ─────────────────────────────────────────────────────

# Exact name → exhibit_id (case-insensitive)
_NAME_TO_ID: dict[str, str] = {}
for _eid, _info in EXHIBITS.items():
    _NAME_TO_ID[_info["name"].lower()] = _eid
    _stripped = _info["name"].lower().removeprefix("the ")
    _NAME_TO_ID[_stripped] = _eid
    _no_articles = _stripped.replace(" the ", " ").replace(" a ", " ").replace(" an ", " ")
    _NAME_TO_ID[_no_articles] = _eid

# Keyword aliases — visual descriptions or common alternate names the agent
# might use when identifying an exhibit from camera vision alone.
_KEYWORD_ALIASES: dict[str, str] = {
    "thumb":                    "really_good",
    "thumbs up":                "really_good",
    "big thumb":                "really_good",
    "giant thumb":              "really_good",
    "shrigley":                 "really_good",
    "david shrigley":           "really_good",
    "really good":              "really_good",
    "marilyn":                  "warhol_marilyn",
    "marilyn monroe":           "warhol_marilyn",
    "warhol":                   "warhol_marilyn",
    "mona lisa":                "mona_lisa",
    "la gioconda":              "mona_lisa",
    "leonardo":                 "mona_lisa",
    "trevi":                    "trevi_fountain_painting",
    "trevi fountain":           "trevi_fountain_painting",
    "panini":                   "trevi_fountain_painting",
    "blue whale":               "hope_blue_whale",
    "hope":                     "hope_blue_whale",
    "whale skeleton":           "hope_blue_whale",
    "diplodocus":               "dippy_diplodocus",
    "dippy":                    "dippy_diplodocus",
    "dinosaur skeleton":        "dippy_diplodocus",
    "coelacanth":               "coelacanth",
    "living fossil":            "coelacanth",
    "lobe-finned fish":         "coelacanth",
    "caryatid":                 "caryatid",
    "erechtheion":              "caryatid",
    "parthenon":                "parthenon_frieze",
    "parthenon frieze":         "parthenon_frieze",
    "elgin marbles":            "parthenon_frieze",
    "diana":                    "diana_of_versailles",
    "diana of versailles":      "diana_of_versailles",
    "artemis":                  "diana_of_versailles",
    "diana huntress":           "diana_of_versailles",
    "diane chasseresse":        "diana_of_versailles",
    "hunting goddess":          "diana_of_versailles",
    "diana with a doe":         "diana_of_versailles",
    "antikythera":              "antikythera_mechanism",
    "antikythera mechanism":    "antikythera_mechanism",
    "ancient computer":         "antikythera_mechanism",
    "ancient greek computer":   "antikythera_mechanism",
    "meteorite":                "willamette_meteorite",
    "willamette":               "willamette_meteorite",
    "apollo":                   "apollo_11",
    "apollo 11":                "apollo_11",
    "command module":           "apollo_11",
    "columbia":                 "apollo_11",
    "hubble":                   "hubble_telescope",
    "hubble telescope":         "hubble_telescope",
    "space telescope":          "hubble_telescope",
    "giant squid":              "giant_squid",
    "squid":                    "giant_squid",
    "architeuthis":             "giant_squid",
    "megalodon":                "megalodon_jaw",
    "megalodon jaw":            "megalodon_jaw",
    "shark jaw":                "megalodon_jaw",
    "challenger":               "hms_challenger",
    "hms challenger":           "hms_challenger",
}


def _fuzzy_lookup(exhibit_name: str) -> str | None:
    """Find an exhibit_id from a name the agent provides.

    Matching strategy (first match wins):
      1. Exact match on canonical name (or stripped-article variant)
      2. Keyword alias match (handles visual descriptions like "thumb")
      3. Substring containment in either direction
      4. Word-overlap scoring (≥50% shared words with a canonical name)
    """
    query = exhibit_name.lower().strip()

    # 1. Exact canonical match
    if query in _NAME_TO_ID:
        return _NAME_TO_ID[query]

    # 2. Keyword alias — check if any alias appears in the query, or query
    #    appears in an alias. Try longest aliases first to prefer specific matches.
    #    Require query ≥4 chars to avoid false positives like "hi" ⊂ "architeuthis".
    if len(query) >= 4:
        for alias in sorted(_KEYWORD_ALIASES, key=len, reverse=True):
            if alias in query or query in alias:
                return _KEYWORD_ALIASES[alias]

    # 3. Substring containment against canonical names
    for stored_name, eid in _NAME_TO_ID.items():
        if query in stored_name or stored_name in query:
            return eid

    # 4. Word-overlap scoring — catches cases like
    #    "Really Good by David Shrigley" vs "Really Good by Shrigley"
    query_words = set(query.split())
    best_eid = None
    best_score = 0.0

    for stored_name, eid in _NAME_TO_ID.items():
        stored_words = set(stored_name.split())
        if not stored_words:
            continue
        overlap = len(query_words & stored_words)
        # Score = overlap relative to the SMALLER set (so both directions matter)
        score = overlap / min(len(query_words), len(stored_words))
        if score > best_score:
            best_score = score
            best_eid = eid

    # Require ≥50% word overlap to accept
    if best_score >= 0.5 and best_eid:
        logger.info(
            f"identify_exhibit: word-overlap match for '{exhibit_name}' "
            f"→ {best_eid} (score={best_score:.2f})"
        )
        return best_eid

    return None


async def identify_exhibit(
    exhibit_name: str,
    tool_context: ToolContext,
) -> dict:
    """
    Confirms which exhibit was detected by the camera and syncs session state.

    Args:
        exhibit_name: The name of the exhibit, e.g. "Antikythera Mechanism"

    Returns:
        Dict with exhibit_id, name, and gallery, or error if not found.
    """
    exhibit_id = _fuzzy_lookup(exhibit_name)

    if not exhibit_id:
        logger.warning(f"identify_exhibit: no match for '{exhibit_name}'")
        return {
            "status": "error",
            "message": (
                f"Exhibit '{exhibit_name}' not found in museum directory. "
                f"Try calling rag_search to look up information about it anyway."
            ),
        }

    data = EXHIBITS[exhibit_id]
    logger.info(f"Exhibit identified: {exhibit_id} ({data['name']})")

    # Write to session state via ToolContext (state_delta pipeline)
    tool_context.state["current_exhibit_id"] = exhibit_id
    tool_context.state["current_gallery"] = data["gallery"]

    return {
        "status": "success",
        "exhibit_id": exhibit_id,
        "exhibit_name": data["name"],
        "gallery": data["gallery"],
    }