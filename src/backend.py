import os
import sys
import gc
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
            # Look for models in the project root
            base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        models = {
            "Dark Champion": "L3.2-8X3B-MOE-Dark-Champion-Inst-18.4B-uncen-ablit_D_AU-Q4_k_m.gguf",
            "Coder Mode": "qwen2.5-coder-7b-instruct-q6_k.gguf"
        }

        filename = models.get(model_choice)
        if not filename:
            return f"Error: Unknown model choice: {model_choice}"

        # Try multiple potential paths
        search_paths = [
            os.path.join(base_path, "models", filename),
            os.path.join(os.getcwd(), "models", filename),
            os.path.join(base_path, filename),
            os.path.join(os.getcwd(), filename)
        ]

        # User specific local paths
        if model_choice == "Dark Champion":
            search_paths.append(r"C:\Users\Ritham\.lmstudio\models\DavidAU\Llama-3.2-8X3B-MOE-Dark-Champion-Instruct-uncensored-abliterated-18.4B-GGUF\L3.2-8X3B-MOE-Dark-Champion-Inst-18.4B-uncen-ablit_D_AU-Q4_k_m.gguf")
        elif model_choice == "Coder Mode":
            search_paths.append(r"C:\Users\Ritham\.lmstudio\models\Qwen\Qwen2.5-Coder-7B-Instruct-GGUF\qwen2.5-coder-7b-instruct-q6_k.gguf")

        path = None
        for p in search_paths:
            if os.path.exists(p):
                path = p
                break

        if not path:
            tried_paths = "\n".join(search_paths)
            return f"Error: Model file not found for {model_choice}. Tried:\n{tried_paths}"

        print(f"[BACKEND] Loading model from: {path}")

        # GPU Tuning (RTX 5060 optimization)
        # Dark Champion is ~18.4B MoE, Q4_K_M is roughly 11GB. 
        # Coder is 7B, Q5_K_M is roughly 5.5GB.
        if model_choice == "Dark Champion":
            gpu_layers = 15 # Reduced from 20 to prevent VRAM OOM on 8GB cards
            ctx_size = 2048 # Reduced from 4096 for MoE stability
        elif model_choice == "Coder Mode":
            gpu_layers = -1 # Fits easily in 8GB
            ctx_size = 4096 # Reduced from 8192 for stability
        else:
            gpu_layers = -1
            ctx_size = 4096

        try:
            # Thread optimization to prevent system-wide lag
            import multiprocessing
            cpu_count = multiprocessing.cpu_count()
            # Use most cores but leave some for the OS/UI to prevent freezing
            threads = max(1, cpu_count // 2) 

            self.llm = Llama(
                model_path=path,
                n_gpu_layers=gpu_layers,
                n_ctx=ctx_size,
                n_batch=512,
                n_threads=threads,
                verbose=True
            )
            self.current_model_name = model_choice
            return f"Success: {model_choice} loaded."
        except Exception as e:
            return f"Critical Load Error: {str(e)}"

    def unload_model(self):
        """Cleanly unloads the model and frees memory."""
        if self.llm:
            print(f"[BACKEND] Unloading {self.current_model_name}...")
            # Explicitly call __del__ or just null it
            del self.llm
            self.llm = None
            gc.collect()
            return True
        return False

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
