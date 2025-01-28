from datetime import datetime
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib import rcParams
import plotly.express as px
import plotly.graph_objects as go
from helper import replace_if_football_club_exists


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
            #self.date_of_birth = datetime.strptime(player_data[11], "%Y-%m-%d %H:%M:%S")
            self.date_of_birth = datetime.strptime(player_data[11], "%d/%m/%Y %H:%M")
            self.position = player_data[12]
            self.foot = player_data[14]
            self.height_in_meters = player_data[15] / 100  # Convert height to meters
            self.player_image_url = player_data[18]
            self.current_club_logo_url = f"https://tmssl.akamaized.net//images/wappen/head/{self.current_club_id}.png"
            self.player_transfermarkt_url = player_data[19]
            #self.current_club_name = player_data[21]
            self.current_club_name = replace_if_football_club_exists(player_data[21])
            self.market_value_in_eur = player_data[22]
            self.highest_market_value_in_eur = player_data[23]
            self.goals_df, self.assists_df, self.ga_df, self.cards_df, self.marketvalue_df, self.appearances_per_year_df, self.appearances_per_competition_df = self.generate_player_stats_dfs()

            # Calculate age based on date of birth
            current_date = datetime.now()
            self.age = current_date.year - self.date_of_birth.year - (
                (current_date.month, current_date.day) < (self.date_of_birth.month, self.date_of_birth.day)
            )
        else:
            # Default values for the player if no player_data is provided
            self.player_id = 0
            self.name = "Not Applicable"
            self.current_club_id = 0
            self.country_of_birth = "Not Applicable"
            self.city_of_birth = "Not Applicable"
            self.country_of_citizenship = "Not Applicable"
            self.date_of_birth = datetime(1900, 1, 1)  # Set to a placeholder date
            self.position = "Not Applicable"
            self.foot = "Not Applicable"
            self.height_in_meters = 0.0
            self.player_image_url = "https://img.a.transfermarkt.technology/portrait/header/default.jpg?lm=1"
            self.current_club_logo_url = "https://tmssl.akamaized.net//images/wappen/homepageWappen150x150/515.png?lm=1456997255"
            self.player_transfermarkt_url = "https://www.transfermarkt.pl/"
            self.current_club_name = "Not Applicable"
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
            # f"Name:                   {self.name}\n"
            # f"Date of Birth (Age):    {self.date_of_birth.strftime('%d/%m/%Y')} ({self.age})\n"
            # f"Country of Birth:       {self.country_of_birth}\n"
            # f"City of Birth:          {self.city_of_birth}\n"
            # f"Country of Citizenship: {self.country_of_citizenship}\n"
            # f"Position:               {self.position}\n"
            # f"Preferred Foot:         {self.foot}\n"
            # f"Height:                 {self.height_in_meters} meters\n"
            # f"Current Club:           {self.current_club_name}\n"
            # f"Market Value:           €{self.market_value_in_eur:,.0f}\n"
            # f"Highest Market Value:   €{self.highest_market_value_in_eur:,.0f}"
            f"{self.name}\n"
            f"{self.date_of_birth.strftime('%d/%m/%Y')} ({self.age})\n"
            f"{self.country_of_birth}\n"
            f"{self.city_of_birth}\n"
            f"{self.country_of_citizenship}\n"
            f"{self.position}\n"
            f"{self.foot}\n"
            f"{self.height_in_meters} meters\n"
            f"{self.current_club_name}\n"
            f"€{self.market_value_in_eur:,.0f}\n"
            f"€{self.highest_market_value_in_eur:,.0f}"
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
                df_appearances = df_appearances.drop(columns=["index", "appearance_id", "game_id", "player_club_id", "player_current_club_id"])

                # Convert the 'date' column to datetime
                df_appearances['date'] = pd.to_datetime(df_appearances['date'], errors='coerce')

                # Extract year from the 'date' column
                df_appearances['year'] = df_appearances['date'].dt.year

                # Appearances per year
                df_appearances_per_year = df_appearances.groupby(['player_id', 'year']).size().reset_index(name='Appearances')

                # Appearances per competition per year
                df_appearances_per_competition_per_year = df_appearances.groupby(['player_id', 'year', 'competition_id']).size().reset_index(name='Appearances')

                # Goals per year
                goals_per_year = df_appearances.groupby(['player_id', 'year'])['goals'].sum().reset_index()
                goals_per_year.rename(columns={'goals': 'Goals'}, inplace=True)

                # Assists per year
                assists_per_year = df_appearances.groupby(['player_id', 'year'])['assists'].sum().reset_index()
                assists_per_year.rename(columns={'assists': 'Assists'}, inplace=True)

                # Combine Goals and Assists
                ga_tmp = pd.merge(goals_per_year, assists_per_year, on="year")
                ga_per_year = ga_tmp.melt(id_vars=["year"], value_vars=["Goals", "Assists"], var_name="Stat Type", value_name="value")

                # Red and Yellow Cards
                red_cards = df_appearances.groupby(['player_id', 'year'])['red_cards'].sum().reset_index()
                yellow_cards = df_appearances.groupby(['player_id', 'year'])['yellow_cards'].sum().reset_index()

                # Combine Card Data
                cards_tmp = pd.merge(red_cards, yellow_cards, on=["year", "player_id"])

                # Rename Columns
                cards_tmp = cards_tmp.rename(columns={"red_cards": "Red Cards", "yellow_cards": "Yellow Cards"})

                cards_per_year = cards_tmp.melt(id_vars=["year"], value_vars=["Red Cards", "Yellow Cards"], var_name="Stat Type", value_name="value")
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
            return goals_per_year, assists_per_year, ga_per_year, cards_per_year, market_value_per_year, df_appearances_per_year, df_appearances_per_competition_per_year

        except Exception as e:
            print(f"An error occurred: {e}")
            return None

        finally:
            # Close the database connection
            conn.close()


    # Matplotlib [MPL] graph generation
    def generate_goals_mpl_graph(self):
        rcParams['font.family'] = 'Calibri'
        fig, ax = plt.subplots(figsize=(8, 5))

        # Create a bar graph for goals
        bars = ax.bar(self.goals_df['year'], self.goals_df['Goals'], color='lightgreen', alpha=1.0, label='Goals')

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
        ax.set_ylim(bottom=0)
        
        # Rotate x-tick labels for readability
        plt.xticks(rotation=45)

        plt.tight_layout()  # Adjust layout to prevent overlap
        return fig
    

    def generate_assists_mpl_graph(self):
        fig, ax = plt.subplots(figsize=(8, 5))

        # Create a bar graph for assists
        bars = ax.bar(self.assists_df['year'], self.assists_df['Assists'], color="skyblue", alpha=1.0, label='Assists')

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
        ax.set_ylim(bottom=0)

        # Rotate x-tick labels for readability
        plt.xticks(rotation=45)

        plt.tight_layout()  # Adjust layout to prevent overlap
        return fig
    

    def generate_ga_mpl_graph(self):
        # Pivot the DataFrame to get goals and assists in separate columns
        df_pivot = self.ga_df.pivot(index='year', columns='Stat Type', values='value')

        # Plot the grouped bar graph
        fig, ax = plt.subplots(figsize=(10, 6))

        # Create bars for goals and assists
        bars = df_pivot.plot(kind='bar', ax=ax, width=0.8, color=['skyblue', 'lightgreen'], alpha=1.0)

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
        ax.set_ylim(bottom=0)
        plt.tight_layout()

        return fig
    

    def generate_cards_mpl_graph(self):
        # Pivot the DataFrame to get goals and assists in separate columns
        df_pivot = self.cards_df.pivot(index='year', columns='Stat Type', values='value')

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
        ax.set_ylim(bottom=0)
        plt.tight_layout()

        return fig
    

    def generate_appearances_per_year_mpl_graph(self):
        # Pivoting the dataframe
        df_pivot = self.appearances_per_year_df.pivot(index="year", columns="player_id", values="Appearances").fillna(0)

        # Creating the plot
        fig, ax = plt.subplots(figsize=(12, 8))
        bars = df_pivot.plot(kind="bar", stacked=False, ax=ax, width=0.8, legend=False, color="#9467bd")

        # Add values above the bars
        for container in ax.containers:
            ax.bar_label(container, fmt='%d', label_type='edge', fontsize=10)

        # Customizing the plot
        ax.set_title(f"{self.name}'s Total Appearances by Year", fontsize=16)
        ax.set_xlabel("Year", fontsize=14)
        ax.set_ylabel("Number of Appearances", fontsize=14)
        ax.set_xticks(range(len(df_pivot.index)))
        ax.set_xticklabels(df_pivot.index, rotation=45, fontsize=12)
        ax.grid(axis="y", linestyle="--", alpha=1)
        #ax.legend(title="Player ID", fontsize=12)
        plt.tight_layout()

        # Return the figure object
        return fig

    def generate_appearances_per_competition_mpl_graph(self):
        # Pivoting the dataframe for a grouped bar chart
        pivot_df = self.appearances_per_competition_df.pivot(index="year", columns="competition_id", values="Appearances").fillna(0)

        # Creating the plot
        fig, ax = plt.subplots(figsize=(12, 8))
        bars = pivot_df.plot(kind="bar", stacked=False, ax=ax, width=0.8, legend=False)

        # Add values above the bars
        for container in ax.containers:
            ax.bar_label(container, fmt='%d', label_type='edge', fontsize=10, labels=[int(label) if label > 0 else '' for label in container.datavalues])

        # Customizing the plot
        ax.set_title(f"{self.name}'s Appearances per Competition by Year", fontsize=16)
        ax.set_xlabel("Year", fontsize=14)
        ax.set_ylabel("Number of Appearances", fontsize=14)
        ax.set_xticks(range(len(pivot_df.index)))
        ax.set_ylim(bottom=0)
        ax.set_xticklabels(pivot_df.index, rotation=45, fontsize=12)
        ax.legend(title="Competition", fontsize=12)
        ax.grid(axis="y", linestyle="--", alpha=1)
        plt.tight_layout()

        # Return the figure object
        return fig


    # TODO: Fix this graph
    def generate_marketvalue_mpl_graph(self):
        fig, ax = plt.subplots(figsize=(8, 5))

        # Scale Market Value to millions
        self.marketvalue_df['Market Value (Million Euros)'] = self.marketvalue_df['Market Value (Euros)'] / 1e6
        
        # Plot the market value line
        ax.plot(self.marketvalue_df['Year'], self.marketvalue_df['Market Value (Million Euros)'], 
                marker='o', linestyle='-', color='g', label='Market Value (Million Euros)')
        
        # Add the title and axis labels
        ax.set_title(f"{self.name}'s Market Value over the Years", fontsize=14)
        ax.set_xlabel('Year', fontsize=12)
        ax.set_ylabel('Market Value (Million Euros)', fontsize=12)
        ax.legend()
        ax.grid(True)
        ax.set_ylim(bottom=0)

        # Annotate the data points with their values, ensuring they don't overlap
        for year, value in zip(self.marketvalue_df['Year'], self.marketvalue_df['Market Value (Million Euros)']):
            ax.text(year, value + (0.2 if value > 0 else -0.2),  # Adjust annotation position
                    f"{value:.1f}",  # Format to 1 decimal place
                    fontsize=10, ha='center', va='bottom', 
                    bbox=dict(facecolor='white', edgecolor='none', alpha=0.7))  # Add background to text
        
        return fig


    # Plotly [PX] graph generation
    def generate_goals_graph_plotly(self):
        fig = px.bar(self.goals_df, x="year", y="Goals", 
                    title=f"{self.name}'s Goals Over the Years")
        
        # Update the bar color to light green
        fig.update_traces(marker_color='lightgreen')
        return fig


    def generate_assists_graph_plotly(self):
        fig = px.bar(self.assists_df, x="year", y="Assists", 
                    title=f"{self.name}'s Assists Over the Years")
        
        # Update the bar color to sky blue
        fig.update_traces(marker_color='skyblue')
        return fig


    def generate_goals_assists_graph_plotly(self):
        fig = px.bar(self.ga_df, x="year", y="value", color="Stat Type",
                    color_discrete_map={"goals": "lightgreen", "assists": "skyblue"},
                    labels={"Stat Type": "Statistic", "value": "Value"},
                    title=f"{self.name}'s Goals and Assists Over the Years")
        return fig


    def generate_cards_graph_plotly(self):
        # Pivot the DataFrame to get 'Red Cards' and 'Yellow Cards' in separate columns
        df_pivot = self.cards_df.pivot(index='year', columns='Stat Type', values='value').reset_index()

        # Create a grouped bar chart with Plotly
        fig = go.Figure()

        # Add Red Cards
        fig.add_trace(go.Bar(
            x=df_pivot['year'],
            y=df_pivot['Red Cards'],
            name='Red Cards',
            marker_color='red'
        ))

        # Add Yellow Cards
        fig.add_trace(go.Bar(
            x=df_pivot['year'],
            y=df_pivot['Yellow Cards'],
            name='Yellow Cards',
            marker_color='yellow'
        ))

        # Update layout for styling and titles
        fig.update_layout(
            title=f"{self.name}'s Cards Over the Years",
            xaxis_title="Year",
            yaxis_title="Number of Cards",
            barmode='group',  # Grouped bars
            legend_title="Card Type",
            template="plotly_white"  # Optional: clean background style
        )

        # Improve spacing and readability
        fig.update_xaxes(tickangle=45)
        fig.update_yaxes(gridcolor='lightgray')

        return fig


    def generate_marketvalue_graph_plotly(self):
        fig = px.line(self.marketvalue_df, x="Year", y="Market Value (Euros)",
                    title=f"{self.name}'s Market Value Over the Years")
        
        # Update line color to red
        fig.update_traces(line=dict(color='red'))
        
        return fig
    

    def generate_appearances_per_year_plotly(self):
        # Pivoting the dataframe
        df_pivot = self.appearances_per_year_df.pivot(index="year", columns="player_id", values="Appearances").fillna(0)

        # Creating the plot
        fig = go.Figure()
        for player_id in df_pivot.columns:
            fig.add_trace(go.Bar(
                x=df_pivot.index,
                y=df_pivot[player_id],
                name=f"Player {player_id}"
            ))

        # Customizing the plot
        fig.update_layout(
            title=f"{self.name}'s Total Appearances by Year",
            xaxis_title="Year",
            yaxis_title="Number of Appearances",
            barmode="group",
            legend_title="Player ID",
            xaxis=dict(tickmode='linear'),
        )

        return fig

    def generate_appearances_per_competition_plotly(self):
        # Pivoting the dataframe for a grouped bar chart
        pivot_df = self.appearances_per_competition_df.pivot(index="year", columns="competition_id", values="Appearances").fillna(0)

        # Creating the plot
        fig = go.Figure()
        for competition_id in pivot_df.columns:
            fig.add_trace(go.Bar(
                x=pivot_df.index,
                y=pivot_df[competition_id],
                name=f"Competition {competition_id}"
            ))

        # Customizing the plot
        fig.update_layout(
            title=f"{self.name}'s Appearances per Competition by Year",
            xaxis_title="Year",
            yaxis_title="Number of Appearances",
            barmode="group",
            legend_title="Competition",
            xaxis=dict(tickmode='linear'),
        )

        return fig

