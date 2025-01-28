import customtkinter as ctk
from VideoAnalysisTab import VideoAnalysisTab
from PlayerDashboardTab import PlayerDashboardTab
from WelcomeTab import WelcomeTab
#from WelcomeTabNew import WelcomeTab

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        # App configuration
        self.title("Goalytics")
        self.iconbitmap('Images/app.ico')
        self.geometry("1366x768")
        self.resizable(False, False)

        # Tab view
        self.tab_view = ctk.CTkTabview(self)
        self.tab_view.pack(expand=True, fill="both", padx=5, pady=5)

        # Add tabs
        welcome_tab = self.tab_view.add("Welcome")
        video_analysis_tab = self.tab_view.add("Video Analysis")
        player_dashboard_tab = self.tab_view.add("Player Dashboard")

        # Attach custom tabs
        WelcomeTab(welcome_tab, self.tab_view).pack(expand=True, fill="both")
        VideoAnalysisTab(video_analysis_tab).pack(expand=True, fill="both")
        PlayerDashboardTab(player_dashboard_tab).pack(expand=True, fill="both")