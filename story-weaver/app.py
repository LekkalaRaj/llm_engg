import os
import json
import time
import base64
import io
import re
import wave
import gradio as gr
from openai import OpenAI
from typing import Dict, Any, List, Optional, Tuple, Union
from dotenv import load_dotenv

# --- CONFIGURATION & CLIENT SETUP ---
load_dotenv(override=True)

# IMPORTANT: The GEMINI_API_KEY is expected to be provided by the environment.
# Use a placeholder if empty to satisfy the SDK's header requirement and direct fetch calls,
# allowing the proxy to inject the actual token later.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or "placeholder_key_for_proxy"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

# Models
LLM_MODEL = "gemini-2.5-flash"
IMAGE_MODEL = "imagen-3.0-generate-002" # Used for image generation
TTS_MODEL = "gemini-2.5-flash-preview-tts" # Used for text-to-speech

# Initialize client using the OpenAI SDK pointing to the Gemini endpoint
try:
    # Use GEMINI_API_KEY which is guaranteed to be non-empty (placeholder if needed)
    client = OpenAI(api_key=GEMINI_API_KEY, base_url=GEMINI_BASE_URL)
except Exception as e:
    print(f"Warning: Could not initialize OpenAI client: {e}")
    client = None

# --- TOOL DEFINITION: The Lore Keeper ---

def lore_keeper_lookup(topic: str) -> str:
    """
    Simulates a database lookup for fictional lore, providing rules or facts 
    that the story must adhere to. The bot must integrate this information.
    """
    # UPDATED: Lore database focused on Indian Mythology
    lore_db = {
        "Dharma": "Dharma mandates that all acts must prioritize righteous conduct and duty above personal desire.",
        "Vishnu's Avatars": "The next major challenge must involve the theme of preserving cosmic order, mirroring Vishnu's role.",
        "Mahadev's weapons": "Mahadev's primary weapon is the Trishula, symbolizing the three aspects of consciousness: wakefulness, dream, and deep sleep.",
        "Krishna's Vows": "Krishna's vow of non-violence means he cannot wield a physical weapon in battle, but must guide through strategy."
    }
    
    if topic in lore_db:
        return json.dumps({"lore_data": lore_db[topic], "source": "Internal Lore Keeper (Mythology)"})
    else:
        return json.dumps({"lore_data": f"No specific lore found for '{topic}'. The story can proceed without hard constraint.", "source": "Internal Lore Keeper (Mythology)"})

# Mapping tool functions for the model to call
tool_functions = {
    "lore_keeper_lookup": lore_keeper_lookup,
}

# Define the tool schema for the API
# FIX: Changed structure from function_declarations array to the standard OpenAI SDK Tool Object format
tools = [{
    "type": "function",
    "function": {
        "name": "lore_keeper_lookup",
        "description": lore_keeper_lookup.__doc__.strip(),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "The specific lore topic, artifact, or rule to look up in the story's knowledge base."},
            },
            "required": ["topic"],
        },
    }
}]

# --- MULTIMODAL UTILITIES ---

def pcm_to_wav(pcm_data: bytes, sample_rate: int = 16000) -> bytes:
    """Converts raw PCM data (signed 16-bit, mono) to a standard WAV file format."""
    with io.BytesIO() as wav_io:
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit PCM (2 bytes)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm_data)
        
        return wav_io.getvalue()

