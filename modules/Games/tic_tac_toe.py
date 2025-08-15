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
            return "draw"

        return None

    def get_computer_move(self, board):
        raise NotImplementedError("This game does not support a computer opponent.")

def handle_tic_tac_toe_command(sender_id, interface):
    """
    Main entry point for the Tic Tac Toe game.
    Displays open games and options to start a new one or continue.
    """
    game_instance = TicTacToeGame()

    open_games = get_open_games(game_instance.game_type)
    active_games = get_active_games_for_player(game_instance.game_type, str(sender_id))

    menu = f"Welcome to {menu_name}!\n\n"
    if open_games:
        menu += "Join an open game by entering its ID:\n"
        for game_id, player_x_id, _ in open_games:
            node_id = get_node_id_from_num(int(player_x_id), interface)
            short_name = get_node_short_name(node_id, interface) if node_id else f"Unknown ({player_x_id})"
            menu += f"ID: {game_id}, Started by: {short_name}\n"
    else:
        menu += "No open games to join.\n"

    menu += "\nOr [N]EW to create a new one.\n"

    if any(g[3] in ('in_progress', 'waiting') for g in active_games):
        menu += "Or [C]ONTINUE an active game.\n"

    menu += "E[X]IT to return to the main menu."

    send_message(menu, sender_id, interface)
    update_user_state(sender_id, {'command': command_str, 'step': 1})

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
            game_id = driver.start_new_game(sender_id)
            update_user_state(sender_id, {'command': command_str, 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
        elif message == 'c':
            active_games = get_active_games_for_player(game_instance.game_type, str(sender_id))
            response = "Your active games:\n"
            for game_id, player_x, player_o, status in active_games:
                opponent_id = player_o if str(sender_id) == player_x else player_x
                opponent_sn = "Waiting..."
                if opponent_id:
                    opponent_node_id = get_node_id_from_num(int(opponent_id), interface)
                    opponent_sn = get_node_short_name(opponent_node_id, interface)
                response += f"ID: {game_id}, Opponent: {opponent_sn}, Status: {status}\n"
            response += "\nEnter the ID of the game you want to continue."
            send_message(response, sender_id, interface)
            update_user_state(sender_id, {'command': command_str, 'step': 13})
        elif message.isdigit():
            game_id = driver.join_game_by_id(sender_id, message)
            if game_id:
                update_user_state(sender_id, {'command': command_str, 'step': 12, 'game_id': game_id, 'active_game_id': game_id})
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
