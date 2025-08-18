import json
from .game_interface import GameInterface
from .game_logic_driver import GameLogicDriver
from db_operations import get_active_games_for_player, get_open_games, get_game_by_id
from utils import update_user_state, send_message, get_node_short_name, get_node_id_from_num

menu_name = "Connect 4"
command_str = "CONNECT_FOUR"

# Unicode characters for the game pieces
PLAYER_X_CHAR = '🔴'
PLAYER_O_CHAR = '🟡'
EMPTY_CHAR = '⚫'

ROWS = 6
COLS = 7

INSTRUCTION_BOARD = (
    " 1  2  3  4  5  6  7 \n"
    "---------------------\n"
    "Enter a column number to drop your piece."
)

class ConnectFourGame(GameInterface):
    """
    The implementation of Connect 4, conforming to the GameInterface.
    """
    @property
    def game_type(self):
        return 'connect_four'

    def get_initial_board(self):
        return [[" " for _ in range(COLS)] for _ in range(ROWS)]

    def render_board(self, board, player_x_name=None, player_o_name=None):
        def get_char(symbol):
            if symbol == 'X':
                return PLAYER_X_CHAR
            if symbol == 'O':
                return PLAYER_O_CHAR
            return EMPTY_CHAR

        board_str = ""
        for r in range(ROWS - 1, -1, -1):
            board_str += " ".join([get_char(cell) for cell in board[r]]) + "\n"

        if player_x_name and player_o_name:
            board_str += f"\n{PLAYER_X_CHAR}: {player_x_name}\n{PLAYER_O_CHAR}: {player_o_name}"
        return board_str

    def get_instruction_board(self):
        return INSTRUCTION_BOARD

    def handle_move(self, board, move, player_symbol):
        try:
            col = int(move) - 1
        except ValueError:
            raise ValueError("Invalid move! Column must be a number.")

        if not (0 <= col < COLS):
            raise ValueError("Invalid move! Column must be between 1 and 7.")

        for r in range(ROWS):
            if board[r][col] == " ":
                board[r][col] = player_symbol
                return board

        raise ValueError("Invalid move! That column is full.")

    def check_winner(self, board):
        # Check horizontal
        for r in range(ROWS):
            for c in range(COLS - 3):
                if board[r][c] == board[r][c+1] == board[r][c+2] == board[r][c+3] and board[r][c] != " ":
                    return board[r][c]

        # Check vertical
        for c in range(COLS):
            for r in range(ROWS - 3):
                if board[r][c] == board[r+1][c] == board[r+2][c] == board[r+3][c] and board[r][c] != " ":
                    return board[r][c]

        # Check positive diagonal (/)
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                if board[r][c] == board[r+1][c+1] == board[r+2][c+2] == board[r+3][c+3] and board[r][c] != " ":
                    return board[r][c]

        # Check negative diagonal (\)
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                if board[r][c] == board[r-1][c+1] == board[r-2][c+2] == board[r-3][c+3] and board[r][c] != " ":
                    return board[r][c]

        if all(cell != " " for row in board for cell in row):
            return "draw"

        return None

def handle_connect_four_command(sender_id, interface):
    """
    Main entry point for the Connect 4 game.
    Displays open games to join and active games to continue.
    """
    game_instance = ConnectFourGame()
    driver = GameLogicDriver(game_instance, interface)
    driver.show_current_games(sender_id)

    menu = "\n[N]EW game.\n"
    menu += "E[X]IT."

    send_message(menu, sender_id, interface)
    update_user_state(sender_id, {'command': command_str, 'step': 1})

def handle_connect_four_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()

    game_instance = ConnectFourGame()
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