def generate_image(prompt: str) -> Optional[str]:
    """Calls the Imagen API to generate an image and returns a base64 URL."""
    print("-> Generating Image...")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGE_MODEL}:predict?key={GEMINI_API_KEY}"
    
    payload = { 
        "instances": { 
            "prompt": prompt,
            "config": {
                "number_of_images": 1,
                "output_mime_type": "image/png",
                "aspect_ratio": "1:1"
            }
        }, 
        "parameters": { 
            "sampleCount": 1
        } 
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = gr.client.fetch(url, { # Using gr.client.fetch as instructed for external calls
                "method": "POST",
                "headers": { 'Content-Type': 'application/json' },
                "body": json.dumps(payload)
            })
            
            result = response.json()
            
            if result.get('predictions') and result['predictions'][0].get('bytesBase64Encoded'):
                base64_data = result['predictions'][0]['bytesBase64Encoded']
                # Return the data URI
                return f"data:image/png;base64,{base64_data}"
            
            print(f"Image generation failed on attempt {attempt+1}: {result.get('error', 'Unknown Error')}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"Image API call exception on attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt)
            
    return None

def generate_tts_audio(text_to_speak: str, voice_name: str = "Kore") -> Optional[str]:
    """Calls the Gemini TTS API, converts PCM to WAV, and returns the temporary file path."""
    print("-> Generating TTS Audio...")
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{TTS_MODEL}:generateContent?key={GEMINI_API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [{"text": text_to_speak}]
        }],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": { "voiceName": voice_name }
                }
            }
        },
        "model": TTS_MODEL
    }

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = gr.client.fetch(url, { # Using gr.client.fetch as instructed for external calls
                "method": "POST",
                "headers": { 'Content-Type': 'application/json' },
                "body": json.dumps(payload)
            })
            
            result = response.json()
            
            candidate = result.get('candidates', [{}])[0]
            part = candidate.get('content', {}).get('parts', [{}])[0]
            audio_data_b64 = part.get('inlineData', {}).get('data')
            mime_type = part.get('inlineData', {}).get('mimeType', '')

            if audio_data_b64 and mime_type.startswith("audio/L16"):
                # Extract sample rate from mimeType if available, default to 16000
                sample_rate_match = re.search(r'rate=(\d+)', mime_type)
                sample_rate = int(sample_rate_match.group(1)) if sample_rate_match else 16000
                
                pcm_data = base64.b64decode(audio_data_b64)
                wav_bytes = pcm_to_wav(pcm_data, sample_rate)
                
                # Save the WAV file temporarily (Gradio will clean up temp files)
                audio_path = f"temp_tts_{time.time()}.wav"
                with open(audio_path, 'wb') as f:
                    f.write(wav_bytes)
                
                return audio_path
            
            print(f"TTS generation failed on attempt {attempt+1}: {result.get('error', 'Unknown Error')}")
            time.sleep(2 ** attempt)
        except Exception as e:
            print(f"TTS API call exception on attempt {attempt+1}: {e}")
            time.sleep(2 ** attempt)
            
    return None

# --- CHAT & TOOL-USE ORCHESTRATION ---

# Helper to format Gradio history for the Gemini API
def format_history(history: List[Tuple[str, str]]) -> List[Dict[str, str]]:
    formatted = []
    for user_msg, bot_msg in history:
        # User message
        if user_msg:
            formatted.append({"role": "user", "content": user_msg})
        
        # Bot message (handle multimodal tuples from previous turns)
        if bot_msg:
            bot_text = bot_msg[0] if isinstance(bot_msg, tuple) else bot_msg
            formatted.append({"role": "model", "content": bot_text})
    return formatted

