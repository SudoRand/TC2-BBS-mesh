# Tic Tac Toe game logic
# Adapted from https://github.com/VeggieVampire/MeshBoard/blob/c4b0a70357a54f018bf6c0629e9104ea627969ff/modules/Games/tic_tac_toe.py
import random
import json

from db_operations import (
    create_tic_tac_toe_game,
    get_open_tic_tac_toe_games,
    get_active_tic_tac_toe_games_for_player,
    join_tic_tac_toe_game,
    get_tic_tac_toe_game_by_id,
    update_tic_tac_toe_board,
    end_tic_tac_toe_game
)
from utils import update_user_state, send_message, get_node_short_name, get_node_id_from_num

menu_name = "Tic Tac Toe"

INSTRUCTION_BOARD = (
    " 1 | 2 | 3 \n"
    "---+---+---\n"
    " 4 | 5 | 6 \n"
    "---+---+---\n"
    " 7 | 8 | 9 \n"
    "\n"
    "Move positions correspond to the numbers above."
)

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
    board_str = (f" {board[0]} | {board[1]} | {board[2]} \n" 
                "---+---+---\n" 
                f" {board[3]} | {board[4]} | {board[5]} \n" 
                "---+---+---\n" 
                f" {board[6]} | {board[7]} | {board[8]} ")
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

def redisplay_game_board(sender_id, game_id, interface):
    """Redisplays the game board and current prompt to a user returning to a game."""
    game_data = get_tic_tac_toe_game_by_id(game_id)
    if not game_data:
        send_message("Could not find your game. It may have ended.", sender_id, interface)
        from command_handlers import handle_help_command
        handle_help_command(sender_id, interface)
        return

    game_id, player_x, player_o, board_json, current_player, winner, status, _ = game_data
    board = json.loads(board_json)

    player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), interface), interface)
    player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), interface), interface) if player_o else None

    if status == 'finished':
        winner_name = player_x_sn if str(winner) == player_x else player_o_sn
        response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nGame over! Winner: {winner_name}\n\nType 'X' to return to the games menu."
        send_message(response, sender_id, interface)
        return

    if str(sender_id) == current_player:
        player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
        response = f"{INSTRUCTION_BOARD}\n\n{render_board(board, player_x_sn, player_o_sn)}\n\nIt's your turn ({player_symbol}). Enter 1-9 to make your move, or [M]enu to exit."
        send_message(response, sender_id, interface)
    elif player_o is None and str(sender_id) == player_x:
        response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nWaiting for an opponent to join. Or [M]enu to exit."
        send_message(response, sender_id, interface)
    else:
        response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nIt's not your turn. Or [M]enu to exit."
        send_message(response, sender_id, interface)

def handle_tic_tac_toe_command(sender_id, interface):
    active_games = get_active_tic_tac_toe_games_for_player(str(sender_id))
    menu = "Welcome to Tic Tac Toe!\nWhat would you like to do?\n" \
           "[1] Player vs Player (Local)\n" \
           "[2] Player vs Computer\n" \
           "[3] Player vs Player (Remote)\n"
    if active_games:
        menu += "[4] Continue Game\n"
    menu += "E[X]IT"
    send_message(menu, sender_id, interface)
    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})

