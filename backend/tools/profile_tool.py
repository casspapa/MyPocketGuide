"""
Profile Tool — saves the visitor's profile to session state.

State management (ADK docs /sessions/state/):
  - tool_context.state["visitor_profile"] = session-scoped (this conversation)
  - tool_context.state["user:name"] = user-scoped (persists across sessions)

The tour guide reads the profile via {visitor_profile?} template syntax.
"""

import logging
from google.adk.tools import ToolContext

logger = logging.getLogger(__name__)


async def save_visitor_profile(
    profile_summary: str,
    tool_context: ToolContext,
) -> dict:
    """Saves the visitor's profile after the concierge has gathered their preferences.

    Args:
        profile_summary: A short summary including the visitor's name, interests,
                        and preferred depth of experience.
    """
    # Session-scoped: read by tour guide via {visitor_profile?} template
    tool_context.state["visitor_profile"] = profile_summary

    # User-scoped: persists across sessions for returning visitors
    words = profile_summary.strip().split()
    if words:
        candidate = words[0].rstrip(",.:;")
        if candidate and candidate[0].isupper():
            tool_context.state["user:name"] = candidate

    logger.info(f"Visitor profile saved: {profile_summary[:80]}...")

    return {
        "status": "success",
        "message": "Visitor profile saved. You can now transfer to the tour guide.",
    }
