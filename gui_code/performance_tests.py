import unittest
import time
import pandas as pd
import matplotlib.pyplot as plt
from PlayerDashboardTab import PlayerDashboardTab
from customtkinter import CTk

class TestPlayerDashboardPerformance(unittest.TestCase):

    def setUp(self):
        # Set up a minimal CustomTkinter environment for testing
        self.app = CTk()
        self.dashboard = PlayerDashboardTab(self.app)

    def tearDown(self):
        # Destroy the app after each test
        self.app.destroy()

    def test_player_search_and_switch_time(self):
        test_player_names = [
            "Lionel Messi",
            "Cristiano Ronaldo",
            "Neymar",
            "Kylian Mbappé",
            "Kevin De Bruyne",
            "Erling Haaland",
            "Mohamed Salah",
            "Robert Lewandowski",
            "Virgil van Dijk",
            "Luka Modric",
            "Lamine Yamal",
            "Pedri",
            "Gavi",
            "Raphinha",
            "Frenkie de Jong",
            "Dani Olmo",
            "Alejandro Balde",
            "Wojciech Szczęsny",
            "Jules Koundé",
            "Ferran Torres",
            "Ansu Fati"

        ]

        total_time = 0
        results = []

        for player_name in test_player_names:
            start_time = time.time()

            # Simulate searching for a player
            self.dashboard.player_name_combobox.set(player_name)
            self.dashboard.get_player_info()

            end_time = time.time()
            elapsed_time = end_time - start_time
            total_time += elapsed_time

            print(f"Time to load player '{player_name}': {elapsed_time:.4f} seconds")
            results.append({"Player Name": player_name, "Time (s)": elapsed_time})

        # Create a DataFrame from the results
        df = pd.DataFrame(results)

        # Generate a graph
        plt.figure(figsize=(12, 6))
        plt.bar(df["Player Name"], df["Time (s)"], color="skyblue")
        plt.xlabel("Player Names")
        plt.ylabel("Time (seconds)")
        plt.title("Time Taken to Switch Players in Dashboard")
        plt.xticks(rotation=45, ha="right")
        plt.legend(["Time (s)"], loc="upper right")
        plt.tight_layout()
        plt.savefig("player_switch_times.png")
        plt.show()

        average_time = total_time / len(test_player_names)
        print(f"Average time to switch between players: {average_time:.4f} seconds")

        # Assert that the average time is within an acceptable threshold (e.g., 1 second)
        self.assertLess(average_time, 1.0, "Average time to switch players is too high.")

    def test_graph_loading_times(self):
        test_player_names = [
            "Lionel Messi",
            "Cristiano Ronaldo",
            "Neymar",
            "Kylian Mbappé",
            "Kevin De Bruyne",
            "Erling Haaland",
            "Mohamed Salah",
            "Robert Lewandowski",
            "Virgil van Dijk",
            "Luka Modric"
        ]

        graph_types = [
            "Goals",
            "Assists",
            "Goals + Assists",
            "Cards",
            "Market Value",
            "Appearances",
            "Appearances per Competition"
        ]

        results = []

        for player_name in test_player_names:
            self.dashboard.player_name_combobox.set(player_name)
            self.dashboard.get_player_info()

            for graph_type in graph_types:
                start_time = time.time()

                # Simulate graph generation
                self.dashboard.graph_type_combobox.set(graph_type)
                self.dashboard.update_graph(None)

                end_time = time.time()
                elapsed_time = end_time - start_time

                print(f"Time to load graph '{graph_type}' for player '{player_name}': {elapsed_time:.4f} seconds")
                results.append({"Player Name": player_name, "Graph Type": graph_type, "Time (s)": elapsed_time})

        # Create a DataFrame from the results
        df = pd.DataFrame(results)

        # Pivot the DataFrame for visualization
        pivot_df = df.pivot(index="Player Name", columns="Graph Type", values="Time (s)")

        # Generate a graph
        pivot_df.plot(kind="bar", figsize=(14, 8), width=0.8)
        plt.xlabel("Player Names")
        plt.ylabel("Time (seconds)")
        plt.title("Time Taken to Load Graphs for Each Player")
        plt.xticks(rotation=45, ha="right")
        plt.legend(title="Graph Types", loc="upper left")
        plt.tight_layout()
        plt.savefig("player_graph_loading_times.png")
        plt.show()

if __name__ == "__main__":
    unittest.main()