def story_weaver_response(message: str, history: List[Tuple[str, str]]) -> Union[str, Tuple[str, str]]:
    """
    Handles the full conversational turn, including tool use and multimodal outputs.
    """
    if not client:
        return "The LLM client is not initialized. Please ensure your GEMINI_API_KEY is set correctly."

    # 1. Prepare history and system prompt
    full_history = format_history(history)
    
    # System instruction for Mythology theme
    system_instruction = "You are the Interactive Mythological Story Weaver. Continue the imaginative narrative based on the user's prompt, drawing deeply from Indian epics like Ramayana and Mahabharata, and stories of the Trimurti (Brahma, Vishnu, Shiva). You must use the lore_keeper_lookup tool if the user mentions specific concepts like 'Dharma' or 'Vishnu's Avatars'. When prompted to 'read out loud', use the dialogue provided. Keep your narrative segments short and engaging."
    
    # FIX: Restructure messages to include system instruction as the first element
    llm_messages = [
        {"role": "system", "content": system_instruction}
    ] + full_history + [
        {"role": "user", "content": message}
    ]
    
    final_text = ""
    image_url = None
    audio_path = None
    
    # --- Tool Calling Loop ---
    # The loop runs until the model generates a final text response (or hits the retry limit)
    for _ in range(5): 
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=llm_messages,
                tools=tools,
                # REMOVED: system_instruction=system_instruction keyword argument
            )
        except Exception as e:
            return f"Error connecting to LLM: {e}"

        response_message = response.choices[0].message
        
        # Check for Tool Calls (Execution of Tool-Use Requirement)
        if response_message.tool_calls:
            llm_messages.append(response_message) # Append model's tool call request
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                if function_name in tool_functions:
                    tool_output = tool_functions[function_name](**arguments)
                    
                    # Append tool result back to messages
                    llm_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "name": function_name,
                        "content": tool_output,
                    })
                
            # Loop continues to let the LLM generate the final narrative using the tool output
            continue 
        
        # Text is generated (Tool loop breaks)
        final_text = response_message.content
        break
    
    # --- Modality Generation (Story 1 & 2) ---
    
    # A. Image Generation Check (Triggered mainly on first turn or explicit request)
    image_keywords = ["image", "visualize", "scene", "first part"]
    is_initial_image_prompt = len(history) == 0 and any(kw in message.lower() for kw in image_keywords)
    
    if is_initial_image_prompt:
        # Use the user's detailed prompt for high-quality image generation
        image_prompt = f"{message}. Epic, highly detailed, style of classic Indian art or fresco."
        image_url = generate_image(image_prompt)
        
    # B. TTS Audio Generation Check (Triggered by explicit audio/dialogue requests)
    if "speak" in message.lower() or "read out loud" in message.lower() or "dialogue" in message.lower():
        # Heuristic: Find text inside quotes for the dialogue
        dialogue_match = re.search(r'["“](.*?)[”"]', final_text, re.DOTALL)
        
        if dialogue_match:
            text_to_speak = dialogue_match.group(1).strip()
            # Ensure text is not empty before calling TTS
            if text_to_speak:
                audio_path = generate_tts_audio(text_to_speak)
        else:
            # If no quotes found, speak the entire generated text
            audio_path = generate_tts_audio(final_text)

    # --- Final Output Formatting for Gradio ChatInterface ---
    if audio_path:
        # Return (text, audio_file_path) -> Gradio renders text + Audio component
        return (final_text, audio_path) 
    elif image_url:
        # Return (text, image_url) -> Gradio renders text + Image component
        return (final_text, image_url)
    else:
        # Standard text response
        return final_text

# --- GRADIO INTERFACE SETUP ---

# UPDATED: Custom components for initial story trigger (Mythology theme)
initial_message = "Start a story about a young prince who is Lord Rama's ancestor, setting out on a quest to defeat a demon from the Mahabharata era."

# Define the chat interface
demo = gr.ChatInterface(
    fn=story_weaver_response,
    title="🕉️ Interactive Mythological Story Weaver (Indian Epics)", # UPDATED Title
    description=(
        "**User Story 1:** Start by describing a scene (e.g., 'Start a story about a young prince...'). The bot will respond with **Text and an Image** based on the scene.\n"
        "**User Story 2:** Continue the story and ask for dialogue to be read out loud (e.g., 'Make Lord Krishna speak, and read his line out loud.'). The bot will respond with **Text and Audio**.\n"
        "**Tool Use:** Try asking about **'Dharma'** or **'Vishnu's Avatars'** to see the Mythological Lore Keeper in action." # UPDATED Tool Examples
    ),
    textbox=gr.Textbox(
        placeholder="Continue the epic saga...", # UPDATED Placeholder
        show_copy_button=True,
    ),
    submit_btn="Continue Story",
    # REMOVED: clear_btn argument causing TypeError
    theme=gr.themes.Monochrome(),
    examples=[
        [initial_message], # UPDATED Example
        ["Tell me what happens next, and make sure the prince's actions respect the 'Dharma' principle."], # UPDATED Example
        ["Lord Krishna appears. Make his next line 'Be fearless, for destiny favors the righteous.' and read it out loud."], # UPDATED Example
    ]
)

if __name__ == "__main__":
    if client:
        # Launching the demo
        demo.launch(inbrowser=True)
    else:
        print("Application failed to launch due to missing API configuration.")
