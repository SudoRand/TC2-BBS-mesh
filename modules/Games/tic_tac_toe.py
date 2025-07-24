# Tic Tac Toe game logic
# Adapted from https://github.com/VeggieVampire/MeshBoard/blob/c4b0a70357a54f018bf6c0629e9104ea627969ff/modules/Games/tic_tac_toe.py
import random

from utils import update_user_state, send_message

menu_name = "Tic Tac Toe"

def display_menu():
    return "Welcome to Tic Tac Toe!\n" \
           "1. Player vs Player\n" \
           "2. Player vs Computer\n" \
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

def render_board(board):
    """Render the game board as ASCII art with double underscores for empty cells."""
    formatted_board = [cell if cell != " " else "__" for cell in board]
    return f" {formatted_board[0]} | {formatted_board[1]} | {formatted_board[2]} \n" \
           "---+---+---\n" \
           f" {formatted_board[3]} | {formatted_board[4]} | {formatted_board[5]} \n" \
           "---+---+---\n" \
           f" {formatted_board[6]} | {formatted_board[7]} | {formatted_board[8]} "

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
    response = "Welcome to Tic Tac Toe!\nWhat would you like to do?\n[1] Player vs Player\n[2] Player vs Computer\nE[X]IT"
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
            response = f"Player vs Player mode selected.\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "2":
            game_state = init_game("pvc")
            response = f"Player vs Computer mode selected.\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        else:
            send_message("Invalid choice. Enter '1' for Player vs Player, '2' for Player vs Computer, or 'X' to exit.", sender_id, interface)

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
                update_user_state(sender_id, None)
                return

            if game["turns"] == 9:
                response = f"{render_board(game['board'])}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                send_message(response, sender_id, interface)
                update_user_state(sender_id, None)
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
                    update_user_state(sender_id, None)
                    return

                if game["turns"] == 9:
                    response = f"{render_board(game['board'])}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                    send_message(response, sender_id, interface)
                    update_user_state(sender_id, None)
                    return

                game["current_player"] = "X"
                response = f"{render_board(game['board'])}\n\nYour turn: X"
                send_message(response, sender_id, interface)

            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game})

        except ValueError:
            send_message("Invalid input! Enter a number between 1 and 9.", sender_id, interface)
