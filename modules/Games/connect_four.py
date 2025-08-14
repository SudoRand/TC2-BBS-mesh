import json
from .game_interface import GameInterface
from .game_logic_driver import GameLogicDriver
from db_operations import get_active_games_for_player, get_game_by_id
from utils import update_user_state, send_message, get_node_short_name, get_node_id_from_num

menu_name = "Connect 4"

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

        # Header with column numbers
        board_str = " 1  2  3  4  5  6  7 \n"
        # Iterate rows in reverse to print top-down
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

        # If the loop completes, the column is full
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

        # Check for draw (no empty spaces left)
        if all(cell != " " for row in board for cell in row):
            return "draw"

        return None

    def get_computer_move(self, board):
        # Basic AI: Not implemented for Connect 4 in this version
        raise NotImplementedError("This game does not support a computer opponent.")

def init_local_game(mode):
    """Helper to initialize a local game state."""
    game_instance = ConnectFourGame()
    return {
        "board": game_instance.get_initial_board(),
        "current_player": "X",
        "winner": None,
        "turns": 0,
        "mode": mode
    }

def handle_connect_four_command(sender_id, interface):
    active_games = get_active_games_for_player('connect_four', str(sender_id))
    menu = f"Welcome to {menu_name}!\nWhat would you like to do?\n" \
           "[1] Player vs Player (Local)\n" \
           "[2] Player vs Player (Remote)\n"
    if active_games:
        menu += "[3] Continue Remote Game\n"
    menu += "E[X]IT"
    send_message(menu, sender_id, interface)
    update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 1})

def handle_connect_four_steps(sender_id, message, step, state, interface):
    from command_handlers import handle_help_command
    message = message.strip().lower()

    game_instance = ConnectFourGame()
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
            response = f"Player vs Player (Local) mode selected.\n\n{INSTRUCTION_BOARD}\n\n{game_instance.render_board(game_state['board'])}\n\n{PLAYER_X_CHAR} starts. Enter 1-7 to make your move."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 2, 'game': game_state})
        elif message == "2":
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 10})
            response = "Player vs Player (Remote) mode selected.\n[1] Start a new game\n[2] Join an existing game\nE[X]IT"
            send_message(response, sender_id, interface)
        elif message == "3" and get_active_games_for_player('connect_four', str(sender_id)):
            active_games = get_active_games_for_player('connect_four', str(sender_id))
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
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 13})
        else:
            send_message("Invalid choice. Please try again.", sender_id, interface)

    elif step == 2:  # Local PvP game loop
        game = state.get('game', {})
        if game.get("winner"):
            response = f"The game is over! Winner: {game['winner']}\n\n{game_instance.render_board(game['board'])}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 1})
            return

        try:
            game["board"] = game_instance.handle_move(game["board"], message, game["current_player"])
            game["turns"] += 1
            winner = game_instance.check_winner(game["board"])
            if winner:
                game["winner"] = winner
                winner_char = PLAYER_X_CHAR if winner == 'X' else PLAYER_O_CHAR
                win_msg = f"Congratulations! {winner_char} wins!"
                if winner == 'draw':
                    win_msg = "It's a draw!"
                response = f"{game_instance.render_board(game['board'])}\n\n{win_msg}\n\nType 'X' to return to the games menu."
                send_message(response, sender_id, interface)
                update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 1})
                return

            game["current_player"] = "O" if game["current_player"] == "X" else "X"
            next_player_char = PLAYER_O_CHAR if game["current_player"] == 'O' else PLAYER_X_CHAR
            response = f"{game_instance.render_board(game['board'])}\n\nNext turn: {next_player_char}"
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 2, 'game': game})
        except (ValueError, KeyError) as e:
            send_message(str(e), sender_id, interface)

    elif step == 10:  # Remote game options
        if message == "1":
            game_id = driver.start_new_game(sender_id)
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
        elif message == "2":
            driver.show_open_games(sender_id)
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 11})
        else:
            send_message("Invalid choice. Enter '1' or '2'.", sender_id, interface)

    elif step == 11:  # Joining a game
        game_id = driver.join_game_by_id(sender_id, message)
        if game_id:
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})

    elif step == 12:  # Remote game play
        driver.play_move(sender_id, message, state)

    elif step == 13: # Selecting a game to continue
        try:
            game_id = int(message)
            active_games = get_active_games_for_player('connect_four', str(sender_id))
            if game_id not in [g[0] for g in active_games]:
                send_message("Invalid game ID. Please choose from the list.", sender_id, interface)
                return
            update_user_state(sender_id, {'command': 'CONNECT_FOUR', 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
            driver.redisplay_game_board(sender_id, game_id)
        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, interface)
