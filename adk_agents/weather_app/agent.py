from google.genai.types import ThinkingConfig
from google.adk.agents.llm_agent import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.planners import BuiltInPlanner

from . import config
from . import tools

def create_agent() -> LlmAgent:
    """Creates and configures the agent."""
    
    # Step 1: Create a ThinkingConfig
    thinking_config = ThinkingConfig(
        include_thoughts=True,   # Ask the model to include its thoughts in the response
        thinking_budget=256      # Limit the 'thinking' to 256 tokens (adjust as needed)
    )
    
    # Step 2: Instantiate BuiltInPlanner
    planner = BuiltInPlanner(
        thinking_config=thinking_config
    )
    
    # Step 3: Wrap the planner in an LlmAgent
    agent = LlmAgent(
        model=config.MODEL_NAME,
        name="weather_and_time_agent",
        instruction="You are an agent that returns time and weather",
        planner=planner,
        tools=[tools.get_weather, tools.get_current_time]
    )
    return agent

# Create the root agent instance
root_agent = create_agent()

def create_runner() -> Runner:
    """Creates and configures the agent runner."""
    
    # Session and Runner
    session_service = InMemorySessionService()
    # Ensure session exists
    import asyncio
    asyncio.run(session_service.create_session(
        app_name=config.APP_NAME, 
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID
    ))
    
    runner = Runner(
        agent=root_agent, 
        app_name=config.APP_NAME, 
        session_service=session_service
    )
    
    return runner