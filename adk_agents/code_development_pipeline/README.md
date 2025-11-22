# Code Development Pipeline Agent

This agent implements a **Sequential Agentic Flow** for automating software development tasks. It uses a pipeline of specialized agents to write, review, and refactor code, ensuring high-quality output.

## Architecture

The system uses a **Conditional Execution** model:

1.  **General Agent (`root_agent`)**: The entry point. It handles general queries directly.
2.  **`run_coding_pipeline` Tool**: If the user requests a coding task, the General Agent uses this tool to trigger the sequential pipeline.
3.  **Sequential Pipeline**:
    *   **CodeWriterAgent**: Generates initial Python code based on the user's specification.
    *   **CodeReviewerAgent**: Reviews the generated code for correctness, readability, efficiency, and best practices.
    *   **CodeRefactorerAgent**: Refactors the code based on the reviewer's feedback to produce the final output.

## Prerequisites

- Python 3.10+
- Google Cloud Project with Vertex AI API enabled OR Google AI Studio API Key.
- `google-adk` and `google-genai` libraries.

## Configuration

1.  Ensure you have a `.env` file in the `code_development_pipeline` directory (or parent) with your API key:
    ```env
    GOOGLE_API_KEY=your_api_key_here
    ```
2.  The model is configured in `config.py` (default: `gemini-2.5-flash`).

## Usage

### Command Line Interface (CLI)

You can run the pipeline directly from the terminal:

**Interactive Mode:**
```bash
python code_development_pipeline/main.py
```

**Single Query:**
```bash
python code_development_pipeline/main.py "Write a Python function to calculate the Fibonacci sequence."
```

### ADK Web UI

To run the agent with the ADK Web UI:

1.  Navigate to the parent directory (`adk_agents`).
2.  Run the ADK web server:
    ```bash
    adk web
    ```
3.  Open your browser and go to `http://127.0.0.1:8000`.
4.  Select `code_development_pipeline`.
5.  Ask a coding question (e.g., "Write a script to parse a CSV file") to see the pipeline in action.

## Project Structure

-   `agent.py`: Defines the agents (`CodeWriter`, `CodeReviewer`, `CodeRefactorer`, `GeneralAgent`) and the pipeline tool.
-   `config.py`: Configuration constants.
-   `main.py`: CLI entry point.
