# imports

import os
import json
import time
import gradio as gr
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any

# Load environment variables in a file called .env
load_dotenv(override=True)

# --- CONFIGURATION ---
try:
    # 1. Set your Gemini API Key. It's best practice to use an environment variable.
    # For simplicity, you can replace os.environ.get('GEMINI_API_KEY') 
    # with your key as a string: 'YOUR_GEMINI_API_KEY'
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') 

    # 2. Define the base URL for the Gemini OpenAI-compatible endpoint
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # 3. Create the client instance
    client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url=GEMINI_BASE_URL
    )
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    # Set client to None to handle API key errors gracefully
    client = None 

# Model to use
LLM_MODEL = "gemini-2.5-flash" # Fast, capable, and cost-effective for structured extraction

# Define the target JSON schema as a string for the prompt
# Note: Python's triple quotes are great for multi-line JSON structures in prompts.
TARGET_JSON_SCHEMA = """
{
  "personal_info": {
    "name": "string",
    "email": "string",
    "phone": "string",
    "linkedin": "string"
  },
  "summary": "string",
  "experience": [
    {
      "title": "string",
      "company": "string",
      "dates": "string",
      "description_points": ["string", "string", "..."]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "years": "string"
    }
  ],
  "skills": ["string", "string", "..."]
}
"""

# Define Few-Shot Examples
# A single, concise, high-quality example is sufficient to demonstrate the technique.
FEW_SHOT_EXAMPLE_INPUT = """
Rajasekhr Lekkala | LLM Engineer
(65) 1234-1234 | rajasekhar.lekkala.03@gmail.com | https://www.linkedin.com/in/rajasekhar-lekkala-556464146/

SUMMARY
Highly motivated and results-oriented Software Engineer with 10 years of experience specializing in Python and cloud technologies. Proven ability to deliver scalable web applications.

EXPERIENCE
Senior Developer | Tech Innovations Inc. | 2021 – Present
- Led a team of 3 developers to build a new microservices platform using FastAPI and AWS Lambda, reducing latency by 40%.
- Designed and implemented a data ingestion pipeline processing over 1TB of daily log data.
- Mentored junior engineers on best practices for clean code and CI/CD pipelines.

EDUCATION
B.Tech. ECE - CSE     | IIIT RK VALLEY | 2014

SKILLS
Python, FastAPI, AWS, Docker, Kubernetes, SQL, Git, Agile, LLM Prompt Engineering
"""

FEW_SHOT_EXAMPLE_OUTPUT_JSON = {
  "personal_info": {
    "name": "Rajasekhr Lekkala",
    "email": "rajasekhar.lekkala.03@gmail.com",
    "phone": "(65) 1234-1234",
    "linkedin": "https://www.linkedin.com/in/rajasekhar-lekkala-556464146/"
  },
  "summary": "Highly motivated and results-oriented Software Engineer with 10 years of experience specializing in Python and cloud technologies. Proven ability to deliver scalable web applications.",
  "experience": [
    {
      "title": "Senior Developer",
      "company": "Tech Innovations Inc.",
      "dates": "2021 – Present",
      "description_points": [
        "Led a team of 3 developers to build a new microservices platform using FastAPI and AWS Lambda, reducing latency by 40%.",
        "Designed and implemented a data ingestion pipeline processing over 1TB of daily log data.",
        "Mentored junior engineers on best practices for clean code and CI/CD pipelines."
      ]
    }
  ],
  "education": [
    {
      "institution": "IIIT RK VALLEY",
      "degree": "B.Tech. ECE - CSE ",
      "years": "2014"
    }
  ],
  "skills": ["Python", "FastAPI", "AWS", "Docker", "Kubernetes", "SQL", "Git", "Agile", "LLM Prompt Engineering"]
}


def create_few_shot_prompt(raw_resume: str) -> str:
    """Constructs the full few-shot prompt for the LLM."""

    # 1. System Prompt (Role and Instruction)
    system_prompt = f"""
    You are a specialized HR Data Parser and Resume-to-JSON extractor. Your primary goal is to reliably extract all structured data from the provided raw resume text.

    You MUST strictly adhere to the target JSON schema provided below. Do not include any text outside of the JSON structure. Use the key names exactly as specified.

    Target JSON Schema:
    {TARGET_JSON_SCHEMA}

    --- FEW-SHOT EXAMPLE START ---
    RAW RESUME INPUT:
    {FEW_SHOT_EXAMPLE_INPUT}

    PERFECT JSON OUTPUT:
    {json.dumps(FEW_SHOT_EXAMPLE_OUTPUT_JSON, indent=2)}
    --- FEW-SHOT EXAMPLE END ---

    Now, process the user's input.
    """
    
    # 2. User Prompt (The actual data to be processed)
    user_prompt = f"""
    RAW RESUME INPUT:
    {raw_resume}

    PERFECT JSON OUTPUT:
    """

    return system_prompt, user_prompt


