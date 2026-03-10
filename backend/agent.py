"""
Root agent entry point for ADK.
Wires up the agent hierarchy: concierge → tour_guide.
"""

from backend.agents.concierge_agent import concierge_agent
from backend.agents.tour_guide_agent import tour_guide_agent

concierge_agent.sub_agents = [tour_guide_agent]

root_agent = concierge_agent
