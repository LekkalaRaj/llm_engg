import os
import json
import time
import gradio as gr
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go # Added explicit go import for clarity
from openai import OpenAI
from dotenv import load_dotenv
from typing import Dict, Any, List, Optional, Tuple

# --- CONFIGURATION & CLIENT SETUP ---

# Load environment variables in a file called .env
load_dotenv(override=True)

try:
    # Use GEMINI_API_KEY for the OpenAI-compatible endpoint
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
    
    if not GEMINI_API_KEY:
        # Using a default error message if key is missing
        raise ValueError("GEMINI_API_KEY not found in environment variables.")

    # Initialize OpenAI client pointing to the Gemini endpoint
    client = OpenAI(
        api_key=GEMINI_API_KEY,
        base_url=GEMINI_BASE_URL
    )
    LLM_MODEL = "gemini-2.5-flash" 
    
except Exception as e:
    print(f"Error initializing OpenAI client: {e}")
    client = None
    LLM_MODEL = "gemini-2.5-flash" 


# --- YFINANCE & DATA FETCHING ---

def fetch_financial_data(ticker: str, metric: str = 'Quarterly Revenue') -> Optional[pd.DataFrame]:
    """
    Fetches the last four quarters of a primary financial statement metric 
    for an Indian stock ticker (requires '.NS' suffix).
    """
    try:
        # Append .NS suffix for Indian National Stock Exchange
        full_ticker = f"{ticker.upper()}.NS"
        stock = yf.Ticker(full_ticker)
        
        if metric == 'Quarterly Revenue':
            # Get income statement and extract Total Revenue
            financials = stock.quarterly_income_stmt.loc['Total Revenue'].T
            financials.name = 'Value'
            df = financials.reset_index()
            df.columns = ['Date', 'Value']
            
            # Data Cleaning: ensure 'Value' is numeric
            df['Value'] = pd.to_numeric(df['Value'], errors='coerce') 
            df.dropna(subset=['Value'], inplace=True) 
            
            df['Metric'] = metric
            df['Ticker'] = ticker.upper()
            
            # Use only the last 4 quarters (rows)
            return df.head(4).sort_values('Date', ascending=True)

        return None
    
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return None

# --- PLOTLY VISUALIZATION ---

def generate_comparative_chart(df: pd.DataFrame, metric: str) -> Optional[go.Figure]:
    """
    Generates an interactive Plotly Figure object comparing two stocks.
    
    Returns the Plotly Figure object or None if data is insufficient.
    """
    # Check if there is enough data to chart (requires two unique tickers)
    if df.empty or df['Ticker'].nunique() < 2:
        return None

    # Convert large numbers for better display
    # Assumes data is in base currency units (Rupees), converting to Billion Rupees (₹ Billion)
    df['Value_Formatted'] = df['Value'] / 1_000_000_000 

    fig = px.bar(
        df, 
        x='Date', 
        y='Value_Formatted', 
        color='Ticker',
        barmode='group',
        text='Value_Formatted',
        title=f"Comparative Quarterly {metric} (₹ Billion)",
        height=500
    )
    
    fig.update_traces(texttemplate='%{text:.2f}B', textposition='outside')
    fig.update_layout(xaxis_title="Quarter End Date", yaxis_title=f"{metric} (₹ Billion)")
    fig.update_layout(uniformtext_minsize=8, uniformtext_mode='hide', margin=dict(t=50, b=50))
    
    # Return the Plotly Figure object directly for gr.Plot
    return fig


# --- LLM AUGMENTATION & GENERATION ---

def get_rag_prompt(data_markdown: str, ticker1: str, ticker2: str, metric: str) -> str:
    """Constructs the augmented prompt for the LLM to generate the narrative summary."""
    
    prompt = f"""
    You are a highly skilled Financial Analyst. Your task is to perform a comparative deep-dive analysis.
    
    1. Analyze the provided financial data (Quarterly {metric}) for two companies: {ticker1} and {ticker2}.
    2. Identify key trends, significant changes, and state clearly which company demonstrated stronger growth or performance in the last four reported quarters.
    3. Generate a concise, professional, and cited narrative summary.

    ## PROVIDED FINANCIAL DATA (AUGMENTED CONTEXT)
    {data_markdown}
    
    ## INSTRUCTIONS:
    * Focus on trends over the four-quarter period.
    * Do not include the data table itself in your FINAL ANSWER. Only provide the narrative summary.
    * Use Indian Rupee context where appropriate in your analysis (e.g., mention performance in terms of crores or lakhs).
    """
    return prompt

