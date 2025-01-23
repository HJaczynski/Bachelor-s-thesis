import customtkinter as ctk
import cv2
from PIL import Image, ImageTk
import time
import os
import threading
import tkinter.filedialog as fd
from threading import Thread, Lock
import VideoAnalysisModel as vam  # your custom analysis code

class VideoAnalysisTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)

        # ---------------------------------------------------------------------
        #  ADD A LOCK TO PROTECT VIDEO CAPTURES (NEW)
        # ---------------------------------------------------------------------
        self.read_lock = Lock()  # We will lock around read()/set() calls

        # -------------------------
        #  CAPTURES AND PATHS
        # -------------------------
        self.cap = None           # main video capture
        self.cap2 = None          # secondary video capture
        self.playing = False
        self.frame_count = 0
        self.current_frame = 0

        # Paths for main / top_down / ball_path
        self.uploaded_main_video_path = None
        self.top_down_path = None
        self.ball_path_path = None

        # -------------------------
        #  PLAY/PAUSE BUTTON ICONS
        # -------------------------
        self.play_image = ctk.CTkImage(
            Image.open("Images/play-button.png").resize((30, 30), Image.Resampling.LANCZOS)
        )
        self.pause_image = ctk.CTkImage(
            Image.open("Images/pause-button.png").resize((30, 30), Image.Resampling.LANCZOS)
        )

        # -------------------------
        #  GRID LAYOUT
        # -------------------------
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)  # Stats
        self.grid_columnconfigure(1, weight=2)  # Main video
        self.grid_columnconfigure(2, minsize=320)  # Secondary

        # -------------------------
        #  STATS LABEL (COLUMN 0)
        # -------------------------
        self.statistics_label = ctk.CTkLabel(
            self,
            width=400,
            height=400,
            font=("Calibri", 18, "bold"),
            text="Statistics will be displayed here.",
            bg_color="#1d1e1e",
            corner_radius=10
        )
        self.statistics_label.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # -------------------------
        #  MAIN VIDEO (COLUMN 1)
        # -------------------------
        self.video_frame = ctk.CTkFrame(self)
        self.video_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        self.video_frame.configure(width=800, height=394)

        self.video_player_canvas = ctk.CTkCanvas(
            self.video_frame, 
            width=800, 
            height=394, 
            bg="black"
        )
        self.video_player_canvas.place(relx=0.5, rely=0.5, anchor="center")

        # -------------------------
        #  CONTROLS (Below main video)
        # -------------------------
        self.controls_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.controls_frame.grid(row=1, column=1, pady=5, sticky="ew")

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

        self.slider = ctk.CTkSlider(
            self.controls_frame,
            from_=0, 
            to=100,
            command=self.seek_video,
            width=800
        )
        self.slider.set(0)
        self.slider.grid(row=0, column=1, padx=10, pady=5, sticky="ew")
        self.controls_frame.grid_columnconfigure(1, weight=1)

        self.message_field = ctk.CTkLabel(
            self, 
            text="No video uploaded yet.", 
            font=("Calibri", 18, "bold")
        )
        self.message_field.grid(row=2, column=1, pady=10)

        # -------------------------
        #  BOTTOM BUTTONS (Below controls)
        # -------------------------
        button_frame = ctk.CTkFrame(self, fg_color="transparent")
        button_frame.grid(row=4, column=1, pady=10)

        # Upload button
        upload_button = ctk.CTkButton(
            button_frame,
            text="Upload Video",
            command=self.upload_video,
            font=("Calibri", 18, "bold")
        )
        upload_button.grid(row=0, column=0, padx=5)

        # Preloaded videos dropdown
        self.preloaded_videos = self.get_preloaded_videos()
        self.video_dropdown = ctk.CTkOptionMenu(
            button_frame, 
            values=self.preloaded_videos,
            command=self.select_preloaded_video,
            font=("Calibri", 18, "bold")
        )
        self.video_dropdown.grid(row=0, column=1, padx=5)

        # Analyze button
        analyze_button = ctk.CTkButton(
            button_frame,
            text="Analyze Video",
            command=self.analyze_video,
            font=("Calibri", 18, "bold")
        )
        analyze_button.grid(row=0, column=2, padx=5)

        # -------------------------
        #  SECONDARY VIDEO FRAME (COLUMN 2)
        # -------------------------
        self.video_frame2 = ctk.CTkFrame(self, width=280)
        self.video_frame2.configure(height=394)

        # Create the canvas
        self.video_player_canvas2 = ctk.CTkCanvas(
            self.video_frame2,
            width=280,
            height=394,
            bg="black"
        )
        self.video_player_canvas2.place(relx=0.5, rely=0.5, anchor="center")

        # Create the secondary dropdown
        self.secondary_dropdown = ctk.CTkOptionMenu(
            self.video_frame2,
            values=["Ball Path", "Top Down"],
            command=self.on_secondary_choice,
            font=("Calibri", 14, "bold"),
            width=200
        )
        self.secondary_dropdown.set("Ball Path")  # default selection
        self.secondary_dropdown.pack(pady=(10, 0))

        # We initially HIDE this frame (so no pitch is shown yet)
        # We'll only show it after analysis is done
        self.video_frame2.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        self.video_frame2.grid_remove()

        # Instead, show a placeholder label in column=2
        self.no_pitch_label = ctk.CTkLabel(
            self,
            text="Analyze the video or check the video \nfrom dropdown list to see pitch views...",
            font=("Calibri", 16, "bold"),
            fg_color="#1d1e1e",
            corner_radius=10,
            width=280,
            height=394,
            justify="center"
        )
        # Grid this label in the same slot as where the frame would go
        self.no_pitch_label.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")

        self.progress_bar = ctk.CTkProgressBar(self, width=500)
        self.progress_bar.grid(row=3, column=1, pady=10, padx=10)  # Or wherever you want it
        self.progress_bar.set(0)  # Set it to 0 initially


    # ---------------------------------------------------------
    #  GET / SELECT PRELOADED VIDEO
    # ---------------------------------------------------------
    def get_preloaded_videos(self, folder_name="preloaded_videos"):
        folder_path = os.path.join(os.getcwd(), folder_name)
        if not os.path.exists(folder_path):
            print(f"Folder '{folder_name}' does not exist.")
            return []
        preloaded = []
        for entry in os.listdir(folder_path):
            entry_path = os.path.join(folder_path, entry)
            if os.path.isdir(entry_path):
                if os.path.isfile(os.path.join(entry_path, "video_output.mp4")):
                    preloaded.append(entry)
        return preloaded

    def select_preloaded_video(self, video_name):
        directory = os.path.join("preloaded_videos", video_name)
        main_video_path = os.path.join(directory, "video_output.mp4")
        self.top_down_path = os.path.join(directory, "top_down_view.mp4")
        self.ball_path_path = os.path.join(directory, "ball_path.mp4")

        if os.path.exists(main_video_path):
            self.uploaded_main_video_path = main_video_path
            self.update_message(f"Preloaded video selected: {video_name}")
            self.initialize_video(main_video_path)

            self.no_pitch_label.grid_remove()  # hide the placeholder
            self.video_frame2.grid()

            # Based on current dropdown choice, open that secondary
            current_choice = self.secondary_dropdown.get()
            if current_choice == "Top Down":
                self.open_secondary_video(self.top_down_path)
            else:
                self.open_secondary_video(self.ball_path_path)
        else:
            self.update_message(f"Error: Preloaded video {video_name} not found.")

    def upload_video(self):
        video_path = fd.askopenfilename(
            title="Select a Video File",
            filetypes=(
                ("Video files", "*.mp4;*.avi;*.mov;*.flv;*.mkv;*.webm"),
                ("All files", "*.*"),
            ),
        )
        if video_path:
            self.uploaded_main_video_path = video_path
            self.update_message(f"Video uploaded: {os.path.basename(video_path)}")
            self.initialize_video(video_path)


    # ---------------------------------------------------------
    #  ANALYSIS
    # ---------------------------------------------------------
    def analyze_video(self):
        if not self.uploaded_main_video_path:
            self.update_message("No video uploaded or selected for analysis.")
            return
        thread = threading.Thread(target=self._analyze_video_thread)
        thread.start()

    def _analyze_video_thread(self):
        self.update_message(f"Analyzing video: {os.path.basename(self.uploaded_main_video_path)}")
        
        # Set output path
        if not os.path.exists("Preloaded_Videos"):
            os.makedirs("Preloaded_Videos")
        preloaded_dir = os.path.join(os.getcwd(), "Preloaded_Videos")
        identifier = "Video_analysis_" + time.strftime("%Y%m%d-%H%M%S")
        identifier = os.path.join(preloaded_dir, identifier)
        if not os.path.exists(identifier):
            os.makedirs(identifier)
        output_path = os.path.join(preloaded_dir, identifier)

        print(self.uploaded_main_video_path)
        print(output_path)

        # Run your analysis
        team1_possession, team2_possession, avg_speeds, avg_distances, counter = vam.analyze_video_model(
            video_path=self.uploaded_main_video_path, 
            output_path=output_path, 
            model_path="models/player_detection2.pt",
            progress_callback=self.on_progress_update
        )

        main_output_path = os.path.join(output_path, "video_output.mp4")
        self.top_down_path = os.path.join(output_path, "top_down_view.mp4")
        self.ball_path_path = os.path.join(output_path, "ball_path.mp4")

        self.initialize_video(main_output_path)

        # Hide the placeholder label
        self.no_pitch_label.grid_remove()
        # Show the video frame
        self.video_frame2.grid()  
        # Now open the correct secondary video (based on dropdown selection)
        current_choice = self.secondary_dropdown.get()
        if current_choice == "Top Down":
            self.open_secondary_video(self.top_down_path)
        else:
            self.open_secondary_video(self.ball_path_path)

        self.update_message("Video Analysis Complete!")

        # Show some stats
        stats_str = (
            f"Team 1 possession: {team1_possession:.2f}%\n"
            f"Team 2 possession: {team2_possession:.2f}%\n\n"
            f"Avg team 1 speed: {avg_speeds[0]:.2f} km/h\n"
            f"Avg team 2 speed: {avg_speeds[1]:.2f} km/h\n"
            f"Avg ball speed: {avg_speeds[2]:.2f} km/h\n\n"
            f"Avg team 1 distance: {avg_distances[0]:.2f} m\n"
            f"Avg team 2 distance: {avg_distances[1]:.2f} m\n"
            f"Avg ball distance: {avg_distances[2]:.2f} m\n\n"
            f"Total team 1 distance: {counter * avg_distances[0]:.2f} m\n"
            f"Total team 2 distance: {counter * avg_distances[1]:.2f} m\n"
            f"Total ball distance: {counter * avg_distances[2]:.2f} m"
        )
        self.statistics_label.configure(text=stats_str)


    # ---------------------------------------------------------
    #  SECONDARY VIDEO DROPDOWN LOGIC
    # ---------------------------------------------------------
    def on_secondary_choice(self, choice):
        if choice == "Top Down":
            self.open_secondary_video(self.top_down_path)
        else:
            self.open_secondary_video(self.ball_path_path)

    def open_secondary_video(self, path):
        """
        Close any existing cap2, open the new path, and jump to the same frame
        as the main video so we stay in sync -- all under a lock to prevent
        concurrency with the playback thread.
        """
        with self.read_lock:  # <--- PROTECT
            if self.cap2 and self.cap2.isOpened():
                self.cap2.release()

            if path and os.path.exists(path):
                self.cap2 = cv2.VideoCapture(path)
                # Align secondary to the same frame
                if self.cap and self.cap.isOpened():
                    self.cap2.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            else:
                self.cap2 = None
                if path:
                    self.update_message(
                        f"Secondary video '{os.path.basename(path)}' not found."
                    )


    # ---------------------------------------------------------
    #  MAIN VIDEO PLAYBACK
    # ---------------------------------------------------------
    def initialize_video(self, video_path):
        self.stop_video()  # Clean up any previous
        self.cap = cv2.VideoCapture(video_path)
        if not self.cap.isOpened():
            self.update_message("Error: Unable to open main video.")
            return

        self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.slider.configure(to=self.frame_count)
        self.current_frame = 0
        self.toggle_play_pause()  # Auto-play

    def toggle_play_pause(self):
        if self.playing:
            # Pause
            self.playing = False
            self.play_pause_button.configure(image=self.play_image)
            self.slider.configure(state="normal")
        else:
            # If video ended, we can "rewind" to frame 0:
            if self.current_frame >= self.frame_count:
                # Move back to frame 0
                self.current_frame = 0
                with self.read_lock:
                    self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    if self.cap2:
                        self.cap2.set(cv2.CAP_PROP_POS_FRAMES, 0)
                self.slider.set(0)

            # Now do the normal "play" logic
            if not self.cap or not self.cap.isOpened():
                self.update_message("Error: No main video loaded.")
                return

            self.playing = True
            self.play_pause_button.configure(image=self.pause_image)
            self.slider.configure(state="disabled")
            Thread(target=self._play_video_thread).start()

    def _play_video_thread(self):
        def update_frames(frame_main, frame_secondary, frame_num):
            if not self.playing:
                return

            # MAIN
            frame_main_resized = cv2.resize(frame_main, (800, 394))
            frame_main_rgb = cv2.cvtColor(frame_main_resized, cv2.COLOR_BGR2RGB)
            main_img = ImageTk.PhotoImage(image=Image.fromarray(frame_main_rgb))
            self.video_player_canvas.create_image(0, 0, anchor="nw", image=main_img)
            self.video_player_canvas.image = main_img  # keep reference

            # SECONDARY
            if frame_secondary is not None:
                frame_sec_resized = cv2.resize(frame_secondary, (280, 394))
                frame_sec_rgb = cv2.cvtColor(frame_sec_resized, cv2.COLOR_BGR2RGB)
                sec_img = ImageTk.PhotoImage(image=Image.fromarray(frame_sec_rgb))
                self.video_player_canvas2.create_image(0, 0, anchor="nw", image=sec_img)
                self.video_player_canvas2.image = sec_img  # keep reference

            # Update slider
            self.slider.set(frame_num)

        while True:
            with self.read_lock:
                if not (self.cap and self.cap.isOpened() and self.playing):
                    break
                ret_main, frame_main = self.cap.read()
                if not ret_main:
                    # Means we've reached the end of the video
                    break

                frame_secondary = None
                if self.cap2 and self.cap2.isOpened():
                    ret_sec, temp_sec = self.cap2.read()
                    if ret_sec:
                        frame_secondary = temp_sec

                self.current_frame += 1

            # Schedule the UI update on the main thread
            self.after(
                1,
                lambda fm=frame_main, fs=frame_secondary, fn=self.current_frame:
                    update_frames(fm, fs, fn)
            )
            time.sleep(1/30)  # ~30 FPS

        if self.current_frame >= self.frame_count:
            # The video ended, so let's do the following in the main thread:
            def finish_video():
                self.playing = False
                self.play_pause_button.configure(image=self.play_image)
                self.slider.configure(state="normal")
                self.slider.set(self.frame_count)  # Move slider to the end (or 0 if you prefer)
            self.after(0, finish_video)
        else:
            # The user paused or something else
            self.playing = False
            self.slider.configure(state="normal")



    def stop_video(self):
        self.playing = False
        with self.read_lock:  # <--- PROTECT
            if self.cap and self.cap.isOpened():
                self.cap.release()
            if self.cap2 and self.cap2.isOpened():
                self.cap2.release()

        self.video_player_canvas.delete("all")
        self.video_player_canvas2.delete("all")

    def seek_video(self, frame_position):
        """
        Seek in the main video while paused. If you also want to sync
        the secondary video, do the same inside this lock.
        """
        if self.cap and not self.playing:
            with self.read_lock:  # <--- PROTECT
                self.current_frame = int(frame_position)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
                ret, frame = self.cap.read()
                if ret:
                    frame_resized = cv2.resize(frame, (800, 394))
                    frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                    img_tk = ImageTk.PhotoImage(image=Image.fromarray(frame_rgb))
                    self.video_player_canvas.create_image(0, 0, anchor="nw", image=img_tk)
                    self.video_player_canvas.image = img_tk

            # If you want to keep the secondary in sync while paused:
            # if self.cap2:
            #     with self.read_lock:
            #         self.cap2.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame)
            #         ret2, frame2 = self.cap2.read()
            #         if ret2:
            #             # draw on canvas2

    def on_progress_update(self, current_frame, total_frames):
        """
        This callback is invoked from the background thread, 
        but we must schedule the actual progress_bar.set(...) in the main thread.
        """
        fraction = current_frame / total_frames
        # We must use "after" to ensure this runs on the main thread
        self.after(0, lambda: self.progress_bar.set(fraction))

    def update_message(self, message):
        self.message_field.configure(text=message, font=("Calibri", 18, "bold"))

    def __del__(self):
        self.stop_video()
