import customtkinter as ctk
import threading
from core.controller import Controller
from gui.dashboard import Dashboard

class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("OpenClaw Alternative (Ollama + CLI)")
        self.geometry("900x650")
        self.configure(fg_color=("#e0e0e0", "#121212"))
        
        self.controller = Controller()
        self.dashboard_window = None
        
        self._setup_ui()
        
    def _setup_ui(self):
        # Top Bar
        self.top_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        self.top_frame.pack(fill="x", side="top")
        
        self.title_label = ctk.CTkLabel(self.top_frame, text="AI Assistant", font=ctk.CTkFont(size=18, weight="bold"))
        self.title_label.pack(side="left", padx=20, pady=10)
        
        self.stats_btn = ctk.CTkButton(self.top_frame, text="Dashboard", width=100, command=self.open_dashboard)
        self.stats_btn.pack(side="right", padx=10, pady=10)
        
        # Left Sidebar (Settings)
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.pack(fill="y", side="left", padx=(0, 10))
        self.sidebar.pack_propagate(False)
        
        self.mode_label = ctk.CTkLabel(self.sidebar, text="Model Mode:", font=ctk.CTkFont(weight="bold"))
        self.mode_label.pack(pady=(20, 5), padx=10, anchor="w")
        
        self.mode_switch = ctk.CTkSwitch(self.sidebar, text="Pro Mode (CLI)", command=self.toggle_mode)
        self.mode_switch.pack(pady=5, padx=10, anchor="w")
        
        self.exp_scraper_switch = ctk.CTkSwitch(self.sidebar, text="Exp. Scraper Mode")
        self.exp_scraper_switch.pack(pady=5, padx=10, anchor="w")
        
        self.tools_label = ctk.CTkLabel(self.sidebar, text="Tools:", font=ctk.CTkFont(weight="bold"))
        self.tools_label.pack(pady=(20, 5), padx=10, anchor="w")
        
        self.collab_switch = ctk.CTkSwitch(self.sidebar, text="Collab Consensus")
        self.collab_switch.pack(pady=5, padx=10, anchor="w")
        
        self.dc_switch = ctk.CTkSwitch(self.sidebar, text="Double Check")
        self.dc_switch.pack(pady=5, padx=10, anchor="w")
        
        # Main Chat Area
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.pack(fill="both", expand=True, side="right", padx=10, pady=10)
        
        self.history_box = ctk.CTkTextbox(self.chat_frame, wrap="word", font=ctk.CTkFont(size=14))
        self.history_box.pack(fill="both", expand=True, pady=(0, 10))
        self.history_box.configure(state="disabled")
        
        self.status_label = ctk.CTkLabel(self.chat_frame, text="", text_color="gray")
        self.status_label.pack(side="bottom", anchor="w", pady=(0, 5))
        
        self.input_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        self.input_frame.pack(fill="x", side="bottom")
        
        self.input_box = ctk.CTkEntry(self.input_frame, placeholder_text="Type your prompt here...")
        self.input_box.pack(fill="x", side="left", expand=True, padx=(0, 10))
        self.input_box.bind("<Return>", lambda e: self.send_prompt())
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="Send", width=80, command=self.send_prompt)
        self.send_btn.pack(side="right")
        
        # Initial Toggle State
        self.toggle_mode()
        
    def toggle_mode(self):
        is_pro = self.mode_switch.get()
        if is_pro:
            self.collab_switch.deselect()
            self.collab_switch.configure(state="disabled")
            self.exp_scraper_switch.deselect()
            self.exp_scraper_switch.configure(state="disabled")
        else:
            self.collab_switch.configure(state="normal")
            self.exp_scraper_switch.configure(state="normal")
            
    def open_dashboard(self):
        if self.dashboard_window is None or not self.dashboard_window.winfo_exists():
            self.dashboard_window = Dashboard(self)
        else:
            self.dashboard_window.focus()
            
    def _append_to_chat(self, text: str):
        self.history_box.configure(state="normal")
        self.history_box.insert("end", text + "\n\n")
        self.history_box.see("end")
        self.history_box.configure(state="disabled")

    def send_prompt(self):
        prompt = self.input_box.get()
        if not prompt.strip():
            return
            
        self.input_box.delete(0, "end")
        self._append_to_chat(f"You:\n{prompt}")
        self.send_btn.configure(state="disabled")
        
        mode = "pro" if self.mode_switch.get() else "free"
        use_dc = bool(self.dc_switch.get())
        use_collab = bool(self.collab_switch.get())
        use_exp_scraper = bool(self.exp_scraper_switch.get())
        
        self.status_label.configure(text="Generating response... Please wait." if not use_collab else "Collab Mode active. Gathering multi-model consensus...")
        
        # Run in thread to prevent UI freezing
        threading.Thread(target=self._generate_worker, args=(prompt, mode, use_dc, use_collab, use_exp_scraper), daemon=True).start()
        
    def _generate_worker(self, prompt, mode, use_dc, use_collab, use_exp_scraper):
        try:
            response = self.controller.generate_response(
                prompt=prompt, 
                mode=mode, 
                use_double_check=use_dc,
                use_collab=use_collab,
                use_experimental_scraper=use_exp_scraper
            )
            self._append_to_chat(f"Assistant:\n{response}")
        except Exception as e:
            self._append_to_chat(f"Assistant [Error]:\n{str(e)}")
        finally:
            self.send_btn.configure(state="normal")
            self.status_label.configure(text="")
