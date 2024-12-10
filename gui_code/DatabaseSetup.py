import os
import sqlite3
import pandas as pd

cwd = os.getcwd()
path = os.path.join(cwd, "gui_code/Transfermarkt Data\\")
print(path)

filenames = ['appearances', 'club_games', 'clubs', 'game_events', 'game_lineups', 'games', 'player_valuations', 'players', 'transfers']

for fn in filenames:
    filename = f'{path}{fn}.csv'

    # Step 1. Load data files
    df = pd.read_csv(filename)

    # Step 2. Data clean up
    df.columns = df.columns.str.strip()

    # Step 3. Create / Connect to a SQLite database
    connection = sqlite3.connect('transfermarkt.db')

    # Step 4. Load data file to SQLite
    df.to_sql(fn, connection, if_exists='replace')

    print(f'[{fn}] loaded into database!')