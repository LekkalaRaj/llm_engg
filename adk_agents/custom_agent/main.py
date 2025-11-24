
import asyncio
import logging
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types
from custom_agent import agent
from custom_agent import config

# --- Configure Logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INITIAL_STATE = {"topic": "a brave kitten exploring a haunted house"}

# --- Setup Runner and Session ---
async def setup_session_and_runner():
    session_service = InMemorySessionService()
    session = await session_service.create_session(
        app_name=config.APP_NAME, 
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID, 
        state=INITIAL_STATE
    )
    logger.info(f"Initial session state: {session.state}")
    runner = Runner(
        agent=agent.root_agent, # Pass the custom orchestrator agent
        app_name=config.APP_NAME,
        session_service=session_service
    )
    return session_service, runner

# --- Function to Interact with the Agent ---
async def call_agent_async(user_input_topic: str):
    """
    Sends a new topic to the agent (overwriting the initial one if needed)
    and runs the workflow.
    """

    session_service, runner = await setup_session_and_runner()

    current_session = await session_service.get_session(
        app_name=config.APP_NAME, 
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID
    )
    if not current_session:
        logger.error("Session not found!")
        return

    current_session.state["topic"] = user_input_topic
    logger.info(f"Updated session state topic to: {user_input_topic}")

    content = types.Content(role='user', parts=[types.Part(text=f"Generate a story about: {user_input_topic}")])
    events = runner.run_async(
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID, 
        new_message=content
    )

    final_response = "No final response captured."
    async for event in events:
        if event.is_final_response() and event.content and event.content.parts:
            logger.info(f"Potential final response from [{event.author}]: {event.content.parts[0].text}")
            final_response = event.content.parts[0].text

    print("\n--- Agent Interaction Result ---")
    print("Agent Final Response: ", final_response)

    final_session = await session_service.get_session(
        app_name=config.APP_NAME, 
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID
    )
    print("Final Session State:")
    import json
    print(json.dumps(final_session.state, indent=2))
    print("-------------------------------\n")

async def main():
    await call_agent_async("a lonely robot finding a friend in a junkyard")

if __name__ == "__main__":
    asyncio.run(main())
