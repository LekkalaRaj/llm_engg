# Story Flow Agent (Custom Agent)

This agent demonstrates a custom orchestration workflow using the Google Agent Development Kit (ADK). It generates a story, critiques and revises it in a loop, and then performs grammar and tone checks.

## Architecture

The agent uses a combination of `LoopAgent` and `SequentialAgent` to create a complex flow:

1.  **StoryGenerator**: Writes an initial story based on a topic.
2.  **CriticReviserLoop** (`LoopAgent`):
    *   **Critic**: Reviews the story.
    *   **Reviser**: Improves the story based on feedback.
    *   *Runs for 2 iterations.*
3.  **PostProcessing** (`SequentialAgent`):
    *   **GrammarCheck**: Checks for grammar errors.
    *   **ToneCheck**: Analyzes the tone (positive/negative/neutral).
4.  **Conditional Logic**: If the tone is negative, the story is regenerated.

## Prerequisites

- Python 3.10+
- Google Cloud Project with Vertex AI API enabled OR Google AI Studio API Key.

## Configuration

1.  Ensure you have a `.env` file in the `custom_agent` directory (or parent) with your API key:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    ```
2.  Configuration constants are in `config.py`.

## Usage

### Command Line Interface (CLI)

```bash
python -m custom_agent.main
```

### ADK Web UI

1.  Run the ADK web server:
    ```bash
    adk web
    ```
2.  Open `http://127.0.0.1:8000`.
3.  Select `custom_agent`.

## Project Structure

-   `agent.py`: Defines the `StoryFlowAgent` class and the sub-agents.
-   `config.py`: Configuration constants.
-   `main.py`: CLI entry point.
