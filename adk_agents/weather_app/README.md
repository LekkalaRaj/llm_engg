# Weather App Agent

This is an AI agent built with the Google Agent Development Kit (ADK). It provides real-time weather updates and current time for cities worldwide using the Open-Meteo API.

## Features

- **Weather Information**: Fetches current weather conditions and temperature using the Open-Meteo API.
- **Current Time**: Dynamically calculates the current time in any city by looking up its timezone.
- **Interactive CLI**: Includes a command-line interface for easy interaction.
- **ADK Web Integration**: Compatible with the ADK Web UI for visual interaction and debugging.

## Prerequisites

- Python 3.10+
- A Google Cloud Project with Vertex AI API enabled (if using Vertex AI) OR a Google AI Studio API Key.

## Installation

1. Clone the repository.
2. Install dependencies (assuming you have a `requirements.txt` or install manually):
   ```bash
   pip install google-genai google-adk requests python-dotenv
   ```

## Configuration

1. Create a `.env` file in the `weather_app` directory.
2. Add your API key or project details:
   ```env
   GOOGLE_API_KEY=your_api_key_here
   # OR for Vertex AI
   # GOOGLE_CLOUD_PROJECT=your_project_id
   # GOOGLE_CLOUD_LOCATION=us-central1
   ```

## Usage

### Command Line Interface (CLI)

You can run the agent directly from the terminal:

**Interactive Mode:**
```bash
python weather_app/main.py
```

**Single Query:**
```bash
python weather_app/main.py "What is the weather in Tokyo?"
```

### ADK Web UI

To run the agent with the ADK Web UI:

1. Navigate to the parent directory (`adk_agents`).
2. Run the ADK web server:
   ```bash
   adk web
   ```
3. Open your browser and go to `http://127.0.0.1:8000`.
4. Select `weather_app` to interact with the agent.

## Project Structure

- `agent.py`: Defines the agent, planner, and tools. Exposes `root_agent`.
- `tools.py`: Contains the tool definitions (`get_weather`, `get_current_time`) and API integration logic.
- `config.py`: Configuration constants and environment variable loading.
- `main.py`: Entry point for the CLI.
