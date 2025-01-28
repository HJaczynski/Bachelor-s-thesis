import customtkinter as ctk
import sqlite3
import webbrowser
from PIL import Image, ImageTk
from Player import Player
import helper as h
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
import matplotlib.pyplot as plt
import tkinter.filedialog as fd
import pandas as pd
from plotly.io import write_html
import plotly.graph_objects as go



class PlayerDashboardTab(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)

        # Configure grid rows and columns
        for i in range(13):
            self.grid_rowconfigure(i, weight=1)

        for i in range(8):
            self.grid_columnconfigure(i, weight=1)

        # Initialize default player
        self.current_player = Player()
        self.player_names_list = h.get_player_names_list()

        # initalize empty dataframe
        self.current_df = pd.DataFrame()

        # initialize empty graphs
        self.current_plotly = go.Figure()
        self.current_matplotlib = plt.figure()


        self.player_name_combobox = ctk.CTkComboBox(self, values=self.player_names_list, font=("Calibri", 18, "bold"))
        self.player_name_combobox.grid(row=0, column=0, columnspan=6, padx=5, pady=5, sticky='ew')
        self.player_name_combobox.bind('<KeyRelease>', self.filter_combobox)

        search_button = ctk.CTkButton(self, text="Search Player", command=self.get_player_info, font=("Calibri", 18, "bold"))
        search_button.grid(row=0, column=6, columnspan=2, padx=5, pady=5, sticky="ew")

        self.graph_type_combobox = ctk.CTkComboBox(self, values=["Goals", "Assists", "Goals + Assists", "Cards", "Market Value", "Appearances", "Appearances per Competition"], font=("Calibri", 18, "bold"), command=self.update_graph)
        
        self.graph_type_combobox.grid(row=1, column=0, padx=5, pady=5, sticky="ew", columnspan=6)

        self.reset_button = ctk.CTkButton(self, text="Reset Dashboard", command=self.reset_dashboard_tab, font=("Calibri", 18, "bold"))
        self.reset_button.grid(row=1, column=6, columnspan=2, padx=5, pady=5, sticky="ew")

        # Create the temporary frame with a fixed width
        player_info_frame = ctk.CTkFrame(self, fg_color='#1d1e1e', corner_radius=10, width=330, height=500)
        player_info_frame.grid(row=2, column=6, rowspan=10, columnspan=2, padx=5, pady=5, sticky="nsew")

        # Configure the grid inside the temp_frame
        player_info_frame.grid_rowconfigure(0, weight=1)  # First row
        player_info_frame.grid_rowconfigure(1, weight=1)  # Second row
        player_info_frame.grid_columnconfigure(0, weight=1)  # First column
        player_info_frame.grid_columnconfigure(1, weight=1)  # Second column

        self.club_icon_canvas = ctk.CTkCanvas(player_info_frame, width=200, height=200, bg="#1d1e1e", highlightthickness=0)
        self.club_icon_canvas.grid(row=0, column=0, columnspan=1, padx=20, pady=20, sticky="nsew")

        self.player_image_canvas = ctk.CTkCanvas(player_info_frame,  width=209, height=272, highlightthickness=0)
        self.player_image_canvas.grid(row=0, column=1, columnspan=1, padx=20, pady=20, sticky="nsew")

        string = "Name:\nDate of Birth (Age):\nCountry of Birth:\nCity of Birth:\nCountry of Citizenship:\nPosition:\nPreferred Foot:\nHeight:\nCurrent Club:\nMarket Value:\nHighest Market Value:"

        info_label = ctk.CTkLabel(
            player_info_frame,
            text=string,
            justify="center",
            font=("Calibri", 18, "bold"),
            fg_color="#1d1e1e", #2c2c2c
            text_color="white",
            corner_radius=10,
            width=100
        )
        info_label.grid(row=1, column=0, padx=5, pady=5, sticky="nsew")

        self.result_label = ctk.CTkLabel(
            player_info_frame,
            text=self.current_player,
            justify="center",
            fg_color='#1d1e1e', ##1d1e1e
            text_color='white',
            corner_radius=10,
            font=("Calibri", 18),
            width=230
        )
        self.result_label.grid(row=1, column=1, padx=5, pady=5, sticky="nsew")

        interactive_dashboard_button = ctk.CTkButton(self, text="Interactive Dashboard", command=self.open_plotly_graph, font=("Calibri", 18, "bold"))
        interactive_dashboard_button.grid(row=12, column=0, columnspan=2, padx=5, pady=5, sticky="nsew")

        save_csv_button = ctk.CTkButton(self, text="Save Dashboard Data (CSV)", command=self.save_df_to_csv, font=("Calibri", 18, "bold"))
        save_csv_button.grid(row=12, column=2, columnspan=2, padx=5, pady=5, sticky="nsew")

        save_dashboard_image_button = ctk.CTkButton(self, text="Save Dashboard Image", command=self.save_graph_to_img, font=("Calibri", 18, "bold"))
        save_dashboard_image_button.grid(row=12, column=4, columnspan=2, padx=5, pady=5, sticky="nsew")

        visit_transfermarkt_button = ctk.CTkButton(self, text="Visit Transfermarkt", command=self.redirect_to_transfermarkt, font=("Calibri", 18, "bold"))
        visit_transfermarkt_button.grid(row=12, column=6, columnspan=2, padx=5, pady=5, sticky="nsew")

        self.graph_canvas = ctk.CTkCanvas(self)
        self.graph_canvas.grid(row=2, column=0, rowspan=10, columnspan=6, padx=5, pady=5, sticky="nsew")
        self.graph_canvas.bind("<Configure>", self.set_initial_graph_canvas)

        self.tmp_graph_canvas_txt = None


    ### FUNCTIONS ### 
    def update_graph(self, event):
            self.graph_canvas.delete("all")
            self.clear_dashboard_text()
            self.update_graph_canvas()
        

    def generate_graph_matplotlib(self):
        graph_type = self.graph_type_combobox.get()

        if graph_type == "Goals":
            fig = self.current_player.generate_goals_mpl_graph()
            fig.tight_layout()
            self.current_df = self.current_player.goals_df
        elif graph_type == "Assists": 
            fig = self.current_player.generate_assists_mpl_graph()
            self.current_df = self.current_player.assists_df
        elif graph_type == "Goals + Assists":
            fig = self.current_player.generate_ga_mpl_graph()
            self.current_df = self.current_player.ga_df
        elif graph_type == "Cards":
            fig = self.current_player.generate_cards_mpl_graph()
            self.current_df = self.current_player.cards_df
        elif graph_type == "Market Value":
            fig = self.current_player.generate_marketvalue_mpl_graph()
            self.current_df = self.current_player.marketvalue_df
        elif graph_type == "Appearances":
            fig = self.current_player.generate_appearances_per_year_mpl_graph()
            self.current_df = self.current_player.appearances_per_year_df
        elif graph_type == "Appearances per Competition":
            fig = self.current_player.generate_appearances_per_competition_mpl_graph()
            self.current_df = self.current_player.appearances_per_competition_df

        self.current_matplotlib = fig

        return fig


    # Function def: Searches for a player within a database
    def get_player_by_name(self, player_name):
        try:
            # Connect to the database
            conn = sqlite3.connect("transfermarkt.db")
            cursor = conn.cursor()
            
            # Execute the SQL query to fetch player by name
            cursor.execute("SELECT * FROM filtered_players WHERE LOWER(name) = LOWER(?)", (player_name,))
            
            # Fetch the first matching player record
            player_data = cursor.fetchone()
            
            # Close the connection
            conn.close()

            print(player_data)
            
            # If player is found, return an instance of the Player class
            if player_data:
                player = Player(player_data)  # Create Player instance
                return player
            
            # If no player found, return None
            return None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None
        except Exception as e:
            print(f"Exception error: {e}")
            return None


    # Function def:
    def update_graph_canvas(self):
        self.graph_canvas.delete("all")

        # Generate the Matplotlib figure
        #fig = self.current_player.generate_goals_mpl_graph()

        fig = self.generate_graph_matplotlib()

        # Render the figure canvas
        canvas = FigureCanvas(fig)
        canvas.draw()  # Explicitly render the figure

        # Convert the figure to a PIL Image
        pil_image = Image.frombytes('RGB', canvas.get_width_height(), canvas.tostring_rgb())

        # Get the dimensions of the dashboard canvas
        self.graph_canvas.update_idletasks()
        canvas_width = self.graph_canvas.winfo_width()
        canvas_height = self.graph_canvas.winfo_height()

        # Resize the PIL image to fill the dashboard canvas
        resized_image = pil_image.resize((canvas_width, canvas_height), Image.LANCZOS)

        # Convert the resized PIL Image to a format compatible with customtkinter
        self.image_tk = ImageTk.PhotoImage(resized_image)

        # Display the resized image on the customtkinter canvas
        self.graph_canvas.create_image(canvas_width // 2, canvas_height // 2, anchor="center", image=self.image_tk)

        # Clean up the Matplotlib figure
        plt.close(fig)


    # Function def:
    def update_result_label(self):
        # Update club icon image
        self.club_icon_image = h.load_image_from_url(self.current_player.get_current_club_logo_url())

        # Resize the club icon image to fit the canvas
        canvas_width = self.club_icon_canvas.winfo_width()
        canvas_height = self.club_icon_canvas.winfo_height()
        resized_club_icon_image = self.club_icon_image.resize((canvas_width, canvas_height), Image.LANCZOS)

        self.club_icon_image_tk = ImageTk.PhotoImage(resized_club_icon_image)

        # Clear the previous image
        self.club_icon_canvas.delete("all")

        # Add the resized image to the canvas
        self.club_icon_canvas.create_image(0, 0, anchor="nw", image=self.club_icon_image_tk)

        # Update player image
        self.player_image = h.load_image_from_url(self.current_player.get_player_image_url())

        # Resize the player image to fit the canvas
        canvas_width = self.player_image_canvas.winfo_width()
        canvas_height = self.player_image_canvas.winfo_height()
        resized_player_image = self.player_image.resize((canvas_width, canvas_height), Image.LANCZOS)

        self.player_image_tk = ImageTk.PhotoImage(resized_player_image)

        # Clear the previous image
        self.player_image_canvas.delete("all")

        # Add the resized image to the player image canvas
        self.player_image_canvas.create_image(0, 0, anchor="nw", image=self.player_image_tk)


    # Function def: Searches for a player
    def get_player_info(self):
        player_name_field = self.player_name_combobox.get()
        #player_name_field = self.player_name_entry.get()
        self.current_player = self.get_player_by_name(player_name_field)

        if self.current_player:
            self.result_label.configure(text=self.current_player)
            self.update_graph_canvas()
            self.update_result_label()
        else:
            print("Player not found.")


    # Function def: 
    def redirect_to_transfermarkt(self):
        url = self.current_player.player_transfermarkt_url
        webbrowser.open(url)
        return
    

    # Function def:
    def clear_dashboard_text(self):
        """
        Clears the centered text from the canvas if it exists.
        """
        # Check if there is existing text on the canvas and delete it
        if hasattr(self, 'temp_text_id') and self.tmp_graph_canvas_txt:
            self.graph_canvas.delete(self.tmp_graph_canvas_txt)
            self.tmp_graph_canvas_txt = None  # Reset the text ID to avoid re-deleting


    def reset_dashboard_tab(self):
        self.current_player = Player()  # Reset player to default
        self.result_label.configure(text=self.current_player)  # Reset result label to default player info
        self.graph_canvas.delete("all")  # Clear all items (including images and text)
        self.set_initial_graph_canvas()  # Manually reset the canvas with centered text
        self.update_result_label()
        return


    # Function def: Center the text in the initial canvas
    def set_initial_graph_canvas(self, event=None):
        # Only show the initial text if we have the default player (empty or placeholder name)
        if str(self.current_player.get_name()) in ["", "Default Player Name"]:
            canvas_width = self.graph_canvas.winfo_width()
            canvas_height = self.graph_canvas.winfo_height()

            if self.tmp_graph_canvas_txt:
                self.graph_canvas.delete(self.tmp_graph_canvas_txt)

            x = canvas_width // 2
            y = canvas_height // 2

            self.tmp_graph_canvas_txt = self.graph_canvas.create_text(
                x, y,
                text="Please search for a player to load a graph",
                font=("Roboto", 24, "bold"),
                fill="black",
                anchor="center",
                justify="center"
            )
        else:
            # If a player is already loaded, don't draw the initial text
            if self.tmp_graph_canvas_txt:
                self.graph_canvas.delete(self.tmp_graph_canvas_txt)
                self.tmp_graph_canvas_txt = None


    # Function def:
    def filter_combobox(self, event):
        """Filters the combo box options based on the input text."""
        input_text = self.player_name_combobox.get()
        
        if input_text == '':
            filtered_values = self.player_names_list
        else:
            filtered_values = [item for item in self.player_names_list if input_text.lower() in item.lower()]

        # Dynamically update the dropdown options
        self.player_name_combobox.configure(values=filtered_values)
        self.player_name_combobox.event_generate('<Button-1>')


    def save_graph_to_img(self):
        # Open a file manager to specify the save location and file name 
        file_path = fd.asksaveasfilename(
            defaultextension=".png",
            filetypes=[
                ("PNG files", "*.png"),
                ("JPEG files", "*.jpg"),
                ("All files", "*.*")
            ],
            title="Save Graph as Image",
            initialfile=f"{self.current_player.get_name()} Graph.png"  # Set a default file name
        )

        if file_path:
            try:
                # Save the Matplotlib figure to the specified file path
                self.current_matplotlib.savefig(file_path, format=file_path.split('.')[-1])
                print(f"Canvas saved successfully as {file_path}")
            except Exception as e:
                print(f"An error occurred while saving the canvas: {e}")
    

    def save_df_to_csv(self):
        try:
            # Open file explorer to choose save location and file name
            file_path = fd.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
                title="Save DataFrame as CSV",
                initialfile=f"{self.current_player.get_name()}.csv"  # Set a default file name
            )
            
            # If the user cancels, file_path will be empty
            if not file_path:
                print("Save operation cancelled.")
                return

            # Save the DataFrame to the selected file path
            self.current_df.to_csv(file_path, index=False)
            print(f"DataFrame successfully saved to {file_path}")
        except Exception as e:
            print(f"An error occurred while saving the file: {e}")
    

    def open_plotly_graph(self):
        graph_type = self.graph_type_combobox.get()

        if graph_type == "Goals":
            self.current_plotly = self.current_player.generate_goals_graph_plotly()
        elif graph_type == "Assists": 
            self.current_plotly = self.current_player.generate_assists_graph_plotly()
        elif graph_type == "Goals + Assists":
            self.current_plotly = self.current_player.generate_goals_assists_graph_plotly()
        elif graph_type == "Cards":
            self.current_plotly = self.current_player.generate_cards_graph_plotly()
        elif graph_type == "Market Value":
            self.current_plotly = self.current_player.generate_marketvalue_graph_plotly()
        elif graph_type == "Appearances":
            self.current_plotly = self.current_player.generate_appearances_per_year_plotly()
        elif graph_type == "Appearances per Competition":
            self.current_plotly = self.current_player.generate_appearances_per_competition_plotly()


        try:
            # Save the figure as a temporary HTML file
            #temp_file = f"temp_plotly_figure.html"
            temp_file = f"{self.current_player.get_player_id()}_{self.graph_type_combobox.get()}.html"
            write_html(self.current_plotly, file=temp_file, auto_open=False)
            # Open the file in the default browser
            webbrowser.open(temp_file)
            print("Plotly figure opened in the default browser.")
        except Exception as e:
            print(f"An error occurred: {e}")


    def cleanup(self):
        # Close database connection
        if self.db_connection:
            self.db_connection.close()
            print("PlayerDashboardTab database connection closed.")

        # Release images
        self.image_tk = None
        self.club_icon_image_tk = None
        self.player_image_tk = None
        print("PlayerDashboardTab images released.")