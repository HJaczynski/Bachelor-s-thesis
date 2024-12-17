import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import time
import os
import tkinter.filedialog as fd
from threading import Thread

import VideoAnalysisModel as vam


class VideoAnalysisTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)

        # Load images for play and pause buttons
        self.play_image = ctk.CTkImage(Image.open("Images/play-button.png").resize((30, 30), Image.Resampling.LANCZOS))
        self.pause_image = ctk.CTkImage(Image.open("Images/pause-button.png").resize((30, 30), Image.Resampling.LANCZOS))

        self.uploaded_video_path = None
        self.analyze_video_path = None
        self.cap = None
        self.playing = False
        self.frame_count = 0
        self.current_frame = 0

        # Create a parent container for the video player and controls
        self.video_frame = ctk.CTkFrame(self)
        self.video_frame.grid(row=0, column=0, pady=5, sticky="nsew")
        self.video_frame.grid_propagate(False)
        self.video_frame.configure(width=900, height=507)

        self.video_player_canvas = ctk.CTkCanvas(self.video_frame, width=900, height=507, bg="black")
        self.video_player_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # Controls frame positioned below the video canvas
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=1, column=0, pady=5, sticky="ew")

        self.play_pause_button = ctk.CTkButton(
            self.controls_frame,
            text="",
            image=self.play_image,
            command=self.toggle_play_pause,
            width=40,
            height=40,
            fg_color="transparent"
        )
        self.play_pause_button.grid(row=0, column=0, padx=5, pady=5)
        self.slider = ctk.CTkSlider(self.controls_frame, from_=0, to=100, command=self.seek_video, width=700)
        self.slider.set(0)

        self.slider.grid(row=0, column=1, padx=10, pady=5, sticky="ew")

        self.controls_frame.grid_columnconfigure(1, weight=1)

        self.message_field = ctk.CTkLabel(self, text="No video uploaded yet.", font=("Calibri", 18, "bold"))
        self.message_field.grid(row=3, column=0, pady=10)

        # Add Upload, Preloaded Dropdown, and Analyze buttons
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=2, column=0, pady=10)

        upload_button = ctk.CTkButton(button_frame, text="Upload Video", command=self.upload_video, font=("Calibri", 18, "bold"))
        upload_button.grid(row=0, column=0, padx=5)

        self.preloaded_videos = self.get_preloaded_videos()
        self.video_dropdown = ctk.CTkOptionMenu(button_frame, values=self.preloaded_videos, command=self.select_preloaded_video, font=("Calibri", 18, "bold"))
        self.video_dropdown.grid(row=0, column=1, padx=5)

        analyze_button = ctk.CTkButton(button_frame, text="Analyze Video", command=self.analyze_video, font=("Calibri", 18, "bold"))
        analyze_button.grid(row=0, column=2, padx=5)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)


    def select_preloaded_video(self, video_name):
        video_path = os.path.join("preloaded_videos", video_name)
        if os.path.exists(video_path):
            self.uploaded_video_path = video_path
            self.update_message(f"Preloaded video selected: {video_name}")
            self.initialize_video(video_path)
        else:
            self.update_message(f"Error: Preloaded video {video_name} not found.")

    def get_preloaded_videos(self, folder_name="preloaded_videos"):
        """
        Returns a list of file names in the specified folder.

        Parameters:
        folder_name (str): The name of the folder containing preloaded videos.

        Returns:
        list: A list of file names in the folder.
        """
        # Get the absolute path of the folder
        folder_path = os.path.join(os.getcwd(), folder_name)

        # Check if the folder exists
        if not os.path.exists(folder_path):
            print(f"Folder '{folder_name}' does not exist.")
            return []

        # List all files in the folder
        file_list = [file for file in os.listdir(folder_path) if os.path.isfile(os.path.join(folder_path, file))]
        return file_list
    
    def analyze_video(self):
        if not self.uploaded_video_path:
            self.update_message("No video uploaded or selected for analysis.")
            return
        self.update_message(f"Analyzing video: {os.path.basename(self.uploaded_video_path)}")
        # Add analysis logic here

        preloaded_videos_dir = os.path.join(os.getcwd(), "preloaded_videos")
        if not os.path.exists(preloaded_videos_dir):
            os.makedirs(preloaded_videos_dir)
        #downloads = os.path.join(os.path.expanduser("~"), "Downloads")
        output_path = os.path.join(preloaded_videos_dir, "VideoOutput.mp4")

        print(self.uploaded_video_path)
        print(output_path)

        # update label to "analyzing video"
        team_0_possession_percent, team_1_possession_percent = vam.analyze_video_model(video_path=self.uploaded_video_path, output_path=output_path, model_path="models/player_detection.pt")
        self.initialize_video(output_path)
        self.update_message(f"BALL POSSESSION | Team 0: {team_0_possession_percent:.2f}% | Team 1: {team_1_possession_percent:.2f}%")


    

    def update_message(self, message):
        self.message_field.configure(text=message, font=("Calibri", 18, "bold"))

    def upload_video(self):
        video_path = fd.askopenfilename(
            title="Select a Video File",
            filetypes=(
                ("Video files", ".mp4;.avi;*.mov;*.flv;*.mkv;*.webm"),
                ("All files", "."),
            ),
        )

        if video_path:
            self.uploaded_video_path = video_path
            self.update_message(f"Video uploaded: {os.path.basename(video_path)}")
            self.initialize_video(video_path)

    def initialize_video(self, video_path):
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.update_message("Error: Unable to open video.")
            return

        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.slider.configure(to=self.frame_count)
        self.current_frame = 0
        self.toggle_play_pause()

    def toggle_play_pause(self):
        if self.playing:
            self.playing = False
            self.play_pause_button.configure(image=self.play_image)  # Switch to play image
            self.slider.configure(state="normal")  # Re-enable the slider when paused
        else:
            if not self.cap or not self.cap.isOpened():
                self.update_message("Error: No video loaded.")
                return

            self.playing = True
            self.play_pause_button.configure(image=self.pause_image)  # Switch to pause image
            self.slider.configure(state="disabled")
            Thread(target=self._play_video_thread).start()

    def _play_video_thread(self):
        # Replace direct PhotoImage creation with a thread-safe approach
        def update_frame(frame):
            if not self.playing:
                return
            img = Image.fromarray(frame)
            img_tk = ImageTk.PhotoImage(image=img)
            self.video_player_canvas.create_image(0, 0, anchor="nw", image=img_tk)
            self.video_player_canvas.image = img_tk  # Keep a reference!

        while self.cap.isOpened() and self.playing:
            ret, frame = self.cap.read()
            if ret:
                # Resize the frame to 900x507
                frame = cv2.resize(frame, (900, 507))
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                # Schedule the frame update in the main thread
                self.after(1, lambda f=frame: update_frame(f))
                time.sleep(1/30)  # Control frame rate
            else:
                break

        self.playing = False
        self.slider.configure(state="normal")

    def seek_video(self, frame_position):
        if self.cap and not self.playing:
            self.current_frame = int(frame_position)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            ret, frame = self.cap.read()
            if ret:
                resized_frame = cv2.resize(frame, (900, 507))
                frame_rgb = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
                img = Image.fromarray(frame_rgb)
                img_tk = ImageTk.PhotoImage(image=img)
                self.video_player_canvas.create_image(0, 0, anchor="nw", image=img_tk)
                self.video_player_canvas.image = img_tk

    def stop_video(self):
        self.playing = False
        if self.cap and self.cap.isOpened():
            self.cap.release()
        self.video_player_canvas.delete("all")

    def __del__(self):
        self.stop_video()

    def cleanup(self):
        # Cancel pending after calls
        if hasattr(self, "update_task_id"):
            self.after_cancel(self.update_task_id)



# if _name_ == "_main_":
#     def on_closing():
#         video_tab.stop_video()
#         root.destroy()

#     root = ctk.CTk()
#     video_tab = VideoAnalysisTab(root)
#     video_tab.pack(fill="both", expand=True)

#     root.protocol("WM_DELETE_WINDOW", on_closing)
#     root.mainloop()