def process_input(user_input: str) -> Dict[str, Any]:
    """
    Core function for the Gradio app. Takes raw resume text and uses a 
    few-shot prompt to extract structured data into a dictionary/JSON object.
    """
    if not client:
        return {
            "error": "API Client not initialized. Please set your GEMINI_API_KEY environment variable.",
            "json_output": "Error: API Key Missing",
            "token_info": "Tokens: 0 | Est. Cost: $0.00"
        }

    if not user_input or len(user_input.strip()) < 50:
        return {
            "error": "Please paste a complete resume into the input box.",
            "json_output": "Input too short.",
            "token_info": "Tokens: 0 | Est. Cost: $0.00"
        }

    try:
        system_prompt, user_prompt = create_few_shot_prompt(user_input)
        
        start_time = time.time()
        
        # --- LLM API CALL WITH JSON MODE AND FEW-SHOT PROMPT ---
        response = client.chat.completions.create(
            model=LLM_MODEL,
            response_format={"type": "json_object"}, # Crucial for reliable JSON output
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        # Extract the JSON string and process token/cost data
        json_output_str = response.choices[0].message.content
        end_time = time.time()
        
        # Calculate tokens and estimated cost (simplified for demo)
        prompt_tokens = response.usage.prompt_tokens
        completion_tokens = response.usage.completion_tokens
        total_tokens = response.usage.total_tokens
        
        # Pricing for Gemini 2.5 Flash (API, text/image/video, as of Q4 2025 - check official docs for latest)
        INPUT_PRICE_PER_M = 0.30  # $0.30 / 1 Million tokens
        OUTPUT_PRICE_PER_M = 2.50 # $2.50 / 1 Million tokens

        input_cost = (prompt_tokens / 1_000_000) * INPUT_PRICE_PER_M
        output_cost = (completion_tokens / 1_000_000) * OUTPUT_PRICE_PER_M
        total_cost = input_cost + output_cost

        token_info = (f"Tokens: {total_tokens} (P: {prompt_tokens}, C: {completion_tokens}) | "
                    f"Est. Cost: ${total_cost:.4f} | "
                    f"Latency: {end_time - start_time:.2f}s")
        
        # Safely parse the JSON string
        parsed_json = json.loads(json_output_str)
        
        # Format the JSON for clean display in Gradio
        formatted_json = json.dumps(parsed_json, indent=2)
        
        return {
            "error": "Extraction Successful!",
            "json_output": formatted_json,
            "token_info": token_info
        }

    except Exception as e:
        return {
            "error": f"An API Error occurred: {e}",
            "json_output": "Error: Failed to process resume.",
            "token_info": "Tokens: 0 | Est. Cost: $0.00"
        }

def process_data(user_input):
    """
    Transformer function to convert dict into tuples
    """
    output = process_input(user_input)
    
    # 2. Extract and return values as a tuple
    # Order: [error, json, token_info]
    return (
        output["error"], 
        output["json_output"], 
        output["token_info"]
    )

# --- GRADIO INTERFACE SETUP ---
with gr.Blocks(title="Resume-to-JSON Analyst (Few-Shot Extractor)") as demo:
    gr.Markdown(
        f"""
        # 📄 Resume-to-JSON Analyst (Few-Shot Extractor)
        A high-impact LLM Engineering demo project built with **Python**, **OpenAI SDK**, and **Gradio**. 
        
        This tool uses **Few-Shot Prompting** and the `{LLM_MODEL}` model with **JSON Mode** to reliably convert unstructured resume text into a standard, structured JSON format, showcasing advanced prompt engineering for data extraction.
        """
    )

    with gr.Row():
        # Input Panel
        resume_input = gr.Textbox(
            lines=20, 
            label="1. Paste Raw Resume Text Here (Unstructured)", 
            placeholder="Copy and paste the entire text of a resume here..."
        )
        
        with gr.Column(scale=1):
            # Output Display
            output_status = gr.Textbox(
                label="Extraction Status", 
                value="Waiting for input...", 
                interactive=False, 
                elem_id="status_box"
            )
            
            # Action Button
            submit_btn = gr.Button(
                "🚀 Analyze & Extract (Run Few-Shot Prompt)", 
                variant="primary"
            )

            # Token and Cost Information
            token_display = gr.Textbox(
                label="LLM Resource Metrics", 
                value="Tokens: 0 | Est. Cost: $0.00 | Latency: 0.00s", 
                interactive=False, 
                elem_id="token_box"
            )

    # Structured Output Panel
    json_output = gr.Code(
        label="2. Structured JSON Output (Schema Adherence enforced via Few-Shot)",
        language="json", 
        interactive=False,
        lines=30,
        value=json.dumps({"status": "Output will appear here..."}, indent=2)
    )

    # Connect the button click to the processing function
    submit_btn.click(
        fn=lambda x: process_data(x),
        inputs=[resume_input],
        outputs=[output_status, json_output, token_display],
        # Only update the textboxes that display the output dict keys
        queue=False 
    )
    
# Launch the application
if __name__ == "__main__":
    demo.launch(inbrowser=True)