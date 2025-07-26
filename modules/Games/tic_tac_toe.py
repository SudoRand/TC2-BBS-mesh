# Tic Tac Toe game logic
# Adapted from https://github.com/VeggieVampire/MeshBoard/blob/c4b0a70357a54f018bf6c0629e9104ea627969ff/modules/Games/tic_tac_toe.py
import random
import json

from db_operations import (
    create_tic_tac_toe_game,
    get_open_tic_tac_toe_games,
    join_tic_tac_toe_game,
    get_tic_tac_toe_game_by_id,
    update_tic_tac_toe_board,
    end_tic_tac_toe_game
)
from utils import update_user_state, send_message

menu_name = "Tic Tac Toe"

def display_menu():
    return "Welcome to Tic Tac Toe!\n" \
           "1. Player vs Player (Local)\n" \
           "2. Player vs Computer\n" \
           "3. Player vs Player (Remote)\n" \
           "'cd ..' to return to the main menu."

def init_game(mode):
    """Initialize a new game state."""
    return {
        "board": [" "] * 9,
        "current_player": "X",
        "winner": None,
        "turns": 0,
        "mode": mode
    }

def render_board(board, player_x=None, player_o=None):
    """Render the game board as ASCII art with double underscores for empty cells."""
    formatted_board = [cell if cell != " " else "__" for cell in board]
    board_str = f" {formatted_board[0]} | {formatted_board[1]} | {formatted_board[2]} \n" \
                "---+---+---\n" \
                f" {formatted_board[3]} | {formatted_board[4]} | {formatted_board[5]} \n" \
                "---+---+---\n" \
                f" {formatted_board[6]} | {formatted_board[7]} | {formatted_board[8]} "
    if player_x and player_o:
        board_str += f"\n\nX: {player_x}\nO: {player_o}"
    return board_str

def check_winner(board):
    """Check if there's a winner on the board."""
    winning_combinations = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6)
    ]
    for combo in winning_combinations:
        if board[combo[0]] == board[combo[1]] == board[combo[2]] and board[combo[0]] != " ":
            return board[combo[0]]
    return None

def computer_move(board):
    """Choose a move for the computer."""
    available_positions = [i for i, cell in enumerate(board) if cell == " "]
    return random.choice(available_positions)

def handle_tic_tac_toe_command(sender_id, interface):
    response = "Welcome to Tic Tac Toe!\nWhat would you like to do?\n[1] Player vs Player (Local)\n[2] Player vs Computer\n[3] Player vs Player (Remote)\nE[X]IT"
    send_message(response, sender_id, interface)
    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})

