
import sys
import os

# Add the parent directory to sys.path to allow importing from the package
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google.genai import types
from weather_app import agent
from weather_app import config

def main():
    """Main entry point for the weather app."""
    runner = agent.create_runner()
    
    # Check for CLI arguments
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        process_query(runner, query)
        return

    # Interactive loop
    print("Weather App Agent (type 'q' or 'quit' to exit)")
    while True:
        try:
            query = input("\nEnter your query: ").strip()
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
        user_id=config.USER_ID, 
        session_id=config.SESSION_ID, 
        new_message=content
    )

    for event in events:
        if event.is_final_response() and event.content:
            final_answer = event.content.parts[0].text.strip()
            print("\n🟢 FINAL ANSWER\n", final_answer, "\n")

if __name__ == "__main__":
    main()
