import pytest
import customtkinter as ctk
from unittest.mock import patch
from VideoAnalysisTab import VideoAnalysisTab

@pytest.fixture
def video_analysis_tab_instance():
    """Fixture to create a VideoAnalysisTab instance for testing."""
    root = ctk.CTk()  # create a test root window
    tab = VideoAnalysisTab(root)
    root.update_idletasks()
    yield tab
    root.destroy()


def test_video_analysis_tab_initialization(video_analysis_tab_instance):
    """Test that the VideoAnalysisTab initializes without errors and required widgets are present."""
    assert isinstance(video_analysis_tab_instance, ctk.CTkFrame)
    
    # Check that message field exists
    msg_field = video_analysis_tab_instance.message_field
    assert msg_field is not None
    assert isinstance(msg_field, ctk.CTkLabel)
    assert "No video uploaded yet." in msg_field.cget("text")

def test_buttons_exist(video_analysis_tab_instance):
    """Test that key buttons (Upload Video, Analyze Video) are created."""
    # Upload Video button
    upload_button = None
    # Analyze Video button
    analyze_button = None
    # Look through children to find buttons by their text
    for child in video_analysis_tab_instance.winfo_children():
        # Button frame for upload, dropdown, analyze
        if isinstance(child, ctk.CTkFrame):
            for grandchild in child.winfo_children():
                if isinstance(grandchild, ctk.CTkButton):
                    if grandchild.cget("text") == "Upload Video":
                        upload_button = grandchild
                    elif grandchild.cget("text") == "Analyze Video":
                        analyze_button = grandchild

    assert upload_button is not None, "Upload Video button not found."
    assert analyze_button is not None, "Analyze Video button not found."

def test_preloaded_video_dropdown(video_analysis_tab_instance):
    """Test that the preloaded video dropdown is created and has expected values."""
    dropdown = None
    for child in video_analysis_tab_instance.winfo_children():
        if isinstance(child, ctk.CTkFrame):
            for grandchild in child.winfo_children():
                if isinstance(grandchild, ctk.CTkOptionMenu):
                    dropdown = grandchild
                    break
    assert dropdown is not None, "Preloaded video dropdown not found."
    assert dropdown == ["Sample1.mp4", "Sample2.mp4", "Sample3.mp4"]

def test_play_pause_button_initial_state(video_analysis_tab_instance):
    """Test that the play/pause button is initially set to the play image."""
    play_pause_button = video_analysis_tab_instance.play_pause_button
    assert play_pause_button is not None
    # The button should have the play image initially (no video loaded)
    # We can't easily assert the image object, but we know the code sets the 'play_image' initially.
    # Just ensure we can access it without error.
    assert play_pause_button.cget("image") is video_analysis_tab_instance.play_image

def test_update_message_method(video_analysis_tab_instance):
    """Test that updating the message field works correctly."""
    video_analysis_tab_instance.update_message("Test message")
    assert video_analysis_tab_instance.message_field.cget("text") == "Test message"

@patch("VideoAnalysisTab.vam.analyze_video_model", return_value=(60.0, 40.0))
def test_analyze_video_no_upload(mock_analyze, video_analysis_tab_instance):
    """Test analyze video behavior when no video is uploaded."""
    video_analysis_tab_instance.uploaded_video_path = None
    video_analysis_tab_instance.analyze_video()
    assert "No video uploaded or selected for analysis." in video_analysis_tab_instance.message_field.cget("text")
    mock_analyze.assert_not_called()

@patch("VideoAnalysisTab.vam.analyze_video_model", return_value=(60.0, 40.0))
def test_analyze_video_with_upload(mock_analyze, video_analysis_tab_instance, tmp_path):
    """Test analyze video behavior when a video is uploaded."""
    # Create a dummy video file
    video_file = tmp_path / "dummy_video.mp4"
    video_file.write_text("dummy content")

    # Set a fake uploaded video path
    video_analysis_tab_instance.uploaded_video_path = str(video_file)
    video_analysis_tab_instance.analyze_video()
    assert "BALL POSSESSION | Team 0: 60.00% | Team 1: 40.00%" in video_analysis_tab_instance.message_field.cget("text")
    mock_analyze.assert_called_once()

def test_select_preloaded_video_not_found(video_analysis_tab_instance):
    """Test selecting a preloaded video that does not exist."""
    # If "PreloadedVideos/Sample4.mp4" doesn't exist, it should show an error message.
    video_analysis_tab_instance.select_preloaded_video("Sample4.mp4")
    assert "Error: Preloaded video Sample4.mp4 not found." in video_analysis_tab_instance.message_field.cget("text")

# def test_select_preloaded_video_found(video_analysis_tab_instance, tmp_path):
#     """Test selecting a preloaded video that exists."""
#     # Create a "PreloadedVideos" directory and a sample file
#     preloaded_dir = tmp_path / "preloaded_videos"
#     preloaded_dir.mkdir()
#     sample_video = preloaded_dir / "ball_possesion.mp4"
#     sample_video.write_text("dummy content")

#     # Temporarily change directory so os.path.join("PreloadedVideos", ...) finds our tmp_path
#     import os
#     original_cwd = os.getcwd()
#     os.chdir(str(tmp_path))

#     video_analysis_tab_instance.select_preloaded_video("ball_possesion.mp4")

#     # Restore the original cwd after test
#     os.chdir(original_cwd)

#     assert "Preloaded video selected: ball_possesion.mp4" in video_analysis_tab_instance.message_field.cget("text")

def test_toggle_play_pause_without_video(video_analysis_tab_instance):
    """Test toggling play/pause when no video is loaded."""
    video_analysis_tab_instance.toggle_play_pause()
    # Since no video is loaded, it should show an error message.
    assert "Error: No video loaded." in video_analysis_tab_instance.message_field.cget("text")
