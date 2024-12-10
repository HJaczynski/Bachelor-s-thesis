import customtkinter as ctk

class WelcomeTab(ctk.CTkFrame):
    def __init__(self, parent, tab_view):
        super().__init__(parent)
        self.tab_view = tab_view

        # Welcome title
        welcome_title = ctk.CTkLabel(self, text="Welcome to Football Analytics!", font=("Calibri", 64, "bold"), text_color='white')
        welcome_title.grid(row=0, column=0, columnspan=2, sticky="")

        # Video Analysis Box with Title (First column)
        video_analysis_title = ctk.CTkLabel(self, text="Video Analysis Usage", font=("Calibri", 36, "bold"), text_color='white')
        video_analysis_title.grid(row=1, column=0, padx=10, sticky="")

        # Player Dashboard Box with Title (Second column)
        player_dashboard_title = ctk.CTkLabel(self, text="Player Dashboard Usage", font=("Calibri", 36, "bold"), text_color='white')
        player_dashboard_title.grid(row=1, column=1, padx=10, sticky="")

        video_analysis_steps = [
            "\nStep 1: Upload Match Video\n   Upload the video of the match you want to analyze.  \n",
            "Step 2: Press Analyze Video\n   Wait for the analysis to finish.  \n",
            "Step 3: Select Pre-Loaded Video\n   View already analyzed video from existing database.  \n",
            "Step 4: Analyze Key Moments\n   Identify and analyze critical moments of the match.  \n"
        ]
        
        player_dashboard_steps = [
            "\nStep 1: Choose a Player\n   Select a player from the available list.  \n",
            "Step 2: View Performance Data\n   See the detailed information about the player.  \n",
            "Step 3: Filter by Club,   League, etc\n Choose specific club or league to look for players.  \n",
            "Step 4: View Statistics\n   Choose the desired statistic and view the displayed graph.  \n",
            "Step 5: Download Statistics\n   Press the button to save statistics in various formats.(CSV,JPG)  \n"
        ]

        video_analysis_steps_text = "\n".join(video_analysis_steps)
        player_dashboard_steps_text = "\n".join(player_dashboard_steps)
        
        video_analysis_tab_widget = ctk.CTkFrame(self, fg_color="white")
        video_analysis_tab_widget.grid(row=2, column=0, padx=5, sticky="n")

        video_analysis_text_label = ctk.CTkLabel(video_analysis_tab_widget, text=video_analysis_steps_text, font=("Calibri", 18, "bold"), text_color="black")
        video_analysis_text_label.grid(row=0, column=0, padx=5, sticky="")
        
        video_analysis_tab_button = ctk.CTkButton(self, text="Analyze Video", font=("Calibri", 18, "bold"), text_color="white", width=200, command=lambda: self.tab_view.set("Video Analysis"))
        video_analysis_tab_button.grid(row=3, column=0, padx=5, sticky="n")

        player_dashboard_tab_widget = ctk.CTkFrame(self, fg_color="white")
        player_dashboard_tab_widget.grid(row=2, column=1, padx=5, sticky="n")
        
        player_dashboard_text_label = ctk.CTkLabel(player_dashboard_tab_widget, text=player_dashboard_steps_text, font=("Calibri", 18, "bold"), text_color="black")
        player_dashboard_text_label.grid(row=0, column=0, padx=5, sticky="")

        player_dashboard_tab_button = ctk.CTkButton(self, text="View Players", font=("Calibri", 18, "bold"), text_color="white", width=200, command=lambda: self.tab_view.set("Player Dashboard"))
        player_dashboard_tab_button.grid(row=3, column=1, padx=5, sticky="n")
        
        # Configure the grid to ensure proper row and column weight distribution
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_rowconfigure(3, weight=1)
