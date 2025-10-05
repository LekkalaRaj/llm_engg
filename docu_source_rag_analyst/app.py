import os
import time
import json
import gradio as gr
from dotenv import load_dotenv
from typing import Dict, Any, List
import sys 


# Core LLM Libraries (Using official Google GenAI SDK)
from google import genai
from google.genai.errors import APIError as GenAI_APIError # Renamed to avoid conflict

# RAG & Document Libraries
import chromadb
from pypdf import PdfReader 
# REMOVED: from chromadb.api.models import EmbeddingFunction, Embeddings # This import caused the error
# Import the official Google Generative AI Embedding Function for ChromaDB
from chromadb.utils import embedding_functions

# Load environment variables in a file called .env
load_dotenv(override=True)

# --- CONFIGURATION ---
LLM_MODEL = "gemini-2.5-flash" # Used for generation
# Native embedding model name format
EMBEDDING_MODEL = "models/text-embedding-004" 

try:
    # Use GEMINI_API_KEY in the .env file
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found in environment variables. Please set it in your .env file.")
    
    # Initialize the native Google GenAI client
    client = genai.Client(api_key=GEMINI_API_KEY)
    
except (ValueError, GenAI_APIError) as e:
    print(f"Error initializing Google GenAI Client: {e}")
    client = None

# --- RAG/CHROMA DB SETUP ---
COLLECTION_NAME = "doc_policy_rag_collection"

try:
    # Using chromadb.Client() (in-memory) to bypass the persistent client dependency issue.
    # Data will NOT persist across restarts.
    chroma_client = chromadb.Client()
    
    # Use the official Google Generative AI Embedding Function
    embedding_function = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
        api_key=GEMINI_API_KEY, 
        model_name=EMBEDDING_MODEL
    )
    
except Exception as e:
    # Log the error for debugging
    print(f"Error initializing ChromaDB: {e}")
    chroma_client = None


def get_rag_prompt(question: str, context_chunks: List[Dict[str, Any]]) -> str:
    """Constructs the CoT-enhanced prompt for the RAG query."""
    formatted_context = ""
    for i, chunk in enumerate(context_chunks):
        source_id = f"DOC-{i+1}-{chunk['metadata'].get('source', 'Unknown')}"
        formatted_context += f"--- CONTEXT CHUNK START: {source_id} ---\n"
        formatted_context += chunk['document'] + "\n"
        formatted_context += f"--- CONTEXT CHUNK END: {source_id} ---\n\n"

    prompt = f"""
    ## CONTEXT CHUNKS:
    {formatted_context}

    ## USER QUESTION:
    {question}

    ## RESPONSE FORMAT:
    THOUGHTS: [Your step-by-step reasoning based on the context analysis.]
    FINAL ANSWER: [The complete, cited answer.]
    """
    return prompt

def get_system_message() -> str:
    """Defines the LLM's role and rules for the CoT process."""
    return """
    You are a professional RAG Analyst. Your task is to answer the user's question STRICTLY based on the provided context chunks.

    ## INSTRUCTIONS FOR CoT ANALYSIS:
    1.  **Analyze & Synthesize:** Read the user question and the context. Internally, outline a step-by-step thinking process to determine which chunks are most relevant. Refuse to answer if the context does not contain sufficient information (only state: "I cannot answer this question based on the provided context.").
    2.  **Citation Rule:** Every factual sentence in the final answer MUST be followed by a citation tag corresponding to the relevant source ID (e.g., [Source DOC-1-policy.pdf]).
    3.  **Final Output:** You MUST structure your entire response into two distinct sections: 'THOUGHTS' and 'FINAL ANSWER'.
    """

# ==============================================================================
# 1. INDEXING FUNCTION
# ==============================================================================
def index_document(file_path) -> str:
    """Loads, chunks, embeds, and stores a PDF document in ChromaDB."""
    if not chroma_client:
        return "ERROR: ChromaDB client not initialized. Check GEMINI_API_KEY/Dependencies."
        
    try:
        collection = chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_function
        )

        reader = PdfReader(file_path)
        raw_text = ""
        for page in reader.pages:
            raw_text += page.extract_text()

        # Simple splitting by double newline to create chunks
        chunks = [text.strip() for text in raw_text.split('\n\n') if text.strip()]
        
        documents = []
        metadatas = []
        ids = []
        doc_name = os.path.basename(file_path)

        for i, chunk in enumerate(chunks):
            documents.append(chunk)
            metadatas.append({"source": doc_name, "chunk_id": i + 1})
            ids.append(f"{doc_name}-{i+1}")

        collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        return f"SUCCESS: Document '{doc_name}' indexed with {len(chunks)} chunks and ready for RAG querying. (NOTE: Data is In-Memory and not persistent.)"

    except Exception as e:
        return f"ERROR during indexing: {e}. Please check the file format or API key."


