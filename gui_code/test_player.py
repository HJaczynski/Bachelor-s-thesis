import pytest
from datetime import datetime
from Player import Player  # Replace with the actual module name containing your Player class


@pytest.fixture
def sample_player_data():
    """Fixture providing a sample player tuple."""
    return (
        3253,  # unique ID
        38253,  # player_id
        'Robert',  # first name
        'Lewandowski',  # last name
        'Robert Lewandowski',  # full name
        2024,  # year
        131,  # team_id
        'robert-lewandowski',  # slug
        'Poland',  # country_of_birth
        'Warszawa',  # city_of_birth
        'Poland',  # country_of_citizenship
        '1988-08-21 00:00:00',  # date_of_birth
        'Centre-Forward',  # position
        'Attack',  # field area
        'right',  # preferred foot
        185.0,  # height in meters
        '2026-06-30 00:00:00',  # contract_end_date
        'Gol International',  # sponsor
        'https://img.a.transfermarkt.technology/portrait/header/38253-1701118759.jpg?lm=1',  # image URL
        'https://www.transfermarkt.co.uk/robert-lewandowski/profil/spieler/38253',  # transfermarkt profile
        'ES1',  # league
        'Futbol Club Barcelona',  # club name
        15000000.0,  # current market value
        90000000.0  # highest market value
    )


@pytest.fixture
def player_instance(sample_player_data):
    """Fixture providing a Player instance."""
    return Player(sample_player_data)


def test_player_initialization(player_instance, sample_player_data):
    """Test initialization of the Player class."""
    assert player_instance.player_id == sample_player_data[1]
    assert player_instance.name == sample_player_data[4]
    assert player_instance.current_club_name == sample_player_data[21]
    assert player_instance.country_of_birth == sample_player_data[8]
    assert player_instance.age == datetime.now().year - 1988 - (
        (datetime.now().month, datetime.now().day) < (8, 21)
    )



def test_default_player_initialization():
    """Test initialization of the Player class with default values."""
    player = Player()
    assert player.name == "n/a"
    assert player.age == 0
    assert player.position == "n/a"


def test_getters(player_instance):
    """Test getter methods."""
    assert player_instance.get_player_id() == 38253
    assert player_instance.get_name() == "Robert Lewandowski"
    assert player_instance.get_position() == "Centre-Forward"
    assert player_instance.get_market_value_in_eur() == 15000000
    assert player_instance.get_highest_market_value_in_eur() == 90000000


def test_generate_player_stats_dfs(player_instance):
    """Test generation of player stats dataframes."""
    goals_df, assists_df, ga_df, cards_df, marketvalue_df = player_instance.generate_player_stats_dfs()

    assert goals_df is not None
    assert assists_df is not None
    assert ga_df is not None
    assert cards_df is not None
    assert marketvalue_df is not None


def test_generate_goals_mpl_graph(player_instance):
    """Test goals graph generation."""
    fig = player_instance.generate_goals_mpl_graph()
    assert fig is not None
    assert hasattr(fig, 'axes')


def test_generate_assists_mpl_graph(player_instance):
    """Test assists graph generation."""
    fig = player_instance.generate_assists_mpl_graph()
    assert fig is not None
    assert hasattr(fig, 'axes')


def test_generate_ga_mpl_graph(player_instance):
    """Test goals and assists graph generation."""
    fig = player_instance.generate_ga_mpl_graph()
    assert fig is not None
    assert hasattr(fig, 'axes')


def test_generate_cards_mpl_graph(player_instance):
    """Test cards graph generation."""
    fig = player_instance.generate_cards_mpl_graph()
    assert fig is not None
    assert hasattr(fig, 'axes')


def test_generate_marketvalue_mpl_graph(player_instance):
    """Test market value graph generation."""
    fig = player_instance.generate_marketvalue_mpl_graph()
    assert fig is not None
    assert hasattr(fig, 'axes')
