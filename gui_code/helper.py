from PIL import Image
from io import BytesIO
import requests
import sqlite3

def load_image_from_url(url):
    response = requests.get(url)
    image_data = BytesIO(response.content)
    return Image.open(image_data)


def get_player_names_list():
    # List to store player names
    player_names_list = []
    
    # Connect to the SQLite3 database
    conn = sqlite3.connect('transfermarkt.db')  # Replace 'transfermarkt.db' with your database file name
    cursor = conn.cursor()
    
    try:
        # Execute SQL query to retrieve all player names
        cursor.execute("SELECT name, current_club_id FROM players")
        rows = cursor.fetchall()  # Fetch all rows from the query result

        # Iterate through the rows and append names to the list
        for row in rows:
            player_names_list.append(row[0])  # Extract the name from the first column
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the database connection
        conn.close()
    
    sorted_player_names_list = sorted(player_names_list)

    return sorted_player_names_list


def get_league_names_list():
    """
    Retrieves a list of leagues (code and name) from the database,
    maps their IDs to full league names using a dictionary.
    
    Returns:
        List of tuples: Each tuple contains (league_code, league_name).
    """
    # Dictionary mapping league codes to full names
    league_name_mapping = {
        'BE1': 'Belgian Pro League',
        'DK1': 'Danish Superliga',
        'ES1': 'La Liga',
        'FR1': 'Ligue 1',
        'GB1': 'Premier League',
        'GR1': 'Greek Super League',
        'IT1': 'Serie A',
        'L1': 'Bundesliga',
        'NL1': 'Eredivisie',
        'PO1': 'Polish Ekstraklasa',
        'RU1': 'Russian Premier League',
        'SC1': 'Scottish Premiership',
        'TR1': 'Turkish Süper Lig',
        'UKR1': 'Ukrainian Premier League'
    }

    # List to store tuples of (league_code, league_name)
    league_names_list = []
    
    # Connect to the SQLite3 database
    conn = sqlite3.connect('transfermarkt.db')  # Replace with your database file name
    cursor = conn.cursor()
    
    try:
        # Execute SQL query to retrieve all domestic competition IDs (leagues)
        cursor.execute("SELECT DISTINCT domestic_competition_id FROM clubs")
        rows = cursor.fetchall()  # Fetch all unique rows from the query result

        # Iterate through the rows and map league codes to their names
        for row in rows:
            league_code = row[0]
            league_name = league_name_mapping.get(league_code, "Unknown League")  # Default to "Unknown League" if not in dictionary
            league_names_list.append((league_code, league_name))
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the database connection
        conn.close()
    
    # Sort the list by league name
    sorted_league_names_list = sorted(league_names_list, key=lambda x: x[1])

    return sorted_league_names_list


def get_club_names_list():
    """
    Retrieves a list of clubs along with their associated league codes.
    
    Returns:
        List of tuples: Each tuple contains (club_name, domestic_competition_id).
    """
    # List to store tuples of (club name, league code)
    club_names_list = []
    
    # Connect to the SQLite3 database
    conn = sqlite3.connect('transfermarkt.db')  # Replace with your database file name
    cursor = conn.cursor()
    
    try:
        # Execute SQL query to retrieve club names and their league codes
        cursor.execute("SELECT club_id, name, domestic_competition_id FROM clubs")  # Adjust table/column names as needed
        rows = cursor.fetchall()  # Fetch all rows from the query result

        # Iterate through the rows and append tuples to the list
        for row in rows:
            club_names_list.append((row[0], row[1]))  # (club_name, league_code)
        
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
    
    finally:
        # Close the database connection
        conn.close()
    
    # Remove duplicates and sort by club name
    unique_club_names_list = sorted(set(club_names_list), key=lambda x: x[0])

    return unique_club_names_list