# ==============================================================================
# 2. QUERY FUNCTION
# ==============================================================================
def query_rag_system(question: str) -> List[str]: # Changed return type hint to List[str]
    """Retrieves context and queries the LLM with a CoT prompt."""
    
    # In case of initialization error, return two strings (empty for the second output)
    if not client or not chroma_client:
        return ["System Error. Check initialization logs.", ""]

    try:
        collection = chroma_client.get_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_function
        )
        
        # Retrieval step
        retrieved_data = collection.query(
            query_texts=[question],
            n_results=5, 
            include=['documents', 'metadatas']
        )
        
        context_chunks = []
        for doc, metadata in zip(retrieved_data['documents'][0], retrieved_data['metadatas'][0]):
            context_chunks.append({
                "document": doc,
                "metadata": metadata
            })

        # Construct the final prompt messages
        system_prompt = get_system_message()
        user_prompt = get_rag_prompt(question, context_chunks)
        
        start_time = time.time()
        
        # Generation step using native SDK
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=[{"role": "user", "parts": [{"text": user_prompt}]}],
            config={
                "system_instruction": system_prompt
            }
        )
        
        end_time = time.time()

        llm_output = response.text
        # Native SDK usage metadata extraction
        total_tokens = response.usage_metadata.total_token_count
        
        # Parse the response (remains the same as the format is enforced by prompt)
        if "THOUGHTS:" in llm_output and "FINAL ANSWER:" in llm_output:
            thoughts = llm_output.split("THOUGHTS:")[1].split("FINAL ANSWER:")[0].strip()
            final_answer = llm_output.split("FINAL ANSWER:")[1].strip()
        else:
            thoughts = "Parsing failed. Raw LLM Output follows: " + llm_output
            final_answer = "Error: LLM output format was unexpected. Ensure the model adhered to the CoT format."
            
        token_info = (f"Tokens: {total_tokens} | Latency: {end_time - start_time:.2f}s")

        analysis_output = f"--- LLM CO-T ANALYSIS ({token_info}) ---\n\n{thoughts}\n\n--- RETRIEVED CONTEXT --- \n{user_prompt}"

        # FIX: Return two separate strings for Gradio
        return [final_answer, analysis_output]

    except Exception as e:
        # In case of other errors, return two strings with the error message
        return [f"System Error during query: {e}", "Check the collection name, ensure the document was indexed, and confirm API key validity."]


# ==============================================================================
# 3. GRADIO INTERFACE
# ==============================================================================
with gr.Blocks(title="DocuSource RAG Analyst (CoT Enhanced - Gemini Native SDK)") as demo:
    gr.Markdown(
        """
        # 🧠 DocuSource RAG Analyst: CoT-Enhanced Knowledge Retrieval (Gemini Native SDK)
        This RAG pipeline uses the **official Google GenAI SDK** for all operations, including embeddings via the built-in ChromaDB function, and generation using **Gemini 2.5 Flash**.
        
        **Goal:** Answer complex questions by retrieving and citing information *only* from an uploaded document.
        
        **Setup Note:** Requires `GEMINI_API_KEY` to be set in the environment.
        """
    )
    
    # --- STEP 1: INDEX DOCUMENT ---
    with gr.Row():
        gr.Markdown("## Step 1: Index Your Document")
        
    with gr.Row():
        file_input = gr.File(
            label="Upload PDF Document for Indexing",
            file_types=[".pdf"]
        )
        index_status = gr.Textbox(
            label="Indexing Status",
            value="Ready to upload...",
            interactive=False
        )
        index_btn = gr.Button("1. Index Document to ChromaDB", variant="primary")
        
        index_btn.click(
            fn=index_document,
            inputs=[file_input],
            outputs=[index_status]
        )

    # --- STEP 2: QUERY RAG SYSTEM ---
    gr.Markdown("## Step 2: Ask a Question based on the Indexed Document")
    
    question_input = gr.Textbox(
        lines=3,
        label="Enter your specific question about the document:",
        placeholder="e.g., 'What are the three main requirements for submitting an expense report?'"
    )

    query_btn = gr.Button("2. Query RAG System (Run CoT Analysis)", variant="secondary")

    # Outputs
    final_answer_output = gr.Textbox(
        label="Final, Cited Answer",
        lines=10,
        interactive=False
    )
    
    analysis_output = gr.Code(
        label="CoT Analysis & Retrieved Context (For Verification)",
        language="markdown",
        lines=15,
        interactive=False
    )
    
    # Connect the query button
    query_btn.click(
        fn=lambda q: query_rag_system(q),
        inputs=[question_input],
        outputs=[final_answer_output, analysis_output]
    )

# Launch the application
if __name__ == "__main__":
    if client:
        demo.launch(inbrowser=True)
    else:
        print("\n*** ERROR: Gradio launch aborted. Please check your GEMINI_API_KEY configuration. ***\n")
