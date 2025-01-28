from PIL import Image
from io import BytesIO
import requests
import sqlite3
import re

# def load_image_from_url(url):
#     response = requests.get(url)
#     image_data = BytesIO(response.content)
#     image = Image.open(image_data)
#     return image

def load_image_from_url(url):
    response = requests.get(url)
    image_data = BytesIO(response.content)
    image = Image.open(image_data)
    # Resize the image to 209x272
    resized_image = image.resize((209, 272))
    return resized_image


def get_player_names_list():
    # List to store player names
    player_names_list = []
    
    # Connect to the SQLite3 database
    conn = sqlite3.connect('transfermarkt.db') 
    cursor = conn.cursor()
    
    try:
        # Execute SQL query to retrieve all player names
        cursor.execute("SELECT name, current_club_id FROM filtered_players")
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


def replace_if_football_club_exists(string):
    options = ["Football Club", "Futbol Kulübü", "Futbolniy klub", "Futbol Klub", "Club de Fútbol", "Futebol Clube", "Futbol Club"]

    for option in options:
        if option in string:
            # Replace the original term with "FC" (case-insensitive)
            string = string.replace(option, "FC")

    if "Associazione Sportiva" in string:
        string = string.replace("Associazione Sportiva", "AS")

    if "Association sportive" in string:
        string = string.replace("Association sportive", "AS")

    if "Associazione Calcio" in string:
        string = string.replace("Associazione Calcio", "AC")

    if "S.p.a." or "S.p.A." in string.lower():
        string = re.sub(r"s\.p\.a\.", "", string, flags=re.IGNORECASE)

    if "Spor Kulübü" in string:
        string = string.replace("Spor Kulübü", "SK")

    if "Racing Club" in string:
        string = string.replace("Racing Club", "RC")

        
    return string