def handle_tic_tac_toe_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()
    if message == 'x':
        handle_help_command(sender_id, interface, 'games')
        return

    if step == 1:
        if message == "1":
            game_state = init_game("pvp")
            response = f"Player vs Player (Local) mode selected.\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "2":
            game_state = init_game("pvc")
            response = f"Player vs Computer mode selected.\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "3":
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 10})
            response = "Player vs Player (Remote) mode selected.\n[1] Start a new game\n[2] Join an existing game\nE[X]IT"
            send_message(response, sender_id, interface)
        else:
            send_message("Invalid choice. Enter '1', '2', or '3', or 'X' to exit.", sender_id, interface)

    elif step == 2:
        game = state['game']
        if game["winner"]:
            response = f"The game is over! Winner: {game['winner']}\n\n{render_board(game['board'])}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1}) # Go back to the beginning
            return

        try:
            position = int(message) - 1
            if position < 0 or position > 8:
                send_message("Invalid move! Choose a number between 1 and 9.", sender_id, interface)
                return
            if game["board"][position] != " ":
                send_message("That spot is already taken. Choose another.", sender_id, interface)
                return

            # Player move
            game["board"][position] = game["current_player"]
            game["turns"] += 1

            winner = check_winner(game["board"])
            if winner:
                game["winner"] = winner
                response = f"{render_board(game['board'])}\n\nCongratulations! {winner} wins!\n\nType 'X' to return to the games menu."
                send_message(response, sender_id, interface)
                return

            if game["turns"] == 9:
                response = f"{render_board(game['board'])}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                send_message(response, sender_id, interface)
                return

            if game["mode"] == "pvp":
                game["current_player"] = "O" if game["current_player"] == "X" else "X"
                response = f"{render_board(game['board'])}\n\nNext turn: {game['current_player']}"
                send_message(response, sender_id, interface)
            elif game["mode"] == "pvc":
                game["current_player"] = "O"
                computer_pos = computer_move(game["board"])
                game["board"][computer_pos] = "O"
                game["turns"] += 1

                winner = check_winner(game["board"])
                if winner:
                    game["winner"] = winner
                    response = f"{render_board(game['board'])}\n\nComputer wins!\n\nType 'X' to return to the games menu."
                    send_message(response, sender_id, interface)
                    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                    return

                if game["turns"] == 9:
                    response = f"{render_board(game['board'])}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                    send_message(response, sender_id, interface)
                    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                    return

                game["current_player"] = "X"
                response = f"{render_board(game['board'])}\n\nYour turn: X"
                send_message(response, sender_id, interface)

            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game})

        except ValueError:
            send_message("Invalid input! Enter a number between 1 and 9.", sender_id, interface)

    elif step == 10:  # Remote game options
        if message == "1":  # Start a new game
            game_id = create_tic_tac_toe_game(str(sender_id))
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id})
            response = f"New game started. Game ID: {game_id}. Waiting for an opponent to join."
            send_message(response, sender_id, interface)
        elif message == "2":  # Join an existing game
            games = get_open_tic_tac_toe_games()
            if not games:
                response = "No open games available to join. Why not start one?"
                send_message(response, sender_id, interface)
                # Optionally, loop back or exit
                return
            response = "Open games:\n"
            for game in games:
                response += f"ID: {game[0]}, Started by: {game[1]}\n"
            response += "\nEnter the ID of the game you want to join, or 'X' to exit."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 11})
        else:
            send_message("Invalid choice. Enter '1' to start a new game, '2' to join, or 'X' to exit.", sender_id, interface)

    elif step == 11:  # Joining a game
        try:
            game_id = int(message)
            join_tic_tac_toe_game(game_id, str(sender_id))
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id})
            response = f"Joined game {game_id}. It's your move if you are 'O'."
            send_message(response, sender_id, interface)
            # You might want to send a notification to the other player
        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)
        except Exception as e:
            send_message(f"Could not join game: {e}", sender_id, interface)

    elif step == 12:  # Remote game play
        game_id = state.get('game_id')
        if not game_id:
            # This can happen if the user types a message that is not a command
            # Let's check if the user is in a game
            # This is a bit of a hack, but it should work
            # A better solution would be to store the user's current game in the user state
            # and check that first
            send_message("You are not in a game. Type '3' to start or join a remote game.", sender_id, interface)
            return

        game_data = get_tic_tac_toe_game_by_id(game_id)
        if not game_data:
            send_message("Game not found.", sender_id, interface)
            return

        game_id, player_x, player_o, board_json, current_player, winner, status, _ = game_data
        board = json.loads(board_json)

        if status == 'finished':
            winner_name = player_x if winner == player_x else player_o
            response = f"{render_board(board, player_x, player_o)}\n\nGame over! Winner: {winner_name}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1}) # Go back to the beginning
            return

        if status == 'waiting':
            send_message("Waiting for another player to join...", sender_id, interface)
            return

        # It's a game in progress, let's show the board and who's turn it is
        current_player_name = player_x if current_player == player_x else player_o
        response = f"{render_board(board, player_x, player_o)}\n\nIt's {current_player_name}'s turn ({'X' if current_player == player_x else 'O'})."

        if str(sender_id) != current_player:
            response += "\nIt's not your turn."
            send_message(response, sender_id, interface)
            return

        send_message(response, sender_id, interface)

        try:
            position = int(message) - 1
            if not (0 <= position < 9 and board[position] == " "):
                send_message("Invalid move. Choose an empty space from 1-9.", sender_id, interface)
                return

            player_symbol = 'X' if sender_id == player_x else 'O'
            board[position] = player_symbol

            winner_symbol = check_winner(board)
            if winner_symbol:
                winner_id = current_player
                loser_id = player_o if current_player == player_x else player_x
                end_tic_tac_toe_game(game_id, winner_id)

                winner_name = player_x if winner_id == player_x else player_o
                win_response = f"{render_board(board, player_x, player_o)}\n\nCongratulations! You win!\n\nType 'X' to return to the games menu."
                lose_response = f"{render_board(board, player_x, player_o)}\n\nGame over. {winner_name} wins.\n\nType 'X' to return to the games menu."

                send_message(win_response, winner_id, interface)
                send_message(lose_response, loser_id, interface)

                update_user_state(winner_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                update_user_state(loser_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                return

            if " " not in board:
                end_tic_tac_toe_game(game_id, "draw")
                draw_response = f"{render_board(board, player_x, player_o)}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                send_message(draw_response, player_x, interface)
                send_message(draw_response, player_o, interface)
                update_user_state(player_x, {'command': 'TIC_TAC_TOE', 'step': 1})
                update_user_state(player_o, {'command': 'TIC_TAC_TOE', 'step': 1})
                return

            next_player = player_o if current_player == player_x else player_x
            update_tic_tac_toe_board(game_id, json.dumps(board), next_player)

            # Notify the current player that the other player has made a move
            response = f"{render_board(board, player_x, player_o)}\n\nYour opponent has made a move. It's your turn."
            send_message(response, next_player, interface)

            # Also send a message to the player who made the move
            response = f"{render_board(board, player_x, player_o)}\n\nMove made. Waiting for opponent."
            send_message(response, sender_id, interface)

        except ValueError:
            # The user might just be checking the board state
            # So we don't send an error message
            pass
