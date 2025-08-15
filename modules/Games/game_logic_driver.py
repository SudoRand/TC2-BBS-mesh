import json
from db_operations import (
    create_game,
    get_open_games,
    join_game,
    get_game_by_id,
    update_game_board,
    end_game,
)
from utils import send_message, get_node_short_name, get_node_id_from_num, update_user_state
from .game_interface import GameInterface


class GameLogicDriver:
    """
    Drives the logic for a generic, turn-based game.

    This class is responsible for orchestrating the game flow for remote
    player-vs-player games. It uses a GameInterface object to get game-specific
    details and interacts with the database to maintain game state.
    """

    def __init__(self, game_interface: GameInterface, interface):
        self.game = game_interface
        self.interface = interface
        self.game_type = self.game.game_type

    def create_game_with_first_move(self, sender_id, board):
        """Creates a new game in the database after the first move."""
        board_json = json.dumps(board)
        # current_player is left NULL, to be set when P2 joins.
        game_id = create_game(self.game_type, str(sender_id), board_json)

        board_str = self.game.render_board(board, None, None)
        response = f"Your game (ID: {game_id}) is now listed and waiting for an opponent.\n\n{board_str}"
        send_message(response, sender_id, self.interface)
        return game_id

    def show_open_games(self, sender_id):
        """Shows a list of open games a player can join."""
        games = get_open_games(self.game_type)
        if not games:
            response = "No open games available to join. Why not start one?"
            send_message(response, sender_id, self.interface)
            return

        response = "Open games:\n"
        for game in games:
            game_id, player_x_id, _ = game
            node_id = get_node_id_from_num(int(player_x_id), self.interface)
            short_name = get_node_short_name(node_id, self.interface)
            response += f"ID: {game_id}, Started by: {short_name}\n"
        response += "\nEnter the ID of the game you want to join, or 'X' to exit."
        send_message(response, sender_id, self.interface)

    def join_game_by_id(self, sender_id, game_id_str):
        """Handles the logic for a player to join a game by its ID."""
        try:
            game_id = int(game_id_str)
            join_game(game_id, str(sender_id))
            game_data = get_game_by_id(game_id)
            if not game_data:
                send_message("Game not found after joining.", sender_id, self.interface)
                return None

            _, _, player_x_id, player_o_id, board_json, _, _, _, _ = game_data
            board = json.loads(board_json)

            player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x_id), self.interface), self.interface)
            player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o_id), self.interface), self.interface)

            board_str = self.game.render_board(board, player_x_sn, player_o_sn)
            instruction_board = self.game.get_instruction_board()

            response_o = f"You joined game {game_id}.\n\n{instruction_board}\n\n{board_str}\nIt's your turn (O). Enter your move, or E[X]IT to pause."
            send_message(response_o, sender_id, self.interface)
            return game_id
        except ValueError:
            send_message("Invalid game ID. Please enter a number.", sender_id, self.interface)
        except Exception as e:
            send_message(f"Could not join game: {e}", sender_id, self.interface)
        return None

    def play_move(self, sender_id, message, state):
        """Processes a player's move for a remote game."""
        game_id = state.get('game_id')
        if not game_id:
            # This should not happen if the state is managed correctly
            send_message("Error: Not in a game.", sender_id, self.interface)
            return

        game_data = get_game_by_id(game_id)
        if not self._validate_game_state(sender_id, game_data):
            return

        _, _, player_x, player_o, board_json, current_player, _, status, _, _ = game_data

        if player_o is None:
            send_message("Waiting for an opponent to join before you can make a move.", sender_id, self.interface)
            return

        board = json.loads(board_json)

        if str(sender_id) != current_player:
            player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), self.interface), self.interface)
            player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), self.interface), self.interface)
            current_player_sn = player_x_sn if str(current_player) == str(player_x) else player_o_sn
            current_player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
            send_message(f"It's {current_player_sn} ({current_player_symbol})'s turn.", sender_id, self.interface)
            return

        try:
            player_symbol = 'X' if str(sender_id) == player_x else 'O'
            board = self.game.handle_move(board, message, player_symbol)
        except ValueError as e:
            send_message(f"Invalid move: {e}", sender_id, self.interface)
            return

        player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), self.interface), self.interface)
        player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), self.interface), self.interface) if player_o else None

        winner_symbol = self.game.check_winner(board)
        if winner_symbol:
            self._handle_game_end(game_id, board, winner_symbol, current_player, player_x, player_o, player_x_sn, player_o_sn)
            return

        next_player = player_o if str(current_player) == player_x else player_x
        update_game_board(game_id, json.dumps(board), next_player)

        self._notify_players(sender_id, board, next_player, player_x, player_o, player_x_sn, player_o_sn, player_symbol)

    def redisplay_game_board(self, sender_id, game_id):
        """Redisplays the game board and prompt to a user returning to a game."""
        game_data = get_game_by_id(game_id)
        if not self._validate_game_state(sender_id, game_data, is_redisplay=True):
            return

        game_id, _, player_x, player_o, board_json, current_player, winner, status, _, _ = game_data
        board = json.loads(board_json)

        player_x_sn = get_node_short_name(get_node_id_from_num(int(player_x), self.interface), self.interface)
        player_o_sn = get_node_short_name(get_node_id_from_num(int(player_o), self.interface), self.interface) if player_o else None

        if status == 'finished':
            winner_name = player_x_sn if str(winner) == player_x else (player_o_sn if player_o else "Unknown")
            response = f"{self.game.render_board(board, player_x_sn, player_o_sn)}\n\nGame over! Winner: {winner_name}\n\nType 'X' to return to the games menu."
            send_message(response, sender_id, self.interface)
            return

        # Determine the prompt based on whose turn it is
        if str(sender_id) == current_player:
            player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
            response = f"{self.game.get_instruction_board()}\n\n{self.game.render_board(board, player_x_sn, player_o_sn)}\n\nIt's your turn ({player_symbol}). Enter your move, or E[X]IT to pause."
        elif player_o is None and str(sender_id) == player_x:
            response = f"{self.game.render_board(board, player_x_sn, player_o_sn)}\n\nWaiting for an opponent to join. Or E[X]IT to pause."
        else:
            current_player_sn = player_x_sn if str(current_player) == str(player_x) else player_o_sn
            current_player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
            response = f"{self.game.render_board(board, player_x_sn, player_o_sn)}\n\nIt's {current_player_sn} ({current_player_symbol})'s turn. E[X]IT to pause."

        send_message(response, sender_id, self.interface)

    def _validate_game_state(self, sender_id, game_data, is_redisplay=False):
        """Validates the game data and sends appropriate messages if invalid."""
        if not game_data:
            send_message("Could not find your game. It may have ended.", sender_id, self.interface)
            if not is_redisplay: # Avoid loop
                from command_handlers import handle_help_command
                handle_help_command(sender_id, self.interface)
            return False

        game_type = game_data[1]
        if game_type != self.game_type:
            # This should not happen if called correctly
            send_message("Fatal error: Game type mismatch.", sender_id, self.interface)
            return False

        return True

    def _handle_game_end(self, game_id, board, winner_symbol, current_player, p_x_id, p_o_id, p_x_sn, p_o_sn):
        """Handles the logic when a game has ended (win or draw)."""
        board_str = self.game.render_board(board, p_x_sn, p_o_sn)

        if winner_symbol == 'draw':
            end_game(game_id, "draw")
            draw_response = f"{board_str}\n\nIt's a draw!\n\nType 'X' to return to the games menu."
            send_message(draw_response, int(p_x_id), self.interface)
            if p_o_id:
                send_message(draw_response, int(p_o_id), self.interface)
            update_user_state(int(p_x_id), {'command': 'GAMES', 'step': 1})
            if p_o_id:
                update_user_state(int(p_o_id), {'command': 'GAMES', 'step': 1})
            return

        winner_id = current_player
        end_game(game_id, winner_id)
        winner_name = p_x_sn if str(winner_id) == p_x_id else p_o_sn
        loser_id = int(p_o_id) if str(current_player) == p_x_id else int(p_x_id)

        win_response = f"{board_str}\n\nCongratulations! You win!\n\nType 'X' to return to the games menu."
        lose_response = f"{board_str}\n\nGame over. {winner_name} wins.\n\nType 'X' to return to the games menu."

        send_message(win_response, int(winner_id), self.interface)
        if loser_id:
            send_message(lose_response, loser_id, self.interface)

        update_user_state(int(winner_id), {'command': 'GAMES', 'step': 1})
        if loser_id:
            update_user_state(loser_id, {'command': 'GAMES', 'step': 1})

    def _notify_players(self, sender_id, board, next_player, p_x_id, p_o_id, p_x_sn, p_o_sn, mover_symbol):
        """Notifies players of the move that was just made."""
        board_str = self.game.render_board(board, p_x_sn, p_o_sn)
        mover_sn = p_x_sn if str(sender_id) == p_x_id else p_o_sn

        # Notify the other player that it's their turn
        if str(sender_id) == p_x_id and p_o_id is None: # First move before P2 joins
            pass # P1 is notified when P2 joins
        elif board.count(mover_symbol) == 1 and str(sender_id) == p_o_id: # First move by O
             response_x = f"Player {mover_sn} has joined your game!\n{board_str}\nIt is your turn (X)."
             send_message(response_x, int(p_x_id), self.interface)
        elif next_player:
            your_symbol = 'O' if mover_symbol == 'X' else 'X'
            response_other = f"{board_str}\n\n{mover_sn} ({mover_symbol}) has made a move. It's your turn ({your_symbol})."
            send_message(response_other, int(next_player), self.interface)

        # Confirm move to the current player
        waiting_message = "Move made. Waiting for opponent."
        if next_player:
            opponent_sn = p_x_sn if str(next_player) == p_x_id else p_o_sn
            opponent_symbol = 'X' if str(next_player) == p_x_id else 'O'
            waiting_message = f"Move made. Waiting for opponent {opponent_sn} ({opponent_symbol})."

        response_self = f"{board_str}\n\n{waiting_message}"
        send_message(response_self, sender_id, self.interface)
