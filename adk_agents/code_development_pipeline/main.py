
import sys
import os

# Add the parent directory to sys.path to allow importing from the package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai import types
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from code_development_pipeline import agent
from code_development_pipeline import config

def main():
    """Main entry point for the code development pipeline."""
    
    # Session and Runner
    session_service = InMemorySessionService()
    # Ensure session exists
    import asyncio
    asyncio.run(session_service.create_session(
        app_name=config.APP_NAME, 
        user_id="user", 
        session_id="session1"
    ))
    
    runner = Runner(
        agent=agent.root_agent, 
        app_name=config.APP_NAME, 
        session_service=session_service
    )
    
    # Check for CLI arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        process_query(runner, query)
        return

    # Interactive loop
    print("Code Development Pipeline (type 'q' or 'quit' to exit)")
    while True:
        try:
            query = input("\nEnter your coding task: ").strip()
            if not query:
                continue
            if query.lower() in ('q', 'quit'):
                print("Goodbye!")
                break
            
            process_query(runner, query)
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"An error occurred: {e}")

def process_query(runner, query):
    """Runs the agent with the given query."""
    print(f"Processing: {query}")
    content = types.Content(role='user', parts=[types.Part(text=query)])
    events = runner.run(
        user_id="user", 
        session_id="session1", 
        new_message=content
    )

    final_output = None
    for event in events:
        # print(f"DEBUG: {event}")
        if event.is_final_response() and event.content:
            final_output = event.content.parts[0].text.strip()
    
    if final_output:
        print("\n🟢 FINAL REFACTORED CODE\n")
        print(final_output)
        print("\n")
    else:
        print("\nNo final output received.\n")

if __name__ == "__main__":
    main()
