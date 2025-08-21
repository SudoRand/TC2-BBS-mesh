import logging
import sqlite3
import threading
import uuid
from datetime import datetime

from meshtastic import BROADCAST_NUM

from utils import (
    send_bulletin_to_bbs_nodes,
    send_delete_bulletin_to_bbs_nodes,
    send_delete_mail_to_bbs_nodes,
    send_mail_to_bbs_nodes, send_message, send_channel_to_bbs_nodes
)


thread_local = threading.local()

def get_db_connection():
    if not hasattr(thread_local, 'connection'):
        thread_local.connection = sqlite3.connect('bulletins.db')
    return thread_local.connection

def initialize_database():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS bulletins (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board TEXT NOT NULL,
                    sender_short_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    unique_id TEXT NOT NULL
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS mail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender TEXT NOT NULL,
                    sender_short_name TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    date TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    content TEXT NOT NULL,
                    unique_id TEXT NOT NULL
                );''')
    c.execute('''CREATE TABLE IF NOT EXISTS channels (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL
                );''')
    c.execute('''CREATE TABLE IF NOT EXISTS turn_based_games (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_type TEXT NOT NULL,
                    player_x TEXT,
                    player_o TEXT,
                    board TEXT,
                    current_player TEXT,
                    winner TEXT,
                    status TEXT,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    unique_id TEXT NOT NULL UNIQUE
                );''')
    conn.commit()
    print("Database schema initialized.")

def add_channel(name, url, bbs_nodes=None, interface=None):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("INSERT INTO channels (name, url) VALUES (?, ?)", (name, url))
    conn.commit()

    if bbs_nodes and interface:
        send_channel_to_bbs_nodes(name, url, bbs_nodes, interface)


def get_channels():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT name, url FROM channels")
    return c.fetchall()



def add_bulletin(board, sender_short_name, subject, content, bbs_nodes, interface, unique_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not unique_id:
        unique_id = str(uuid.uuid4())
    c.execute(
        "INSERT INTO bulletins (board, sender_short_name, date, subject, content, unique_id) VALUES (?, ?, ?, ?, ?, ?)",
        (board, sender_short_name, date, subject, content, unique_id))
    conn.commit()
    if bbs_nodes and interface:
        send_bulletin_to_bbs_nodes(board, sender_short_name, subject, content, unique_id, bbs_nodes, interface)

    # New logic to send group chat notification for urgent bulletins
    if board.lower() == "urgent":
        notification_message = f"💥NEW URGENT BULLETIN💥\nFrom: {sender_short_name}\nTitle: {subject}\nDM 'CB,,Urgent' to view"
        send_message(notification_message, BROADCAST_NUM, interface)

    return unique_id


def get_bulletins(board):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, subject, sender_short_name, date, unique_id FROM bulletins WHERE board = ? COLLATE NOCASE", (board,))
    return c.fetchall()

def get_bulletin_content(bulletin_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sender_short_name, date, subject, content, unique_id FROM bulletins WHERE id = ?", (bulletin_id,))
    return c.fetchone()


def delete_bulletin(bulletin_id, bbs_nodes, interface):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("DELETE FROM bulletins WHERE id = ?", (bulletin_id,))
    conn.commit()
    send_delete_bulletin_to_bbs_nodes(bulletin_id, bbs_nodes, interface)

def add_mail(sender_id, sender_short_name, recipient_id, subject, content, bbs_nodes, interface, unique_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    date = datetime.now().strftime('%Y-%m-%d %H:%M')
    if not unique_id:
        unique_id = str(uuid.uuid4())
    c.execute("INSERT INTO mail (sender, sender_short_name, recipient, date, subject, content, unique_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (sender_id, sender_short_name, recipient_id, date, subject, content, unique_id))
    conn.commit()
    if bbs_nodes and interface:
        send_mail_to_bbs_nodes(sender_id, sender_short_name, recipient_id, subject, content, unique_id, bbs_nodes, interface)
    return unique_id

def get_mail(recipient_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, sender_short_name, subject, date, unique_id FROM mail WHERE recipient = ?", (recipient_id,))
    return c.fetchall()

def get_mail_content(mail_id, recipient_id):
    # TODO: ensure only recipient can read mail
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sender_short_name, date, subject, content, unique_id FROM mail WHERE id = ? and recipient = ?", (mail_id, recipient_id,))
    return c.fetchone()

def delete_mail(unique_id, recipient_id, bbs_nodes, interface):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("SELECT recipient FROM mail WHERE unique_id = ?", (unique_id,))
        result = c.fetchone()
        if result is None:
            logging.error(f"No mail found with unique_id: {unique_id}")
            return  # Early exit if no matching mail found
        recipient_id = result[0]
        logging.info(f"Attempting to delete mail with unique_id: {unique_id} by {recipient_id}")
        c.execute("DELETE FROM mail WHERE unique_id = ? and recipient = ?", (unique_id, recipient_id,))
        conn.commit()
        send_delete_mail_to_bbs_nodes(unique_id, bbs_nodes, interface)
        logging.info(f"Mail with unique_id: {unique_id} deleted and sync message sent.")
    except Exception as e:
        logging.error(f"Error deleting mail with unique_id {unique_id}: {e}")
        raise


def get_sender_id_by_mail_id(mail_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT sender FROM mail WHERE id = ?", (mail_id,))
    result = c.fetchone()
    if result:
        return result[0]
    return None


# --- Generic Turn-Based Game Functions ---

def create_game(game_type, player_x, board_json, unique_id=None):
    conn = get_db_connection()
    c = conn.cursor()
    if not unique_id:
        unique_id = str(uuid.uuid4())

    # current_player is intentionally left NULL. It will be set when player_o joins.
    c.execute(
        "INSERT INTO turn_based_games (game_type, player_x, board, status, unique_id) VALUES (?, ?, ?, ?, ?)",
        (game_type, player_x, board_json, "waiting", unique_id)
    )
    conn.commit()
    return c.lastrowid

def get_open_games(game_type):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT id, player_x, unique_id FROM turn_based_games WHERE status = 'waiting' AND game_type = ?", (game_type,))
    return c.fetchall()

def get_waiting_games_for_creator(game_type, player_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, unique_id FROM turn_based_games
        WHERE status = 'waiting' AND game_type = ? AND player_x = ?
    """, (game_type, player_id))
    return c.fetchall()

def get_active_games_for_player(game_type, player_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, player_x, player_o, status, current_player
        FROM turn_based_games
        WHERE game_type = ? AND (player_x = ? OR player_o = ?) AND status IN ('waiting', 'in_progress')
    """, (game_type, player_id, player_id))
    return c.fetchall()

def get_active_games(limit=3):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT id, game_type, player_x, player_o FROM turn_based_games
        WHERE status = 'in_progress'
        ORDER BY last_activity DESC
        LIMIT ?
    """, (limit,))
    return c.fetchall()

def count_active_games():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM turn_based_games WHERE status = 'in_progress'")
    return c.fetchone()[0]

def join_game(game_id, player_o):
    conn = get_db_connection()
    c = conn.cursor()
    # When player_o joins, they become the current player and activity is updated.
    c.execute("UPDATE turn_based_games SET player_o = ?, status = 'in_progress', current_player = ?, last_activity = CURRENT_TIMESTAMP WHERE id = ?", (player_o, player_o, game_id))
    conn.commit()

def get_game_by_id(game_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM turn_based_games WHERE id = ?", (game_id,))
    return c.fetchone()

def update_game_board(game_id, board, current_player):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE turn_based_games SET board = ?, current_player = ?, last_activity = CURRENT_TIMESTAMP WHERE id = ?", (board, current_player, game_id))
    conn.commit()

def end_game(game_id, winner):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE turn_based_games SET winner = ?, status = 'finished' WHERE id = ?", (winner, game_id))
    conn.commit()

def get_player_stats(game_type, player_id):
    """
    Retrieves game statistics for a given player and game type.

    Args:
        game_type (str): The type of the game (e.g., 'tic_tac_toe').
        player_id (str): The ID of the player.

    Returns:
        list: A list of tuples, where each tuple contains (player_x, player_o, winner).
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT player_x, player_o, winner
        FROM turn_based_games
        WHERE game_type = ? AND (player_x = ? OR player_o = ?) AND status = 'finished'
    """, (game_type, player_id, player_id))
    return c.fetchall()

def get_all_finished_games(game_type):
    """
    Retrieves all finished games for a given game type.

    Args:
        game_type (str): The type of the game (e.g., 'tic_tac_toe').

    Returns:
        list: A list of tuples, where each tuple contains (player_x, player_o, winner).
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT player_x, player_o, winner
        FROM turn_based_games
        WHERE game_type = ? AND status = 'finished'
    """, (game_type,))
    return c.fetchall()

def get_active_games_by_type(game_type, limit=10):
    """
    Retrieves all active games for a given game type, ordered by last activity.

    Args:
        game_type (str): The type of the game.
        limit (int): The maximum number of games to retrieve.

    Returns:
        list: A list of tuples, each containing (player_x, player_o, last_activity).
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT player_x, player_o, last_activity
        FROM turn_based_games
        WHERE game_type = ? AND status = 'in_progress'
        ORDER BY last_activity DESC
        LIMIT ?
    """, (game_type, limit))
    return c.fetchall()

def count_active_games_by_type(game_type):
    """
    Counts all active games for a given game type.

    Args:
        game_type (str): The type of the game.

    Returns:
        int: The number of active games.
    """
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM turn_based_games WHERE game_type = ? AND status = 'in_progress'", (game_type,))
    return c.fetchone()[0]
