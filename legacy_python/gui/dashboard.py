import customtkinter as ctk
from core.stats_monitor import stats_monitor

class Dashboard(ctk.CTkToplevel):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.title("Stats Dashboard")
        self.geometry("300x350")
        self.attributes("-topmost", True)
        self.resizable(False, False)
        
        # Make it look modern
        self.configure(fg_color=("#f0f0f0", "#1a1a1a"))
        
        self.title_label = ctk.CTkLabel(self, text="Usage Statistics", font=ctk.CTkFont(size=20, weight="bold"))
        self.title_label.pack(pady=(20, 10))
        
        self.stats_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.stats_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.labels = {}
        
        self._init_labels()
        self.update_stats()
        
    def _init_labels(self):
        stats = stats_monitor.get_stats()
        for i, (key, value) in enumerate(stats.items()):
            label_title = ctk.CTkLabel(self.stats_frame, text=f"{key}:", font=ctk.CTkFont(size=14, weight="bold"))
            label_title.grid(row=i, column=0, sticky="w", pady=5)
            
            label_val = ctk.CTkLabel(self.stats_frame, text=str(value), font=ctk.CTkFont(size=14))
            label_val.grid(row=i, column=1, sticky="e", padx=20, pady=5)
            
            self.labels[key] = label_val
            
    def update_stats(self):
        stats = stats_monitor.get_stats()
        for key, value in stats.items():
            if key in self.labels:
                self.labels[key].configure(text=str(value))
        
        # Auto refresh every 2 seconds
        self.after(2000, self.update_stats)
