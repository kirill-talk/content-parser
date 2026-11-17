"""
Migration Studio Background Agents and Task Coordinator.
Provides specialized worker agents:
- ContentAgent (Splitting and cleaning)
- TranslationAgent (Language pairing)
- TaxonomyAgent (Category & filter mapping)
"""

import threading
import time

class AgentStatus:
    def __init__(self):
        self.discovery_agent = "Ready"
        self.content_agent = "Ready"
        self.translation_agent = "Ready"
        self.taxonomy_agent = "Ready"
        self.last_active = time.time()

    def set_busy(self, agent_name: str, task: str):
        setattr(self, agent_name, f"Working: {task}")
        self.last_active = time.time()

    def set_ready(self, agent_name: str):
        setattr(self, agent_name, "Ready")
        self.last_active = time.time()

    def to_dict(self):
        agents = [self.discovery_agent, self.content_agent, self.translation_agent, self.taxonomy_agent]
        return {
            "discovery_agent": self.discovery_agent,
            "content_agent": self.content_agent,
            "translation_agent": self.translation_agent,
            "taxonomy_agent": self.taxonomy_agent,
            "status": "idle" if all(v == "Ready" for v in agents) else "busy"
        }

coordinator = AgentStatus()
