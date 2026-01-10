import customtkinter as ctk
import threading
import os
import sys
import subprocess
from src.backend import AIBackend
from tkinter import filedialog
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader
from docx import Document
import datetime
from tkinter import messagebox

try:
    import pyperclip
    HAS_PYPERCLIP = True
except ImportError:
    HAS_PYPERCLIP = False

# THEME: Roa.ai Blue/Dark
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue") 

# CUSTOM PALETTE
BG_COLOR = "#0D0F11"
BOX_BG = "#1A1C1E"
ACCENT_COLOR = "#62D6E3"
TEXT_COLOR = "#D1D5DB"
USER_BUBBLE = "#222426"
AI_BUBBLE = "#1A1C1E"

# FONTS
MAIN_FONT = "Terminal"

class RoaApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        # Handle Base Path for EXE vs Script
        if getattr(sys, 'frozen', False):
            self.base_dir = os.path.dirname(sys.executable)
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))

        self.backend = AIBackend()
        self.configure(fg_color=BG_COLOR)
        self.is_generating = False
        self.chat_history = {
            "RANDOM": [],
            "PERSONAL": [],
            "CONTEXT": [],
            "DIARY": [],
            "CODER": []
        }
        self.current_ai_response = ""

        # Window Setup
        self.title("Roa.ai // AI Workbench")
        self.geometry("1200x800")
        
        # Grid Configuration
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR (LEFT) ===
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=BG_COLOR)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.logo = ctk.CTkLabel(self.sidebar, text="ROA.AI V2", font=ctk.CTkFont(family=MAIN_FONT, size=24, weight="bold"), text_color=ACCENT_COLOR)
        self.logo.grid(row=0, column=0, padx=20, pady=(30, 20))

        # Model Section Box
        self.model_box = ctk.CTkFrame(self.sidebar, fg_color=BOX_BG, corner_radius=10, border_width=1, border_color="#2A2D30")
        self.model_box.grid(row=1, column=0, padx=15, pady=10, sticky="ew")
        
        self.lbl_model = ctk.CTkLabel(self.model_box, text="Models Selection", font=ctk.CTkFont(family=MAIN_FONT, size=14, weight="bold"))
        self.lbl_model.pack(padx=15, pady=(10, 5), anchor="w")
        
        self.model_menu = ctk.CTkOptionMenu(
            self.model_box, 
            values=["Dark Champion", "Coder Mode"],
            font=(MAIN_FONT, 13),
            dropdown_font=(MAIN_FONT, 13),
            fg_color="#222426",
            button_color="#222426",
            button_hover_color="#303336",
            dynamic_resizing=False
        )
        self.model_menu.pack(padx=15, pady=5, fill="x")

        self.load_model_btn = ctk.CTkButton(
            self.model_box, 
            text="LOAD MODEL", 
            font=(MAIN_FONT, 13, "bold"),
            fg_color=ACCENT_COLOR,
            text_color="black",
            hover_color="#4FBBC8",
            command=lambda: self.start_model_load_thread(self.model_menu.get())
        )
        self.load_model_btn.pack(padx=15, pady=(5, 15), fill="x")

        # Status and Controls Section
        self.status_box = ctk.CTkFrame(self.sidebar, fg_color=BOX_BG, corner_radius=10, border_width=1, border_color="#2A2D30")
        self.status_box.grid(row=2, column=0, padx=15, pady=10, sticky="ew")

        self.status_lbl = ctk.CTkLabel(self.status_box, text="Status: IDLE", text_color="#10B981", font=ctk.CTkFont(family=MAIN_FONT, size=12))
        self.status_lbl.pack(padx=15, pady=(10, 5))

        self.web_access_var = ctk.BooleanVar(value=False)
        self.web_access_switch = ctk.CTkSwitch(self.status_box, text="Web Access", font=(MAIN_FONT, 12), variable=self.web_access_var, progress_color=ACCENT_COLOR)
        self.web_access_switch.pack(padx=15, pady=5)

        self.vpn_var = ctk.BooleanVar(value=False)
        self.vpn_switch = ctk.CTkSwitch(self.status_box, text="VPN Stealth Mode", font=(MAIN_FONT, 12), variable=self.vpn_var, progress_color=ACCENT_COLOR, command=self.toggle_vpn)
        self.vpn_switch.pack(padx=15, pady=5)

        self.vpn_status_lbl = ctk.CTkLabel(self.status_box, text="Connection: EXPOSED", text_color="#EF4444", font=ctk.CTkFont(family=MAIN_FONT, size=11, weight="bold"))
        self.vpn_status_lbl.pack(padx=15, pady=(0, 5))

        self.stop_btn = ctk.CTkButton(self.status_box, text="STOP GENERATION", font=(MAIN_FONT, 12, "bold"), fg_color="#EF4444", hover_color="#DC2626", command=self.stop_generation)
        self.stop_btn.pack(padx=15, pady=(5, 15), fill="x")
        self.stop_btn.configure(state="disabled")

        # === MEMORY SYSTEM (SIDEBAR) ===
        self.memory_box = ctk.CTkFrame(self.sidebar, fg_color=BOX_BG, corner_radius=10, border_width=1, border_color="#2A2D30")
        self.memory_box.grid(row=3, column=0, padx=15, pady=10, sticky="nsew")
        self.sidebar.grid_rowconfigure(3, weight=1)

        self.mem_lbl = ctk.CTkLabel(self.memory_box, text="Load Memory", font=ctk.CTkFont(family=MAIN_FONT, size=14, weight="bold"))
        self.mem_lbl.pack(padx=15, pady=(10, 5), anchor="w")
        
        self.memory_frame = ctk.CTkScrollableFrame(self.memory_box, fg_color="transparent")
        self.memory_frame.pack(padx=15, pady=5, fill="both", expand=True)
        
        self.active_mem_lbl = ctk.CTkLabel(self.memory_box, text="Active Context: 0", text_color="gray", font=ctk.CTkFont(family=MAIN_FONT, size=11))
        self.active_mem_lbl.pack(padx=15, pady=0)
        
        self.mem_ctrls = ctk.CTkFrame(self.memory_box, fg_color="transparent")
        self.mem_ctrls.pack(padx=15, pady=(5, 15), fill="x")
        
        ctk.CTkButton(self.mem_ctrls, text="REFRESH", font=(MAIN_FONT, 11), width=70, height=28, fg_color="#222426", command=self.refresh_memory_list).pack(side="left", padx=2)
        ctk.CTkButton(self.mem_ctrls, text="CLEAR", font=(MAIN_FONT, 11), width=70, height=28, fg_color="#222426", command=self.clear_active_memory).pack(side="right", padx=2)

        self.active_memories = {} # {filepath: content}

        # === MAIN AREA (TABS) ===
        self.tabview = ctk.CTkTabview(
            self, 
            corner_radius=10, 
            fg_color=BG_COLOR, 
            segmented_button_selected_color=ACCENT_COLOR, 
            segmented_button_selected_hover_color="#4FBBC8", 
            segmented_button_unselected_color="#1A1C1E"
        )
        # Apply font after creation if needed, though CTkTabview usually inherits or uses segmented_button styles.
        # However, font is NOT a valid kwarg for CTkTabview constructor in current version.
        self.tabview._segmented_button.configure(font=(MAIN_FONT, 11))
        self.tabview.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")
        
        self.tab_random = self.tabview.add("Random Chat")
        self.tab_personal = self.tabview.add("Personal Chat")
        self.tab_context = self.tabview.add("Context")
        self.tab_diary = self.tabview.add("Diary")
        self.tab_coder = self.tabview.add("Coder")

        self.setup_random_chat_tab()
        self.setup_personal_chat_tab()
        self.setup_context_tab()
        self.setup_diary_tab()
        self.setup_coder_tab()

        self.tabview.set("Diary")
        # Initial model load
        self.after(500, lambda: self.start_model_load_thread("Dark Champion"))
        # Initial memory scan
        self.after(1000, self.refresh_memory_list)

    def on_tab_change(self):
        # Navigation no longer triggers automatic model loading
        pass

    def refresh_memory_list(self):
        # Clear current frame
        for child in self.memory_frame.winfo_children():
            child.destroy()
            
        log_folders = ["diary_logs", "personal_logs", "coder_logs", "random_logs", "context_logs"]
        files_found = False
        
        for folder in log_folders:
            folder_path = os.path.join(self.base_dir, folder)
            if os.path.exists(folder_path):
                files = os.listdir(folder_path)
                files.sort(reverse=True)
                for f in files:
                    if f.endswith(".txt"):
                        files_found = True
                        path = os.path.join(folder_path, f)
                        is_active = path in self.active_memories
                        
                        btn = ctk.CTkButton(
                            self.memory_frame, 
                            text=f"{f} - {os.path.getsize(path)} bytes", 
                            font=(MAIN_FONT, 11),
                            anchor="w",
                            fg_color="#222426" if not is_active else "#2E4A4D",
                            hover_color="#303336" if not is_active else "#3A5C5F",
                            border_width=1 if is_active else 0,
                            border_color=ACCENT_COLOR,
                            corner_radius=6,
                            height=32,
                            command=lambda p=path: self.toggle_memory(p)
                        )
                        btn.pack(fill="x", pady=3, padx=5)
        
        if not files_found:
            ctk.CTkLabel(self.memory_frame, text="No logs indexed", text_color="gray", font=(MAIN_FONT, 12)).pack(pady=20)

    def toggle_memory(self, filepath):
        if filepath in self.active_memories:
            del self.active_memories[filepath]
        else:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.active_memories[filepath] = f.read()
            except Exception as e:
                messagebox.showerror("Memory Error", f"Could not read {filepath}: {e}")
        
        self.active_mem_lbl.configure(text=f"Active: {len(self.active_memories)} files", text_color="#00FF00" if self.active_memories else "gray")
        self.refresh_memory_list()

    def clear_active_memory(self):
        self.active_memories = {}
        self.active_mem_lbl.configure(text="Active: 0 files", text_color="gray")
        self.refresh_memory_list()

    def setup_random_chat_tab(self):
        self.tab_random.grid_columnconfigure(0, weight=1)
        self.tab_random.grid_rowconfigure(0, weight=1)
        
        # Container for everything in the tab
        container = ctk.CTkFrame(self.tab_random, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Message List
        self.random_display = ctk.CTkTextbox(container, font=(MAIN_FONT, 13), spacing1=8, spacing3=8, fg_color="#111214", border_width=1, border_color="#2A2D30", corner_radius=12)
        self.random_display.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.configure_textbox_tags(self.random_display)
        self.random_display.configure(state="disabled")
        
        # Bottom Control Bar
        self.random_ctrl = ctk.CTkFrame(container, fg_color="#1A1C1E", height=80, corner_radius=12, border_width=1, border_color="#2A2D30")
        self.random_ctrl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.random_input = ctk.CTkEntry(self.random_ctrl, placeholder_text="Type your message...", font=(MAIN_FONT, 13), height=45, fg_color="#0D0F11", border_color="#3A3D40", corner_radius=8)
        self.random_input.pack(side="left", fill="x", expand=True, padx=(15, 10), pady=15)
        self.random_input.bind("<Return>", lambda e: self.send_generic_msg(self.random_input, self.random_display, "RANDOM"))
        
        ctk.CTkButton(self.random_ctrl, text="\ud83d\udccb COPY", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.copy_to_clipboard).pack(side="right", padx=5)
        ctk.CTkButton(self.random_ctrl, text="\ud83d\udcbe SAVE", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.save_session(self.random_display, "RANDOM")).pack(side="right", padx=5)
        ctk.CTkButton(self.random_ctrl, text="Clear", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.clear_chat(self.random_display, "RANDOM")).pack(side="right", padx=15)

    def setup_personal_chat_tab(self):
        self.tab_personal.grid_columnconfigure(0, weight=1)
        self.tab_personal.grid_rowconfigure(0, weight=1)
        
        container = ctk.CTkFrame(self.tab_personal, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.personal_display = ctk.CTkTextbox(container, font=(MAIN_FONT, 13), spacing1=8, spacing3=8, fg_color="#111214", border_width=1, border_color="#2A2D30", corner_radius=12)
        self.personal_display.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.configure_textbox_tags(self.personal_display)
        self.personal_display.configure(state="disabled")
        
        self.personal_ctrl = ctk.CTkFrame(container, fg_color="#1A1C1E", height=80, corner_radius=12, border_width=1, border_color="#2A2D30")
        self.personal_ctrl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.personal_input = ctk.CTkEntry(self.personal_ctrl, placeholder_text="Secret conversation here...", font=(MAIN_FONT, 13), height=45, fg_color="#0D0F11", border_color="#3A3D40", corner_radius=8)
        self.personal_input.pack(side="left", fill="x", expand=True, padx=(15, 10), pady=15)
        self.personal_input.bind("<Return>", lambda e: self.send_generic_msg(self.personal_input, self.personal_display, "PERSONAL"))
        
        ctk.CTkButton(self.personal_ctrl, text="\ud83d\udccb COPY", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.copy_to_clipboard).pack(side="right", padx=5)
        ctk.CTkButton(self.personal_ctrl, text="\ud83d\udcbe SAVE", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.save_session(self.personal_display, "PERSONAL")).pack(side="right", padx=5)
        ctk.CTkButton(self.personal_ctrl, text="Clear", font=(MAIN_FONT, 11), width=70, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.clear_chat(self.personal_display, "PERSONAL")).pack(side="right", padx=15)

    def setup_context_tab(self):
        self.tab_context.grid_columnconfigure(0, weight=1)
        self.tab_context.grid_rowconfigure(1, weight=1)
        
        self.context_top = ctk.CTkFrame(self.tab_context, fg_color="#1A1C1E", corner_radius=12, border_width=1, border_color="#2A2D30")
        self.context_top.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        
        ctk.CTkButton(self.context_top, text="Upload PDF/DOC", font=(MAIN_FONT, 12), height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.upload_context_file).pack(side="left", padx=(15, 5), pady=15)
        self.github_input = ctk.CTkEntry(self.context_top, placeholder_text="GitHub Project URL...", font=(MAIN_FONT, 13), height=36, fg_color="#0D0F11", border_color="#2A2D30", corner_radius=8)
        self.github_input.pack(side="left", fill="x", expand=True, padx=5, pady=15)
        ctk.CTkButton(self.context_top, text="Summarize", font=(MAIN_FONT, 11, "bold"), height=36, fg_color=ACCENT_COLOR, text_color="black", hover_color="#4FBBC8", command=self.summarize_context).pack(side="left", padx=5, pady=15)
        ctk.CTkButton(self.context_top, text="COPY", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.copy_to_clipboard).pack(side="left", padx=5, pady=15)
        ctk.CTkButton(self.context_top, text="SAVE", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.save_session(self.context_display, "CONTEXT")).pack(side="left", padx=5, pady=15)
        ctk.CTkButton(self.context_top, text="Clear", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.clear_chat(self.context_display, "CONTEXT")).pack(side="left", padx=15, pady=15)

        self.context_display = ctk.CTkTextbox(self.tab_context, font=(MAIN_FONT, 13), spacing1=8, spacing3=8, fg_color="#111214", border_width=1, border_color="#2A2D30", corner_radius=12)
        self.context_display.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="nsew")
        self.configure_textbox_tags(self.context_display)
        self.context_display.configure(state="disabled")

    def setup_diary_tab(self):
        self.tab_diary.grid_columnconfigure(0, weight=1)
        self.tab_diary.grid_rowconfigure(0, weight=1)
        
        container = ctk.CTkFrame(self.tab_diary, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        # Display area (History)
        self.diary_display = ctk.CTkTextbox(container, font=(MAIN_FONT, 14), spacing1=8, spacing3=8, fg_color="#111214", border_width=1, border_color="#2A2D30", corner_radius=12)
        self.diary_display.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.configure_textbox_tags(self.diary_display)
        self.diary_display.configure(state="disabled")
        
        # Controls Frame
        self.diary_ctrl = ctk.CTkFrame(container, fg_color="#1A1C1E", height=120, corner_radius=12, border_width=1, border_color="#2A2D30")
        self.diary_ctrl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        # Input area (Large text area for deep conversation)
        self.diary_input = ctk.CTkTextbox(self.diary_ctrl, height=100, font=(MAIN_FONT, 13), fg_color="#0D0F11", border_color="#2A2D30", corner_radius=8)
        self.diary_input.pack(side="left", fill="x", expand=True, padx=(15, 10), pady=15)
        self.diary_input.bind("<Control-Return>", lambda e: self.send_generic_msg(self.diary_input, self.diary_display, "DIARY"))

        # Buttons Panel
        btn_panel = ctk.CTkFrame(self.diary_ctrl, fg_color="transparent")
        btn_panel.pack(side="right", padx=15, pady=15)

        ctk.CTkButton(btn_panel, text="SEND", font=(MAIN_FONT, 11, "bold"), width=80, height=36, fg_color=ACCENT_COLOR, text_color="black", hover_color="#4FBBC8", command=lambda: self.send_generic_msg(self.diary_input, self.diary_display, "DIARY")).pack(pady=5)
        ctk.CTkButton(btn_panel, text="COPY", font=(MAIN_FONT, 11), width=80, height=32, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.copy_to_clipboard).pack(pady=5)
        ctk.CTkButton(btn_panel, text="SAVE", font=(MAIN_FONT, 11), width=80, height=32, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.save_diary).pack(pady=5)
        ctk.CTkButton(btn_panel, text="Clear", font=(MAIN_FONT, 11), width=80, height=32, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.clear_chat(self.diary_display, "DIARY")).pack(pady=5)

    def setup_coder_tab(self):
        self.tab_coder.grid_columnconfigure(0, weight=1)
        self.tab_coder.grid_rowconfigure(0, weight=1)
        
        container = ctk.CTkFrame(self.tab_coder, fg_color="transparent")
        container.grid(row=0, column=0, sticky="nsew")
        container.grid_columnconfigure(0, weight=1)
        container.grid_rowconfigure(0, weight=1)

        self.coder_display = ctk.CTkTextbox(container, font=(MAIN_FONT, 13), spacing1=8, spacing3=8, fg_color="#0D0F11", border_width=1, border_color="#2A2D30", corner_radius=12)
        self.coder_display.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.configure_textbox_tags(self.coder_display)
        self.coder_display.configure(state="disabled")
        
        self.coder_ctrl = ctk.CTkFrame(container, fg_color="#1A1C1E", height=80, corner_radius=12, border_width=1, border_color="#2A2D30")
        self.coder_ctrl.grid(row=1, column=0, padx=10, pady=(0, 10), sticky="ew")
        
        self.coder_input = ctk.CTkEntry(self.coder_ctrl, placeholder_text="Ask for code or describe a bug...", font=(MAIN_FONT, 13), height=45, fg_color="#0D0F11", border_color="#2A2D30", corner_radius=8)
        self.coder_input.pack(side="left", fill="x", expand=True, padx=(15, 10), pady=15)
        self.coder_input.bind("<Return>", lambda e: self.send_generic_msg(self.coder_input, self.coder_display, "CODER"))
        
        ctk.CTkButton(self.coder_ctrl, text="LOAD FILE", font=(MAIN_FONT, 11), width=90, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.load_file_to_chat).pack(side="left", padx=5)
        ctk.CTkButton(self.coder_ctrl, text="COPY", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=self.copy_to_clipboard).pack(side="right", padx=5)
        ctk.CTkButton(self.coder_ctrl, text="SAVE", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.save_session(self.coder_display, "CODER")).pack(side="right", padx=5)
        ctk.CTkButton(self.coder_ctrl, text="Clear", font=(MAIN_FONT, 11), width=80, height=36, fg_color="#222426", hover_color="#303336", border_width=1, border_color="#2A2D30", command=lambda: self.clear_chat(self.coder_display, "CODER")).pack(side="right", padx=15)

    def clear_chat(self, textbox, role=None):
        textbox.configure(state="normal")
        textbox.delete("1.0", "end")
        textbox.configure(state="disabled")
        if role and role in self.chat_history:
            self.chat_history[role] = []

    def configure_textbox_tags(self, textbox):
        try:
            tk_text = textbox._textbox
            tk_text.tag_config("role_user", foreground=ACCENT_COLOR, font=(MAIN_FONT, 12, "bold"))
            tk_text.tag_config("role_ai", foreground="#10B981", font=(MAIN_FONT, 12, "bold"))
            tk_text.tag_config("system", foreground="#6B7280", font=(MAIN_FONT, 11, "italic"))
            tk_text.tag_config("bold", font=(MAIN_FONT, 12, "bold"))
            # Distinction: slightly lighter background for code blocks so they are visible
            tk_text.tag_config("code_block", background="#050607", foreground="#CED4DA", font=(MAIN_FONT, 11), spacing1=10, spacing3=10, lmargin1=30, lmargin2=30, rmargin=30)
        except Exception:
            pass
        except Exception:
            textbox.tag_config("role_user", foreground=ACCENT_COLOR)
            textbox.tag_config("role_ai", foreground="#10B981")
            textbox.tag_config("system", foreground="#6B7280")
            textbox.tag_config("bold", underline=True)
            textbox.tag_config("code_block", background="#0D0F11")
        
        # Keep track of formatting state for this specific textbox
        textbox.is_bold = False
        textbox.is_code = False
        textbox.markdown_buffer = ""
        textbox.code_blocks = [] # List of strings containing code
        textbox.current_code_idx = -1

    def create_code_header(self, textbox, lang="Code"):
        """Inserts a header frame for code blocks with a copy button."""
        # Clean language name
        display_lang = lang.strip().upper() if lang.strip() else "CODE"
        
        # Header Frame - slightly lighter than the text box bg
        header_frame = ctk.CTkFrame(textbox, fg_color="#222426", height=34, corner_radius=6, border_width=1, border_color="#2A2D30")
        header_frame.pack_propagate(False)
        
        lbl = ctk.CTkLabel(header_frame, text=f" \u25cf {display_lang}", font=(MAIN_FONT, 10, "bold"), text_color=ACCENT_COLOR)
        lbl.pack(side="left", padx=15)
        
        idx = len(textbox.code_blocks)
        textbox.code_blocks.append("")
        textbox.current_code_idx = idx
        
        btn = ctk.CTkButton(
            header_frame, 
            text="COPY CODE", 
            font=(MAIN_FONT, 10), 
            width=85, 
            height=24, 
            fg_color="#1A1C1E",
            hover_color="#2A2D30",
            border_width=1,
            border_color="#3A3D40",
            command=lambda i=idx, t=textbox: self.copy_specific_code(t, i)
        )
        btn.pack(side="right", padx=10)
        
        textbox._textbox.configure(state="normal")
        # Add some space before the header
        textbox._textbox.insert("end", "\n")
        
        textbox._textbox.window_create("end", window=header_frame)
        textbox._textbox.insert("end", "\n")
        textbox._textbox.configure(state="disabled")

    def copy_specific_code(self, textbox, index):
        if 0 <= index < len(textbox.code_blocks):
            code = textbox.code_blocks[index].strip()
            if code:
                try:
                    import pyperclip
                    pyperclip.copy(code)
                except:
                    # Fallback
                    self.clipboard_clear()
                    self.clipboard_append(code)

    def start_model_load_thread(self, model_name):
        self.status_lbl.configure(text="Status: LOADING...", text_color="orange")
        threading.Thread(target=self.load_model_task, args=(model_name,), daemon=True).start()

    def load_model_task(self, model_name):
        res = self.backend.load_model(model_name)
        self.after(0, lambda: self.status_lbl.configure(text=f"Status: ONLINE", text_color="#00FF00"))

    def send_generic_msg(self, input_widget, display_widget, role):
        if self.is_generating: return
        
        # Determine if input_widget is CTkTextbox or CTkEntry
        if isinstance(input_widget, ctk.CTkTextbox):
            text = input_widget.get("1.0", "end-1c")
        else:
            text = input_widget.get()

        if not text.strip(): return
        
        if isinstance(input_widget, ctk.CTkTextbox):
            input_widget.delete("1.0", "end")
        else:
            input_widget.delete(0, "end")

        self.current_textarea = display_widget
        
        # Determine system prompt based on role
        sys_prompt = "You are a helpful assistant."
        if role == "PERSONAL":
            sys_prompt = "You are a private, personal assistant. Maintain confidentiality."
        elif role == "DIARY":
            sys_prompt = "You are an AI diary companion. Listen and reflect."
        elif role == "CODER":
            sys_prompt = "You are an expert software engineer. Provide high quality code."
        elif role == "CONTEXT":
            sys_prompt = "You are a context analysis assistant. Summarize provided documents accurately."

        self.prepare_generation(text, role)
        web_access = self.web_access_var.get()
        threading.Thread(target=self.generate_task, args=(text, sys_prompt, web_access, role), daemon=True).start()

    def upload_context_file(self):
        filepath = filedialog.askopenfilename(filetypes=[("Documents", "*.pdf *.docx *.txt")])
        if filepath:
            self.context_display.configure(state="normal")
            self.context_display.insert("end", f"\n[SYSTEM]: Loaded {os.path.basename(filepath)}. Click Summarize to process.\n")
            self.context_display.see("end")
            self.context_display.configure(state="disabled")
            self.pending_context_file = filepath

    def summarize_context(self):
        github_link = self.github_input.get()
        extracted_text = ""
        
        if github_link:
            try:
                response = requests.get(github_link)
                soup = BeautifulSoup(response.text, 'html.parser')
                extracted_text = soup.get_text()[:4000] # Limit to 4k chars for summary
                prompt = f"Summarize the content of this GitHub repository: {github_link}\n\nContent:\n{extracted_text}"
            except Exception as e:
                self.after(0, self.append_token, f"\n[ERROR FETCHING GITHUB]: {e}")
                return
        elif hasattr(self, 'pending_context_file') and self.pending_context_file:
            try:
                if self.pending_context_file.endswith(".pdf"):
                    reader = PdfReader(self.pending_context_file)
                    for page in reader.pages:
                        extracted_text += page.extract_text() + "\n"
                elif self.pending_context_file.endswith(".docx"):
                    doc = Document(self.pending_context_file)
                    for para in doc.paragraphs:
                        extracted_text += para.text + "\n"
                elif self.pending_context_file.endswith(".txt"):
                    with open(self.pending_context_file, "r", encoding="utf-8") as f:
                        extracted_text = f.read()
                
                # Sanitize text: Remove non-printable characters that can crash llama.cpp
                extracted_text = "".join(c for c in extracted_text if c.isprintable() or c in "\n\r\t")
                extracted_text = extracted_text[:3000] # Slightly smaller chunk to ensure buffer
                prompt = f"Summarize the content of the uploaded file: {os.path.basename(self.pending_context_file)}\n\nContent:\n{extracted_text}"
            except Exception as e:
                self.after(0, self.append_token, f"\n[ERROR READING FILE]: {e}")
                return
        else:
            return

        self.current_textarea = self.context_display
        self.prepare_generation(prompt, "CONTEXT")
        sys_prompt = "You are a context analysis assistant. Summarize provided documents accurately."
        web_access = self.web_access_var.get()
        threading.Thread(target=self.generate_task, args=(prompt, sys_prompt, web_access, "CONTEXT"), daemon=True).start()

    def prepare_generation(self, text, role):
        self.is_generating = True
        self.stop_btn.configure(state="normal")
        self.current_textarea.configure(state="normal")
        
        # Reset formatting states
        self.current_textarea.is_bold = False
        self.current_textarea.is_code = False
        self.current_textarea.markdown_buffer = ""

        timestamp = datetime.datetime.now().strftime("%H:%M %p")
        model_display = self.backend.current_model_name or "Unknown Model"
        
        self.current_textarea.insert("end", f"\u25cf You\n", "role_user")
        self.current_textarea.insert("end", f"{text}\n", "text")
        self.current_textarea.insert("end", f"{timestamp}\n\n", "system")
        
        self.current_textarea.insert("end", f"\u25cf {model_display}\n", "role_ai")
        
        self.current_textarea.see("end")
        self.current_textarea.configure(state="disabled")

    def generate_task(self, prompt, sys_prompt=None, web_access=False, role="RANDOM"):
        self.current_role = role
        self.current_user_prompt = prompt
        self.current_ai_response = ""
        
        # Inject Active Memories into the prompt if any
        if self.active_memories:
            memory_context = "\n--- START OF LOADED MEMORY CONTEXT ---\n"
            for path, content in self.active_memories.items():
                memory_context += f"FILE: {os.path.basename(path)}\nCONTENT:\n{content}\n"
            memory_context += "--- END OF LOADED MEMORY CONTEXT ---\n"
            
            prompt = f"REFERENCE CONTEXT FROM PREVIOUS SESSIONS:\n{memory_context}\n\nUSER REQUEST: {prompt}"

        # History is now always enabled for these roles
        history = self.chat_history.get(role)

        try:
            for token in self.backend.generate_response(prompt, system_prompt=sys_prompt, web_access=web_access, history=history):
                if not self.is_generating:
                    self.after(0, self.append_token, "\n[INTERRUPTED]")
                    break
                self.after(0, self.append_token, token)
                self.current_ai_response += token
        except Exception as e:
            self.after(0, self.append_token, f"\n[ERROR]: {e}")
        finally:
            self.after(0, self.finalize_generation)

    def append_token(self, token):
        self.current_textarea.configure(state="normal")
        self.current_textarea.markdown_buffer += token
        
        # Determine current tag
        def get_tag():
            if self.current_textarea.is_code: return "code_block"
            if self.current_textarea.is_bold: return "bold"
            return None

        # Process markers
        while True:
            # Find earliest marker (backticks or triple single quotes)
            pos_bold = self.current_textarea.markdown_buffer.find("**")
            # Support both backticks and triple quotes as some models confuse them
            pos_code_back = self.current_textarea.markdown_buffer.find("```")
            pos_code_quote = self.current_textarea.markdown_buffer.find("'''")
            
            # Use the earliest code marker
            pos_code = -1
            if pos_code_back != -1 and pos_code_quote != -1:
                pos_code = min(pos_code_back, pos_code_quote)
            elif pos_code_back != -1: pos_code = pos_code_back
            elif pos_code_quote != -1: pos_code = pos_code_quote

            # No markers at all?
            if pos_bold == -1 and pos_code == -1:
                break
            
            # Case 1: BOLD is first
            if (pos_bold != -1) and (pos_code == -1 or pos_bold < pos_code):
                text_before = self.current_textarea.markdown_buffer[:pos_bold]
                self.current_textarea.insert("end", text_before, get_tag())
                if self.current_textarea.is_code:
                    self.current_textarea.code_blocks[self.current_textarea.current_code_idx] += text_before
                
                self.current_textarea.is_bold = not self.current_textarea.is_bold
                self.current_textarea.markdown_buffer = self.current_textarea.markdown_buffer[pos_bold + 2:]
                
            # Case 2: CODE is first
            elif pos_code != -1:
                text_before = self.current_textarea.markdown_buffer[:pos_code]
                self.current_textarea.insert("end", text_before, get_tag())
                if self.current_textarea.is_code:
                    self.current_textarea.code_blocks[self.current_textarea.current_code_idx] += text_before
                
                # Marker found. Now consume it.
                # Check if we are STARTING or ENDING
                if not self.current_textarea.is_code:
                    # Look for end of the language line
                    remaining = self.current_textarea.markdown_buffer[pos_code + 3:]
                    if "\n" in remaining:
                        newline_pos = remaining.find("\n")
                        lang = remaining[:newline_pos].strip() or "Code"
                        self.create_code_header(self.current_textarea, lang)
                        self.current_textarea.is_code = True
                        self.current_textarea.markdown_buffer = remaining[newline_pos + 1:]
                    else:
                        # We found ``` but no newline yet. 
                        # To prevent premature flushing, we must KEEP the marker in the buffer.
                        # We stop processing this buffer and wait for more tokens.
                        break
                else:
                    # ENDING code block
                    self.current_textarea.is_code = False
                    self.current_textarea.markdown_buffer = self.current_textarea.markdown_buffer[pos_code + 3:]

        # Flush SAFE content (anything before the start of a potential marker)
        buf = self.current_textarea.markdown_buffer
        # Find index of any potential marker start
        idx_b = buf.find("**")
        idx_c = buf.find("```")
        idx_q = buf.find("'''")
        
        indices = [i for i in [idx_b, idx_c, idx_q] if i != -1]
        if not indices:
            # Check for partials at the very end
            safe_idx = len(buf)
            if buf.endswith("*"): safe_idx -= 1
            if buf.endswith("`") or buf.endswith("'"):
                # Could be part of ``` or ''', find how many
                count = 0
                for char in reversed(buf):
                    if char in ["`", "'"]: count += 1
                    else: break
                safe_idx = len(buf) - min(count, 3) # Keep up to 3 markers
            
            safe_text = buf[:safe_idx]
            if safe_text:
                self.current_textarea.insert("end", safe_text, get_tag())
                if self.current_textarea.is_code:
                    self.current_textarea.code_blocks[self.current_textarea.current_code_idx] += safe_text
                self.current_textarea.markdown_buffer = buf[safe_idx:]
        else:
            # We have a full marker being processed by the 'while' loop above, 
            # so we don't flush manually here; it should be handled there.
            pass

        self.current_textarea.see("end")
        self.current_textarea.configure(state="disabled")

    def finalize_generation(self):
        # Flush remaining buffer
        self.current_textarea.configure(state="normal")
        if hasattr(self, 'current_textarea') and self.current_textarea.markdown_buffer:
            tag = "code_block" if self.current_textarea.is_code else ("bold" if self.current_textarea.is_bold else None)
            self.current_textarea.insert("end", self.current_textarea.markdown_buffer, tag)
            if self.current_textarea.is_code:
                self.current_textarea.code_blocks[self.current_textarea.current_code_idx] += self.current_textarea.markdown_buffer
            self.current_textarea.markdown_buffer = ""
        
        # Auto-close code blocks if left open by model
        if self.current_textarea.is_code:
            self.current_textarea.is_code = False
            
        # Ending timestamp and footer
        self.current_textarea.insert("end", "\n\u25b6\n", "system")
        timestamp = datetime.datetime.now().strftime("%H:%M %p")
        self.current_textarea.insert("end", f"{timestamp}\n\n", "system")
        
        self.current_textarea.see("end")
        self.current_textarea.configure(state="disabled")
        
        self.is_generating = False
        self.stop_btn.configure(state="disabled")
        if hasattr(self, 'current_role') and self.current_role in self.chat_history:
            self.chat_history[self.current_role].append({"role": "user", "content": self.current_user_prompt})
            self.chat_history[self.current_role].append({"role": "assistant", "content": self.current_ai_response})
            # Trim history to last 10 turns to save context space
            if len(self.chat_history[self.current_role]) > 20:
                self.chat_history[self.current_role] = self.chat_history[self.current_role][-20:]

    def stop_generation(self):
        self.is_generating = False

    def toggle_vpn(self):
        if self.vpn_var.get():
            self.vpn_status_lbl.configure(text="Connection: CONNECTING...", text_color="orange")
            threading.Thread(target=self._run_vpn_cmd, args=(["rasdial", "hide.me"], True), daemon=True).start()
        else:
            self.vpn_status_lbl.configure(text="Connection: DISCONNECTING...", text_color="orange")
            threading.Thread(target=self._run_vpn_cmd, args=(["rasdial", "hide.me", "/disconnect"], False), daemon=True).start()

    def _run_vpn_cmd(self, cmd, connecting):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 0:
                if connecting:
                    self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: SECURED", text_color="#10B981"))
                else:
                    self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: EXPOSED", text_color="#EF4444"))
            else:
                self.after(0, lambda: messagebox.showerror("VPN Error", f"Command failed: {res.stderr or res.stdout}"))
                self.after(0, lambda: self.vpn_var.set(not connecting)) # Revert switch
                if connecting:
                    self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: EXPOSED", text_color="#EF4444"))
                else:
                    self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: SECURED", text_color="#10B981"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("VPN Error", f"Failed to execute VPN command: {e}"))
            self.after(0, lambda: self.vpn_var.set(not connecting))
            if connecting:
                self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: EXPOSED", text_color="#EF4444"))
            else:
                self.after(0, lambda: self.vpn_status_lbl.configure(text="Connection: SECURED", text_color="#10B981"))

    def save_session(self, textbox, role):
        log_dir = os.path.join(self.base_dir, f"{role.lower()}_logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        date_str = datetime.datetime.now().strftime("%Y-%m-%d")
        filename = f"{role.capitalize()}_{date_str}.txt"
        filepath = os.path.join(log_dir, filename)
        
        try:
            content = textbox.get("1.0", "end-1c")
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            
            # Update sidebar list
            self.refresh_memory_list()
            
            messagebox.showinfo("Session Saved", f"Saved to {filepath}")
        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save {role} session: {e}")

    def copy_to_clipboard(self, content=None):
        if not HAS_PYPERCLIP:
            messagebox.showwarning("Clipboard Error", "pyperclip is not installed. Please try: pip install pyperclip")
            return
        
        target = content or self.current_ai_response
        if target:
            pyperclip.copy(target)
            # Find the active tab to show a tiny feedback label if we had one, 
            # but for now a messagebox or just silent success is enough as per CTK standards.
        else:
            messagebox.showinfo("Clipboard", "Nothing to copy yet.")

    def save_diary(self):
        self.save_session(self.diary_display, "DIARY")

    def load_file_to_chat(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            with open(filepath, "r", encoding="utf-8") as f:
                self.coder_input.insert(0, f"Review: {f.read()[:500]}...")

if __name__ == "__main__":
    app = RoaApp()
    app.mainloop()
