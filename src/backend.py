import os
import sys
import gc
import requests
from bs4 import BeautifulSoup
from ddgs import DDGS
from llama_cpp import Llama

class AIBackend:
    def __init__(self):
        self.llm = None
        self.current_model_name = None

    def load_model(self, model_choice):
        """
        Manages VRAM and RAM for different model sizes. 
        Targeting RTX 5060 (8GB VRAM) + 32GB RAM.
        """
        if self.llm:
            print(f"[BACKEND] Unloading {self.current_model_name}...")
            del self.llm
            self.llm = None
            gc.collect()

        # Model Paths - Support for compiled EXE
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        models = {
            "Dark Champion": os.path.join(base_path, "models", "L3.2-8X3B-MOE-Dark-Champion-Inst-18.4B-uncen-ablit_D_AU-Q4_k_m.gguf"),
            "Coder Mode": os.path.join(base_path, "models", "qwen2.5-coder-7b-instruct-q5_k_m.gguf")
        }

        path = models.get(model_choice)
        if not path or not os.path.exists(path):
            return f"Error: Model file not found at {path}"

        # GPU Tuning (RTX 5060 optimization)
        # Dark Champion is ~18.4B MoE, Q4_K_M is roughly 11GB. 
        # Coder is 7B, Q5_K_M is roughly 5.5GB.
        if model_choice == "Dark Champion":
            gpu_layers = 8 # Lowered even more to ensure stability on 8GB VRAM
            ctx_size = 4096
        elif model_choice == "Coder Mode":
            gpu_layers = -1 # Fits easily in 8GB
            ctx_size = 8192
        else:
            gpu_layers = -1
            ctx_size = 4096

        try:
            self.llm = Llama(
                model_path=path,
                n_gpu_layers=gpu_layers,
                n_ctx=ctx_size,
                n_batch=512, # Explicitly set batch size
                verbose=True # Turn on for better debugging in console
            )
            self.current_model_name = model_choice
            return f"Success: {model_choice} loaded."
        except Exception as e:
            return f"Critical Load Error: {str(e)}"

    def web_search_and_scrape(self, query):
        """Performs a web search and returns a condensed context."""
        print(f"[BACKEND] Searching the web for: {query}")
        search_results = ""
        try:
            with DDGS() as ddgs:
                # Use a specific region/safesearch if needed, but text() is basic
                results = list(ddgs.text(query, max_results=5))
                if not results:
                    print("[BACKEND] No results found.")
                    return "No recent information found."
                
                for i, r in enumerate(results):
                    search_results += f"[{i+1}] {r['title']}\nSnippet: {r['body']}\nSource: {r['href']}\n\n"
            
            print(f"[BACKEND] Found {len(results)} results.")
            return search_results
        except Exception as e:
            print(f"[BACKEND] Search Error: {e}")
            return f"Web Search Error: {str(e)}"

    def generate_response(self, user_input, system_prompt=None, web_access=False, history=None):
        if not self.llm:
            yield "System: No model active."
            return

        # Handle Web Search
        if web_access:
            yield "[SYSTEM]: Searching for latest info...\n"
            extra_context = self.web_search_and_scrape(user_input)
            
            # Combine into a stronger prompt
            user_input = (
                f"You have access to current real-time data from the web.\n"
                f"TODAY'S DATE: January 10, 2026\n\n"
                f"WEB SEARCH RESULTS:\n{extra_context}\n"
                f"INSTRUCTION: Use the search results above to answer the user's request. "
                f"Ignore your knowledge cutoff if the search results provide newer information.\n\n"
                f"USER REQUEST: {user_input}"
            )

        if system_prompt:
            sys_prompt = system_prompt
        elif self.current_model_name == "Dark Champion":
            sys_prompt = "You are Dark Champion, a powerful and helpful AI assistant."
        elif self.current_model_name == "Coder Mode":
            sys_prompt = "You are an expert software engineer. Provide high quality code."
        else:
            sys_prompt = "You are a helpful assistant."
        
        # Adjust system prompt if web access is on
        if web_access:
            sys_prompt += " You have access to real-time web search results. If the user asks about current events, use the provided results to answer accurately, even if they contradict your pre-trained knowledge cutoff."
        
        messages = [{"role": "system", "content": sys_prompt}]
        
        # Add history if provided
        if history:
            messages.extend(history)
            
        # Add current user input
        messages.append({"role": "user", "content": user_input})

        try:
            stream = self.llm.create_chat_completion(
                messages=messages,
                stream=True,
                temperature=0.7,
                max_tokens=2048
            )

            for chunk in stream:
                if 'choices' in chunk and len(chunk['choices']) > 0:
                    if 'delta' in chunk['choices'][0] and 'content' in chunk['choices'][0]['delta']:
                        yield chunk['choices'][0]['delta']['content']
        except Exception as e:
            yield f"\n[ERROR]: {str(e)}"
