import json
from .game_interface import GameInterface
from .game_logic_driver import GameLogicDriver
from db_operations import get_active_games_for_player, get_open_games, get_game_by_id
from utils import update_user_state, send_message, get_node_short_name, get_node_id_from_num

menu_name = "Tic Tac Toe"
command_str = "TIC_TAC_TOE"

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
            return "tie"

        return None

def handle_tic_tac_toe_command(sender_id, interface):
    """
    Main entry point for the Tic Tac Toe game.
    Displays open games to join and active games to continue.
    """
    game_instance = TicTacToeGame()
    driver = GameLogicDriver(game_instance, interface)
    driver.show_games_and_menu(sender_id, command_str)

def handle_tic_tac_toe_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()

    game_instance = TicTacToeGame()
    driver = GameLogicDriver(game_instance, interface)

    if message == 'x':
        game_id = state.get('game_id')
        new_state = {'command': 'MAIN_MENU', 'step': 1}
        if game_id:
            new_state['active_game_id'] = game_id
        update_user_state(sender_id, new_state)
        handle_help_command(sender_id, interface)
        return

    if step == 1: # Unified menu handler
        if message == 'n':
            board = game_instance.get_initial_board()
            send_message("New game started. Please make your first move.", sender_id, interface)
            send_message(game_instance.get_instruction_board(), sender_id, interface)
            send_message(game_instance.render_board(board), sender_id, interface)
            update_user_state(sender_id, {'command': command_str, 'step': 14, 'board': board})
        elif message == 's':
            driver.show_stats_menu(sender_id, command_str)
        elif message.isdigit():
            game_id = int(message)
            player_id_str = str(sender_id)

            all_active_games = get_active_games_for_player(game_instance.game_type, player_id_str)
            continuable_ids = [g[0] for g in all_active_games]

            open_games = get_open_games(game_instance.game_type)
            joinable_ids = [g[0] for g in open_games]

            if game_id in continuable_ids:
                update_user_state(sender_id, {'command': command_str, 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
                driver.redisplay_game_board(sender_id, game_id)
            elif game_id in joinable_ids:
                joined_id = driver.join_game_by_id(sender_id, str(game_id))
                if joined_id:
                    update_user_state(sender_id, {'command': command_str, 'step': 12, 'game_id': joined_id, 'active_game_id': joined_id})
            else:
                send_message("Invalid game ID.", sender_id, interface)
        else:
            send_message("Invalid choice. Please try again.", sender_id, interface)

    elif step == 2: # Stats menu
        if message == 'm':
            driver.show_player_stats(sender_id)
        elif message == 'a':
            driver.show_active_games(sender_id)
        elif message == 'l':
            driver.show_leaderboard(sender_id)
        elif message == 'x':
            driver.show_games_and_menu(sender_id, command_str)
        else:
            send_message("Invalid choice. Please try again.", sender_id, interface)

    elif step == 12:  # Remote game play
        driver.play_move(sender_id, message, state)

    elif step == 13: # Selecting a game to continue
        try:
            game_id = int(message)
            active_games = get_active_games_for_player(game_instance.game_type, str(sender_id))
            if game_id not in [g[0] for g in active_games]:
                send_message("Invalid game ID. Please choose from the list.", sender_id, interface)
                return
            update_user_state(sender_id, {'command': command_str, 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            driver.redisplay_game_board(sender_id, game_id)
        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)

    elif step == 14: # Player 1 makes the first move
        board = state.get('board')
        try:
            updated_board = game_instance.handle_move(board, message, 'X')
            game_id = driver.create_game_with_first_move(sender_id, updated_board)
            # The game is now created and waiting for P2. P1 is done for now.
            update_user_state(sender_id, {'command': 'MAIN_MENU', 'step': 1, 'active_game_id': game_id})
        except ValueError as e:
            send_message(f"Invalid move: {e}\nPlease try again.", sender_id, interface)
            # Keep the user at step 14 to let them re-enter their move.
            update_user_state(sender_id, state)
