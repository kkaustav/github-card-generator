# backend/deploy_memory.py
"""
Creates a Vertex AI Agent Engine with a Memory Bank configured
for GitHub dev card user preferences.

Run ONCE before deploying:
    python deploy_memory.py

Then set the printed AGENT_ENGINE_ID in your .env / Cloud Run env vars.
"""

import os
from google import genai
from google.genai import types

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT")
LOCATION = "us-central1"
AGENT_DISPLAY_NAME = "github-card-memory-agent"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=LOCATION)

MemoryTopic = types.MemoryBankCustomizationConfigMemoryTopic
CustomMemoryTopic = types.MemoryBankCustomizationConfigMemoryTopicCustomMemoryTopic

custom_topics = [
    MemoryTopic(custom_memory_topic=CustomMemoryTopic(
        label="card_preferences",
        description="""Extract the user's preferences for GitHub dev cards:
        - Preferred card theme (hacker, builder, researcher, designer, open-source-hero)
        - Dark or light card preference
        - Favorite programming languages
        - Whether they want verbose or minimal card layout
        Example: 'User prefers hacker-theme dark cards with Python as top language.'"""
    ))
]

agent_engine = client.agent_engines.create(config={
    "display_name": AGENT_DISPLAY_NAME,
    "context_spec": {
        "memory_bank_config": {
            "generation_config": {
                "model": f"projects/{PROJECT_ID}/locations/{LOCATION}/publishers/google/models/gemini-2.5-flash"
            },
            "customization_configs": [{"memory_topics": custom_topics}]
        }
    }
})

engine_id = agent_engine.name.split("/")[-1]
print(f"✅ Memory bank created!")
print(f"AGENT_ENGINE_ID={engine_id}")
print(f"\nAdd this to your .env and Cloud Run env vars, then update main.py to use VertexAi services.")
