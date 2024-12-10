import pytest
import customtkinter as ctk
from App import App

@pytest.fixture
def app_instance():
    """Fixture to initialize the app for testing."""
    app = App()
    yield app
    app.destroy()

def test_app_initialization(app_instance: App):
    """Test that the app initializes correctly."""
    assert app_instance.title() == "Football Analytics"
    dimensions = app_instance.geometry().split("+")[0]  # Extract dimensions without position
    assert dimensions == "1366x768"
    assert app_instance.resizable() == (False, False)

def test_tab_view_created(app_instance: App):
    """Test that the tab view is created."""
    assert isinstance(app_instance.tab_view, ctk.CTkTabview)

def test_tabs_exist(app_instance: App):
    """Test that the tabs exist in the tab view."""
    tab_names = ["Welcome", "Video Analysis", "Player Dashboard"]
    for tab_name in tab_names:
        assert app_instance.tab_view.tab(tab_name) is not None

def test_set_tab(app_instance: App):
    """Test that tabs can be selected correctly."""
    tab_names = ["Welcome", "Video Analysis", "Player Dashboard"]
    for tab_name in tab_names:
        app_instance.tab_view.set(tab_name)
        assert app_instance.tab_view.get() == tab_name

def test_tabs_contain_widgets(app_instance: App):
    """Test that each tab contains widgets."""
    tab_names = ["Welcome", "Video Analysis", "Player Dashboard"]
    for tab_name in tab_names:
        tab_frame = app_instance.tab_view.tab(tab_name)
        assert len(tab_frame.winfo_children()) > 0  # Ensure the tab has child widgets