def handle_tic_tac_toe_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()

    if message == 'm' and 'game_id' in state:
        game_id = state['game_id']
        new_state = {'command': 'MAIN_MENU', 'step': 1, 'active_game_id': game_id}
        update_user_state(sender_id, new_state)
        handle_help_command(sender_id, interface)
        return

    if message == 'x':
        handle_help_command(sender_id, interface, 'games')
        return

    if step == 1:
        if message == "1":
            game_state = init_game("pvp")
            response = f"Player vs Player (Local) mode selected.\n\n{INSTRUCTION_BOARD}\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "2":
            game_state = init_game("pvc")
            response = f"Player vs Computer mode selected.\n\n{INSTRUCTION_BOARD}\n\n{render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "3":
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 10})
            response = "Player vs Player (Remote) mode selected.\n[1] Start a new game\n[2] Join an existing game\nE[X]IT"
            send_message(response, sender_id, interface)
        elif message == "4":
            active_games = get_active_tic_tac_toe_games_for_player(str(sender_id))
            if not active_games:
                send_message("You have no active games to continue.", sender_id, interface)
                handle_tic_tac_toe_command(sender_id, interface)
                return

            response = "Your active games:\n"
            for game in active_games:
                game_id, player_x, player_o, status = game
                opponent_id = player_o if str(sender_id) == player_x else player_x
                opponent_sn = "Waiting..."
                if opponent_id:
                    opponent_node_id = get_node_id_from_num(int(opponent_id), interface)
                    opponent_sn = get_node_short_name(opponent_node_id, interface)

                response += f"ID: {game_id}, Opponent: {opponent_sn}, Status: {status}\n"

            response += "\nEnter the ID of the game you want to continue, or 'X' to exit."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 13})
        else:
            send_message("Invalid choice. Enter '1', '2', '3', or 'X' to exit.", sender_id, interface)

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
            game_data = get_tic_tac_toe_game_by_id(game_id)
            board = json.loads(game_data[3])
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            response = f"New game started. Game ID: {game_id}.\n\n{INSTRUCTION_BOARD}\n\n{render_board(board)}\nYou are X. Enter 1-9 to make your move, or [M]enu to exit."
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
                node_id = get_node_id_from_num(int(game[1]), interface)
                short_name = get_node_short_name(node_id, interface)
                response += f"ID: {game[0]}, Started by: {short_name}\n"
            response += "\nEnter the ID of the game you want to join, or 'X' to exit."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 11})
        else:
            send_message("Invalid choice. Enter '1' to start a new game, '2' to join, or 'X' to exit.", sender_id, interface)

    elif step == 11:  # Joining a game
        try:
            game_id = int(message)
            join_tic_tac_toe_game(game_id, str(sender_id))
            game_data = get_tic_tac_toe_game_by_id(game_id)
            if not game_data:
                send_message("Game not found after joining.", sender_id, interface)
                return

            game_id, player_x_id, player_o_id, board_json, _, _, _, _ = game_data
            board = json.loads(board_json)

            player_x_node_id = get_node_id_from_num(int(player_x_id), interface)
            player_o_node_id = get_node_id_from_num(int(player_o_id), interface)

            player_x_short_name = get_node_short_name(player_x_node_id, interface)
            player_o_short_name = get_node_short_name(player_o_node_id, interface)

            board_str = render_board(board, player_x_short_name, player_o_short_name)

            # Notify Player O (joiner)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            response_o = f"You joined game {game_id}.\n\n{INSTRUCTION_BOARD}\n\n{board_str}\nIt's your turn (O). Enter 1-9 to make your move, or [M]enu to exit."
            send_message(response_o, sender_id, interface)

        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)
        except Exception as e:
            send_message(f"Could not join game: {e}", sender_id, interface)

    elif step == 12:  # Remote game play
        game_id = state.get('game_id')
        if not game_id:
            send_message("You are not in a game. Type '3' to start or join a remote game.", sender_id, interface)
            return

        game_data = get_tic_tac_toe_game_by_id(game_id)
        if not game_data:
            send_message("Game not found.", sender_id, interface)
            return

        game_id, player_x, player_o, board_json, current_player, winner, status, _ = game_data
        board = json.loads(board_json)

        if status == 'finished':
            player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), interface), interface) if player_x else "Player X"
            player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), interface), interface) if player_o else "Player O"
            winner_name = player_x_sn if str(winner) == player_x else player_o_sn
            response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nGame over! Winner: {winner_name}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
            return

        if status == 'waiting':
            if str(sender_id) != player_x:
                send_message("Waiting for another player to join...", sender_id, interface)
                return

        try:
            position = int(message) - 1

            if str(sender_id) != current_player:
                send_message("It's not your turn.", sender_id, interface)
                return

            if not (0 <= position < 9 and board[position] == " "):
                send_message("Invalid move. Choose an empty space from 1-9.", sender_id, interface)
                return

            player_symbol = 'X' if str(sender_id) == player_x else 'O'
            board[position] = player_symbol

            player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), interface), interface)
            player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), interface), interface) if player_o else None

            winner_symbol = check_winner(board)
            if winner_symbol:
                winner_id = current_player
                end_tic_tac_toe_game(game_id, winner_id)

                winner_name = player_x_sn if str(winner_id) == player_x else player_o_sn
                loser_id = int(player_o) if str(current_player) == player_x else int(player_x)

                win_response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nCongratulations! You win!\n\nType 'X' to return to the games menu."
                lose_response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nGame over. {winner_name} wins.\n\nType 'X' to return to the games menu."

                send_message(win_response, int(winner_id), interface)
                send_message(lose_response, loser_id, interface)

                update_user_state(int(winner_id), {'command': 'TIC_TAC_TOE', 'step': 1})
                update_user_state(loser_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                return

            if " " not in board:
                end_tic_tac_toe_game(game_id, "draw")
                draw_response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
                send_message(draw_response, int(player_x), interface)
                if player_o:
                    send_message(draw_response, int(player_o), interface)
                update_user_state(int(player_x), {'command': 'TIC_TAC_TOE', 'step': 1})
                if player_o:
                    update_user_state(int(player_o), {'command': 'TIC_TAC_TOE', 'step': 1})
                return

            next_player = player_o if str(current_player) == player_x else player_x
            if status == 'waiting':
                next_player = None

            update_tic_tac_toe_board(game_id, json.dumps(board), next_player)

            # Notify Player X on Player O's first move
            if player_symbol == 'O' and board.count('O') == 1:
                player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), interface), interface)
                response_x = f"Player {player_o_sn} has joined your game!\n{render_board(board, player_x_sn, player_o_sn)}\nIt is your turn (X)."
                send_message(response_x, int(player_x), interface)
            elif next_player:
                response_other = f"{render_board(board, player_x_sn, player_o_sn)}\n\nYour opponent has made a move. It's your turn."
                send_message(response_other, int(next_player), interface)

            waiting_message = "Move made. Waiting for opponent."
            if next_player:
                opponent_sn = player_x_sn if str(next_player) == str(player_x) else player_o_sn
                opponent_symbol = 'X' if str(next_player) == str(player_x) else 'O'
                waiting_message = f"Move made. Waiting for opponent {opponent_sn} ({opponent_symbol})."

            response_self = f"{render_board(board, player_x_sn, player_o_sn)}\n\n{waiting_message}"
            send_message(response_self, sender_id, interface)

        except ValueError:
            player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), interface), interface)
            player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), interface), interface) if player_o else None

            if str(sender_id) == current_player:
                player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
                response = f"{INSTRUCTION_BOARD}\n\n{render_board(board, player_x_sn, player_o_sn)}\n\nIt's your turn ({player_symbol}). Enter 1-9 to make your move, or [M]enu to exit."
                send_message(response, sender_id, interface)
            elif player_o is None and str(sender_id) == player_x:
                 response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nWaiting for an opponent to join. Or [M]enu to exit."
                 send_message(response, sender_id, interface)
            else:
                response = f"{render_board(board, player_x_sn, player_o_sn)}\n\nIt's not your turn. Or [M]enu to exit."
                send_message(response, sender_id, interface)

    elif step == 13: # Selecting a game to continue
        try:
            game_id = int(message)
            # Basic validation to ensure the user is part of the game they're trying to continue
            active_games = get_active_tic_tac_toe_games_for_player(str(sender_id))
            if game_id not in [g[0] for g in active_games]:
                send_message("Invalid game ID. Please choose from the list.", sender_id, interface)
                return

            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            redisplay_game_board(sender_id, game_id, interface)

        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)
