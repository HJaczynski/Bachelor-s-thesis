from datetime import datetime
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go


# TODO: ADD GOALKEEPER
class Player:
    def __init__(self, player_data=None):
        if player_data:
            # Initialize the player with the provided player_data tuple
            self.player_id = player_data[1]
            self.name = player_data[4]
            self.current_club_id = player_data[6]
            self.country_of_birth = player_data[8]
            self.city_of_birth = player_data[9]
            self.country_of_citizenship = player_data[10]
            self.date_of_birth = datetime.strptime(player_data[11], "%Y-%m-%d %H:%M:%S")
            self.position = player_data[12]
            self.foot = player_data[14]
            self.height_in_meters = player_data[15] / 100  # Convert height to meters
            self.player_image_url = player_data[18]
            self.current_club_logo_url = f"https://tmssl.akamaized.net//images/wappen/head/{self.current_club_id}.png"
            self.player_transfermarkt_url = player_data[19]
            self.current_club_name = player_data[21]
            self.market_value_in_eur = player_data[22]
            self.highest_market_value_in_eur = player_data[23]
            self.goals_df, self.assists_df, self.ga_df, self.cards_df, self.marketvalue_df = self.generate_player_stats_dfs()

            # Calculate age based on date of birth
            current_date = datetime.now()
            self.age = current_date.year - self.date_of_birth.year - (
                (current_date.month, current_date.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        else:
            # Default values for the player if no player_data is provided
            self.player_id = 0
            self.name = "n/a"
            self.current_club_id = 0
            self.country_of_birth = "n/a"
            self.city_of_birth = "n/a"
            self.country_of_citizenship = "n/a"
            self.date_of_birth = datetime(1900, 1, 1)  # Set to a placeholder date
            self.position = "n/a"
            self.foot = "n/a"
            self.height_in_meters = 0.0
            self.player_image_url = "https://img.a.transfermarkt.technology/portrait/header/default.jpg?lm=1"
            self.current_club_logo_url = "https://tmssl.akamaized.net//images/wappen/homepageWappen150x150/515.png?lm=1456997255"
            self.player_transfermarkt_url = "https://www.transfermarkt.pl/"
            self.current_club_name = "n/a"
            self.market_value_in_eur = 0
            self.highest_market_value_in_eur = 0
            self.age = 0
            self.goals_df = None
            self.assists_df = None
            self.ga_df = None
            self.cards_df = None
            self.marketvalue_df = None

    def __str__(self):
        # String representation of the player
        return (
            f"Name: {self.name}\n"
            f"Date of Birth (Age): {self.date_of_birth.strftime('%d/%m/%Y')} ({self.age})\n"
            f"Country of Birth: {self.country_of_birth}\n"
            f"City of Birth: {self.city_of_birth}\n"
            f"Country of Citizenship: {self.country_of_citizenship}\n"
            f"Position: {self.position}\n"
            f"Preferred Foot: {self.foot}\n"
            f"Height: {self.height_in_meters} meters\n"
            f"Current Club: {self.current_club_name}\n"
            f"Market Value: €{self.market_value_in_eur:,.2f}\n"
            f"Highest Market Value: €{self.highest_market_value_in_eur:,.2f}\n"
        )
    

    # Getter functions for all attributes
    def get_player_id(self):
        return self.player_id

    def get_name(self):
        return self.name

    def get_current_club_id(self):
        return self.current_club_id

    def get_country_of_birth(self):
        return self.country_of_birth

    def get_city_of_birth(self):
        return self.city_of_birth

    def get_country_of_citizenship(self):
        return self.country_of_citizenship

    def get_date_of_birth(self):
        return self.date_of_birth

    def get_position(self):
        return self.position

    def get_preferred_foot(self):
        return self.foot

    def get_height_in_meters(self):
        return self.height_in_meters

    def get_player_image_url(self):
        return self.player_image_url
    
    def get_current_club_logo_url(self):
        return self.current_club_logo_url

    def get_player_transfermarkt_url(self):
        return self.player_transfermarkt_url

    def get_current_club_name(self):
        return self.current_club_name

    def get_market_value_in_eur(self):
        return self.market_value_in_eur

    def get_highest_market_value_in_eur(self):
        return self.highest_market_value_in_eur

    def get_age(self):
        return self.age
    
    def get_mv_df(self):
        return self.market_value_in_eur_df


    # Obtain specific player's Goals, Assists, and G+A Dataframes
    def generate_player_stats_dfs(self):
        # Connect to the SQLite3 database
        conn = sqlite3.connect('transfermarkt.db')

        try:
            # **Player Statistics DataFrames**

            # Query the appearances table for the specified player_id
            query1 = "SELECT * FROM appearances WHERE player_id = ?"
            df_appearances = pd.read_sql_query(query1, conn, params=(self.player_id,))

            if not df_appearances.empty:
                # Clean up columns
                df_appearances = df_appearances.drop(columns=["index", "appearance_id", "game_id", "player_club_id", "player_current_club_id", "competition_id"])

                # Convert the 'date' column to datetime
                df_appearances['date'] = pd.to_datetime(df_appearances['date'], errors='coerce')

                # Extract year from the 'date' column
                df_appearances['year'] = df_appearances['date'].dt.year

                # Goals per year
                goals_per_year = df_appearances.groupby(['player_id', 'year'])['goals'].sum().reset_index()

                # Assists per year
                assists_per_year = df_appearances.groupby(['player_id', 'year'])['assists'].sum().reset_index()

                # Combine Goals and Assists
                ga_tmp = pd.merge(goals_per_year, assists_per_year, on="year")
                ga_per_year = ga_tmp.melt(id_vars=["year"], value_vars=["goals", "assists"], var_name="stat_type", value_name="value")

                # Red and Yellow Cards
                red_cards = df_appearances.groupby(['player_id', 'year'])['red_cards'].sum().reset_index()
                yellow_cards = df_appearances.groupby(['player_id', 'year'])['yellow_cards'].sum().reset_index()

                # Combine Card Data
                cards_tmp = pd.merge(red_cards, yellow_cards, on=["year", "player_id"])
                cards_per_year = cards_tmp.melt(id_vars=["year"], value_vars=["red_cards", "yellow_cards"], var_name="stat_type", value_name="value")
            else:
                goals_per_year = assists_per_year = ga_per_year = cards_per_year = None
                print("No data found for appearances for the specified player.")

            # **Market Value DataFrame**

            # Query the player_valuations table for the specified player_id
            query2 = "SELECT * FROM player_valuations WHERE player_id = ?"
            df_valuations = pd.read_sql_query(query2, conn, params=(self.player_id,))

            if not df_valuations.empty:
                # Rename columns for clarity
                df_valuations = df_valuations.rename(columns={'date': 'Date', 'market_value_in_eur': 'Market Value (Euros)', 'player_id': 'Player Id'})

                # Convert the 'Date' column to datetime type
                df_valuations['Date'] = pd.to_datetime(df_valuations['Date'], errors='coerce')

                # Extract the year from the 'Date' column
                df_valuations['Year'] = df_valuations['Date'].dt.year

                # Group by 'Year' and take the most recent market value for each year
                market_value_per_year = df_valuations.groupby('Year').agg({'Market Value (Euros)': 'max'}).reset_index()
            else:
                market_value_per_year = None
                print("No data found for player valuations for the specified player.")

            # Return all the DataFrames
            return goals_per_year, assists_per_year, ga_per_year, cards_per_year, market_value_per_year

        except Exception as e:
            print(f"An error occurred: {e}")
            return None

        finally:
            # Close the database connection
            conn.close()


    # Matplotlib [MPL] graph generation
    def generate_goals_mpl_graph(self):
        fig, ax = plt.subplots(figsize=(8, 5))

        # Create a bar graph for goals
        bars = ax.bar(self.goals_df['year'], self.goals_df['goals'], color='lightgreen', alpha=1.0, label='Goals')

        # Add values above the bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height,  # position of text (x, y)
                    f'{int(height)}', ha='center', va='bottom', fontsize=10)

        ax.set_title(f"{self.name}'s Goals Over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Goals', fontsize=12)
        ax.legend()
        ax.grid(True, axis='y', linestyle='--', alpha=1)

        # Set the x-ticks explicitly to show every year
        ax.set_xticks(self.goals_df['year'])
        
        # Rotate x-tick labels for readability
        plt.xticks(rotation=45)

        plt.tight_layout()  # Adjust layout to prevent overlap
        return fig
    

    def generate_assists_mpl_graph(self):
        fig, ax = plt.subplots(figsize=(8, 5))

        # Create a bar graph for assists
        bars = ax.bar(self.assists_df['year'], self.assists_df['assists'], color="skyblue", alpha=1.0, label='Assists')

        # Add values above the bars
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height,  # position of text (x, y)
                    f'{int(height)}', ha='center', va='bottom', fontsize=10)

        ax.set_title(f"{self.name}'s Assists Over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Assists', fontsize=12)
        ax.legend()
        ax.grid(True, axis='y', linestyle='--', alpha=1)

        # Set the x-ticks explicitly to show every year
        ax.set_xticks(self.assists_df['year'])

        # Rotate x-tick labels for readability
        plt.xticks(rotation=45)

        plt.tight_layout()  # Adjust layout to prevent overlap
        return fig
    

    def generate_ga_mpl_graph(self):
        # Pivot the DataFrame to get goals and assists in separate columns
        df_pivot = self.ga_df.pivot(index='year', columns='stat_type', values='value')

        # Plot the grouped bar graph
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars for goals and assists
        bars = df_pivot.plot(kind='bar', ax=ax, width=0.8, color=['lightgreen', 'skyblue'], alpha=1.0)

        # Add the values above the bars
        for p in bars.patches:
            height = p.get_height()
            ax.text(p.get_x() + p.get_width() / 2, height,  # position of text (x, y)
                    f'{int(height)}', ha='center', va='bottom', fontsize=10)

        ax.set_title(f"{self.name}'s Goals and Assists Over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Goals + Assists', fontsize=12)
        ax.legend(title='Stat Type', loc='upper left', fontsize=10)
        ax.grid(True, axis='y', linestyle='--', alpha=1)
        plt.xticks(rotation=45)
        plt.tight_layout()

        return fig
    

    def generate_cards_mpl_graph(self):
        # Pivot the DataFrame to get goals and assists in separate columns
        df_pivot = self.cards_df.pivot(index='year', columns='stat_type', values='value')

        # Plot the grouped bar graph
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars for goals and assists
        bars = df_pivot.plot(kind='bar', ax=ax, width=0.8, color=['red', 'yellow'], edgecolor='none', alpha=1.0)

        # Add the values above the bars
        for p in bars.patches:
            height = p.get_height()
            ax.text(p.get_x() + p.get_width() / 2, height,  # position of text (x, y)
                    f'{int(height)}', ha='center', va='bottom', fontsize=10)

        ax.set_title(f"{self.name}'s Cardss Over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Number of Cardings', fontsize=12)
        ax.legend(title='Stat Type', loc='upper left', fontsize=10)
        ax.grid(True, axis='y', linestyle='--', alpha=1)
        plt.xticks(rotation=45)
        plt.tight_layout()

        return fig
    
    # TODO: Fix this graph
    def generate_marketvalue_mpl_graph(self):
        fig, ax = plt.subplots(figsize=(8, 5))
        
        # Plot the market value line
        ax.plot(self.marketvalue_df['Year'], self.marketvalue_df['Market Value (Euros)'], 
                marker='o', linestyle='-', color='g', label='Market Value (Euros)')
        
        # Add the title and axis labels
        ax.set_title(f"{self.name}'s Market Value over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Market Value (Million Euros)', fontsize=12)
        ax.legend()
        ax.grid(True)

        # Annotate the data points with their values
        for year, value in zip(self.marketvalue_df['Year'], self.marketvalue_df['Market Value (Euros)']):
            ax.text(year, value + (value * 0.02),  # Slightly above the dot
                    f"{int(value):,}",  # Format as integer with commas
                    fontsize=10, ha='center', va='bottom')

        return fig


    # Plotly [PX] graph generation
    def generate_goals_graph_plotly(self, df):
        fig = px.bar(df, x="year", y="goals")
        return fig


    def generate_assists_graph_plotly(self, df):
        fig = px.bar(df, x="year", y="assists")
        return fig


    def generate_goals_assists_graph_plotly(self, df):
        fig = px.bar(df, x="year", y="value", color="stat_type",
                color_discrete_map={"goals": "red", "assists": "blue"},
                labels={"stat_type": "Statistic", "value": "Goals + Assists"})
        return fig


    def generate_cards_graph_plotly(self, df):
        fig = go.Figure()
        return fig


    def generate_marketvalue_graph_plotly(self, df):
        fig = px.line(df, x="Year", y="Market Value (Euros)")
        return fig