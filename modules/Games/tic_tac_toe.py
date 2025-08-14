import random
import json
from .game_interface import GameInterface
from .game_logic_driver import GameLogicDriver
from db_operations import get_active_games_for_player, get_game_by_id
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

class TicTacToeGame(GameInterface):
    """
    The implementation of Tic-Tac-Toe, conforming to the GameInterface.
    """
    @property
    def game_type(self):
        return 'tic_tac_toe'

    def get_initial_board(self):
        return [" "] * 9

    def render_board(self, board, player_x_name=None, player_o_name=None):
        board_str = (f" {board[0]} | {board[1]} | {board[2]} \n"
                    "---+---+---\n"
                    f" {board[3]} | {board[4]} | {board[5]} \n"
                    "---+---+---\n"
                    f" {board[6]} | {board[7]} | {board[8]} ")
        if player_x_name and player_o_name:
            board_str += f"\n\nX: {player_x_name}\nO: {player_o_name}"
        return board_str

    def get_instruction_board(self):
        return INSTRUCTION_BOARD

    def handle_move(self, board, move, player_symbol):
        try:
            position = int(move) - 1
            if not (0 <= position < 9):
                raise ValueError("Position must be between 1 and 9.")
            if board[position] != " ":
                raise ValueError("That spot is already taken.")

            board[position] = player_symbol
            return board
        except (ValueError, IndexError):
            raise ValueError("Invalid move! Choose an empty number between 1 and 9.")

    def check_winner(self, board):
        winning_combinations = [
            (0, 1, 2), (3, 4, 5), (6, 7, 8),
            (0, 3, 6), (1, 4, 7), (2, 5, 8),
            (0, 4, 8), (2, 4, 6)
        ]
        for combo in winning_combinations:
            if board[combo[0]] == board[combo[1]] == board[combo[2]] and board[combo[0]] != " ":
                return board[combo[0]]

        if " " not in board:
            return "draw"

        return None

    def get_computer_move(self, board):
        available_positions = [i for i, cell in enumerate(board) if cell == " "]
        return str(random.choice(available_positions) + 1)

def init_local_game(mode):
    """Helper to initialize a local game state."""
    return {
        "board": [" "] * 9,
        "current_player": "X",
        "winner": None,
        "turns": 0,
        "mode": mode
    }

def handle_tic_tac_toe_command(sender_id, interface):
    active_games = get_active_games_for_player('tic_tac_toe', str(sender_id))
    menu = "Welcome to Tic Tac Toe!\nWhat would you like to do?\n" \
           "[1] Player vs Player (Local)\n" \
           "[2] Player vs Computer\n" \
           "[3] Player vs Player (Remote)\n"
    if active_games:
        menu += "[4] Continue Remote Game\n"
    menu += "E[X]IT"
    send_message(menu, sender_id, interface)
    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})

def handle_tic_tac_toe_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()

    game_instance = TicTacToeGame()
    driver = GameLogicDriver(game_instance, interface)

    if message == 'x' and 'game_id' in state:
        game_id = state['game_id']
        new_state = {'command': 'MAIN_MENU', 'step': 1, 'active_game_id': game_id}
        update_user_state(sender_id, new_state)
        handle_help_command(sender_id, interface)
        return

    if step == 1:
        if message == "1":
            game_state = init_local_game("pvp")
            response = f"Player vs Player (Local) mode selected.\n\n{INSTRUCTION_BOARD}\n\n{game_instance.render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "2":
            game_state = init_local_game("pvc")
            response = f"Player vs Computer mode selected.\n\n{INSTRUCTION_BOARD}\n\n{game_instance.render_board(game_state['board'])}\n\nX starts. Enter 1-9 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game_state})
        elif message == "3":
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 10})
            response = "Player vs Player (Remote) mode selected.\n[1] Start a new game\n[2] Join an existing game\nE[X]IT"
            send_message(response, sender_id, interface)
        elif message == "4":
            active_games = get_active_games_for_player('tic_tac_toe', str(sender_id))
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
            send_message("Invalid choice. Please try again.", sender_id, interface)

    elif step == 2:  # Local PvP and PvC game loop
        game = state.get('game', {})
        if game.get("winner"):
            response = f"The game is over! Winner: {game['winner']}\n\n{game_instance.render_board(game['board'])}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
            return

        try:
            game["board"] = game_instance.handle_move(game["board"], message, game["current_player"])
            game["turns"] += 1
            winner = game_instance.check_winner(game["board"])
            if winner:
                game["winner"] = winner
                win_msg = f"Congratulations! {winner} wins!"
                if game['mode'] == 'pvc' and winner == 'O':
                    win_msg = "Computer wins!"
                response = f"{game_instance.render_board(game['board'])}\n\n{win_msg}\n\nType 'X' to return to the games menu."
                send_message(response, sender_id, interface)
                update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                return

            if game["mode"] == "pvp":
                game["current_player"] = "O" if game["current_player"] == "X" else "X"
                response = f"{game_instance.render_board(game['board'])}\n\nNext turn: {game['current_player']}"
                send_message(response, sender_id, interface)
            elif game["mode"] == "pvc":
                computer_move = game_instance.get_computer_move(game['board'])
                game["board"] = game_instance.handle_move(game['board'], computer_move, "O")
                game["turns"] += 1
                winner = game_instance.check_winner(game["board"])
                if winner:
                    game["winner"] = winner
                    response = f"{game_instance.render_board(game['board'])}\n\nComputer wins!\n\nType 'X' to return to the games menu."
                    send_message(response, sender_id, interface)
                    update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 1})
                    return
                response = f"{game_instance.render_board(game['board'])}\n\nYour turn: X"
                send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 2, 'game': game})
        except (ValueError, KeyError) as e:
            send_message(str(e), sender_id, interface)

    elif step == 10:  # Remote game options
        if message == "1":
            game_id = driver.start_new_game(sender_id)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
        elif message == "2":
            driver.show_open_games(sender_id)
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 11})
        else:
            send_message("Invalid choice. Enter '1' or '2'.", sender_id, interface)

    elif step == 11:  # Joining a game
        game_id = driver.join_game_by_id(sender_id, message)
        if game_id:
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})

    elif step == 12:  # Remote game play
        driver.play_move(sender_id, message, state)

    elif step == 13: # Selecting a game to continue
        try:
            game_id = int(message)
            active_games = get_active_games_for_player('tic_tac_toe', str(sender_id))
            if game_id not in [g[0] for g in active_games]:
                send_message("Invalid game ID. Please choose from the list.", sender_id, interface)
                return
            update_user_state(sender_id, {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            driver.redisplay_game_board(sender_id, game_id)
        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)
