import pytest
import customtkinter as ctk
from WelcomeTab import WelcomeTab

@pytest.fixture
def welcome_tab_instance():
    """Fixture to create a WelcomeTab instance for testing."""
    root = ctk.CTk()  
    tab_view = ctk.CTkTabview(root)
    tab_view.add("Welcome")  
    tab_view.add("Video Analysis")
    tab_view.add("Player Dashboard")
    welcome_tab = WelcomeTab(tab_view.tab("Welcome"), tab_view=tab_view)
    
    root.update_idletasks()
    yield welcome_tab
    root.destroy()

def test_welcome_tab_initialization(welcome_tab_instance):
    """Test that the WelcomeTab initializes without errors."""
    assert isinstance(welcome_tab_instance, ctk.CTkFrame)

def test_welcome_title_label(welcome_tab_instance):
    """Test that the welcome title label is created and has correct text."""
    children = welcome_tab_instance.winfo_children()
    title_label = None
    for child in children:
        if isinstance(child, ctk.CTkLabel) and "Welcome to Football Analytics!" in child.cget("text"):
            title_label = child
            break
    assert title_label is not None
    assert title_label.cget("text") == "Welcome to Football Analytics!"

def test_video_analysis_title_label(welcome_tab_instance):
    """Test that the Video Analysis usage title label is created."""
    children = welcome_tab_instance.winfo_children()
    va_title_label = None
    for child in children:
        if isinstance(child, ctk.CTkLabel) and "Video Analysis Usage" in child.cget("text"):
            va_title_label = child
            break
    assert va_title_label is not None
    assert va_title_label.cget("text") == "Video Analysis Usage"

def test_player_dashboard_title_label(welcome_tab_instance):
    """Test that the Player Dashboard usage title label is created."""
    children = welcome_tab_instance.winfo_children()
    pd_title_label = None
    for child in children:
        if isinstance(child, ctk.CTkLabel) and "Player Dashboard Usage" in child.cget("text"):
            pd_title_label = child
            break
    assert pd_title_label is not None
    assert pd_title_label.cget("text") == "Player Dashboard Usage"

def test_video_analysis_steps(welcome_tab_instance):
    """Test that the video analysis steps frame and label are created."""
    children = welcome_tab_instance.winfo_children()
    va_frame = None
    for child in children:
        if isinstance(child, ctk.CTkFrame) and child != welcome_tab_instance:
            labels = [c for c in child.winfo_children() if isinstance(c, ctk.CTkLabel)]
            for lbl in labels:
                if "Upload Match Video" in lbl.cget("text"):
                    va_frame = child
                    break
            if va_frame:
                break
    assert va_frame is not None, "Video Analysis steps frame not found."

def test_player_dashboard_steps(welcome_tab_instance):
    """Test that the player dashboard steps frame and label are created."""
    children = welcome_tab_instance.winfo_children()
    pd_frame = None
    for child in children:
        if isinstance(child, ctk.CTkFrame) and child != welcome_tab_instance:
            labels = [c for c in child.winfo_children() if isinstance(c, ctk.CTkLabel)]
            for lbl in labels:
                if "Choose a Player" in lbl.cget("text"):
                    pd_frame = child
                    break
            if pd_frame:
                break
    assert pd_frame is not None, "Player Dashboard steps frame not found."

def test_buttons_exist_and_function(welcome_tab_instance):
    """Test that the Analyze Video and View Players buttons are created."""
    children = welcome_tab_instance.winfo_children()
    analyze_button = None
    view_players_button = None
    for child in children:
        if isinstance(child, ctk.CTkButton):
            if child.cget("text") == "Analyze Video":
                analyze_button = child
            elif child.cget("text") == "View Players":
                view_players_button = child

    assert analyze_button is not None, "Analyze Video button not found."
    assert view_players_button is not None, "View Players button not found."

    analyze_button.invoke()
    view_players_button.invoke()
