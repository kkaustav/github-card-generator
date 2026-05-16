# backend/agent.py
from google.adk.agents import Agent
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioConnectionParams, StdioServerParameters
import os
import sys

github_card_agent = Agent(
    name="github_card_agent",
    model="gemini-2.5-flash",
    instruction="""You are a GitHub profile analyst and dev card generator. When a user gives you a 
    GitHub username, you ALWAYS follow this exact sequence: first call scrape_github, then 
    analyze_profile with the result, then generate_card_html with all three inputs, then save_card. 
    Never skip steps. Be enthusiastic about developers' work. If the profile is private or doesn't 
    exist, say so clearly.""",
    tools=[
        McpToolset(
            connection_params=StdioConnectionParams(
                timeout=120.0,  # Gemini API calls need more than the default 5s
                server_params=StdioServerParameters(
                    command=sys.executable,  # Uses same Python as server — works locally & Cloud Run
                    args=[os.path.join(os.path.dirname(__file__), "mcp_server.py")],
                    env={
                        **os.environ,
                        "GEMINI_API_KEY": os.getenv("GEMINI_API_KEY", ""),
                        "GOOGLE_API_KEY": os.getenv("GOOGLE_API_KEY", ""),
                        "GITHUB_TOKEN": os.getenv("GITHUB_TOKEN", ""),
                    },
                )
            )
        )
    ]
)