def deep_dive_analysis(ticker1: str, ticker2: str, metric: str) -> Tuple[str, str, str, Optional[go.Figure]]:
    """
    Main function to orchestrate data fetching, chart generation, and LLM analysis.
    
    Returns: status, narrative_summary, data_table_markdown, chart_figure_or_none
    """
    # Initialize default outputs
    default_narrative = "N/A"
    default_data_table = "N/A"
    default_chart_fig = None
    
    if not client:
        return (
            "ERROR: LLM Client not initialized. Check GEMINI_API_KEY in .env.", 
            default_narrative, default_data_table, default_chart_fig
        )

    # 1. Data Fetching and Merging
    df1 = fetch_financial_data(ticker1, metric)
    df2 = fetch_financial_data(ticker2, metric)
    
    df_combined_list = []
    if df1 is not None and not df1.empty:
        df_combined_list.append(df1)
    if df2 is not None and not df2.empty:
        df_combined_list.append(df2)

    if not df_combined_list:
        status = f"ERROR: Could not fetch *any* complete financial data for {ticker1}.NS or {ticker2}.NS. Check tickers, availability, and internet connection."
        return (status, default_narrative, default_data_table, default_chart_fig)

    df_combined = pd.concat(df_combined_list)
    data_table_markdown = df_combined.to_markdown(index=False)
    
    # 2. Visualization
    chart_fig = generate_comparative_chart(df_combined, metric)
    
    # 3. Handle Chart Warnings / Insufficient Data
    if chart_fig is None:
        narrative_summary = "Cannot perform comparative analysis. Only data for one ticker (or none) was available. Chart cleared."
        status = f"WARNING: Only data for {df_combined['Ticker'].unique()[0]} was available. Comparative analysis requires two tickers."
        
        # Return here, skipping the LLM call, but providing the raw data
        return (status, narrative_summary, data_table_markdown, default_chart_fig)


    # 4. LLM Augmentation & Generation (Only runs if chart_fig is available)
    user_prompt = get_rag_prompt(data_table_markdown, ticker1, ticker2, metric)
    
    start_time = time.time()
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a specialized Financial Analyst Copilot for the Indian stock market."},
                {"role": "user", "content": user_prompt}
            ]
        )
        narrative_summary = response.choices[0].message.content
        latency = time.time() - start_time
        status = f"SUCCESS: Analysis and narrative completed in {latency:.2f}s."

    except Exception as e:
        narrative_summary = f"LLM Generation Error: {e}"
        status = "CRITICAL ERROR during LLM call."

    # 5. Return results for Gradio
    return (status, narrative_summary, data_table_markdown, chart_fig)


# --- GRADIO INTERFACE SETUP ---

with gr.Blocks(title="Financial Analyst Copilot - Indian Market Deep Dive") as demo:
    gr.Markdown(
        """
        # 🇮🇳 Financial Analyst Copilot: Comparative Health Deep Dive
        This application uses the **OpenAI SDK (via Gemini Endpoint)**, **yfinance**, and **Plotly** to perform a comparative financial analysis on two Indian stocks.

        Enter two valid NSE tickers (e.g., `RELIANCE`, `TCS`).
        """
    )
    
    with gr.Row():
        ticker_input_1 = gr.Textbox(
            label="Company 1 Ticker (e.g., RELIANCE)",
            value="RELIANCE"
        )
        ticker_input_2 = gr.Textbox(
            label="Company 2 Ticker (e.g., TATAMOTORS)",
            value="TATAMOTORS"
        )
        metric_input = gr.Dropdown(
            label="Metric to Compare",
            choices=["Quarterly Revenue"],
            value="Quarterly Revenue"
        )

    analyze_btn = gr.Button("🚀 Run Comparative Deep Dive Analysis", variant="primary")
    
    # --- OUTPUTS ---
    status_output = gr.Textbox(label="Status", interactive=False)
    
    gr.Markdown("## 1. Comparative Performance Chart")
    # FIX APPLIED HERE: gr.Plot component to display the Plotly Figure object
    chart_output = gr.Plot(label="Interactive Plotly Chart") 
    
    gr.Markdown("## 2. LLM Narrative Summary")
    narrative_output = gr.Textbox(
        label="Analyst Summary (LLM Interpretation of Data)",
        lines=10, 
        interactive=False
    )
    
    gr.Markdown("## 3. Raw Data Context (Augmented RAG Source)")
    data_table_output = gr.Code(
        label="Raw Quarterly Data (Input Context for LLM)",
        language="markdown",
        interactive=False,
        lines=15
    )
    
    # Connect function to interface
    analyze_btn.click(
        fn=deep_dive_analysis,
        inputs=[ticker_input_1, ticker_input_2, metric_input],
        outputs=[status_output, narrative_output, data_table_output, chart_output]
    )
    
# Launch the application
if __name__ == "__main__":
    if client:
        demo.launch(inbrowser=True)
    else:
        print("\n*** ERROR: Gradio launch aborted. Please check your GEMINI_API_KEY configuration. ***\n")