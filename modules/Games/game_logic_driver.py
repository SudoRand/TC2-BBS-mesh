import json
from db_operations import (
    create_game,
    get_open_games,
    get_waiting_games_for_creator,
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

    def _send_game_state_message(self, recipient_id, pre_board_text=None, board_str=None, post_board_text=None):
        """Sends a message, ensuring the board is in its own message."""
        if pre_board_text:
            send_message(pre_board_text, recipient_id, self.interface)
        if board_str:
            send_message(board_str, recipient_id, self.interface)
        if post_board_text:
            send_message(post_board_text, recipient_id, self.interface)

    def create_game_with_first_move(self, sender_id, board):
        """Creates a new game in the database after the first move."""
        board_json = json.dumps(board)
        # current_player is left NULL, to be set when P2 joins.
        game_id = create_game(self.game_type, str(sender_id), board_json)

        board_str = self.game.render_board(board, None, None)
        pre_board_text = f"Your game (ID: {game_id}) is now listed and waiting for an opponent."
        self._send_game_state_message(sender_id, pre_board_text=pre_board_text, board_str=board_str)
        return game_id

    def show_open_games(self, sender_id):
        """Shows a list of open games a player can join."""
        # Games waiting for an opponent that were created by the user
        waiting_games = get_waiting_games_for_creator(self.game_type, str(sender_id))
        if waiting_games:
            response = "Your waiting games:\n"
            for game in waiting_games:
                game_id, _ = game
                response += f"ID: {game_id}\n"
            send_message(response, sender_id, self.interface)

        # Show open games that the user can join
        open_games = get_open_games(self.game_type)
        joinable_games = [game for game in open_games if str(game[1]) != str(sender_id)]

        if not waiting_games and not joinable_games:
            response = "No open games available. Why not start one?"
            send_message(response, sender_id, self.interface)
            return

        if joinable_games:
            response = "Open games to join:\n"
            for game in joinable_games:
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

            pre_board_text = f"You joined game {game_id}.\n\n{instruction_board}"
            post_board_text = "It's your turn (O). Enter your move, or E[X]IT to pause."
            self._send_game_state_message(sender_id, pre_board_text=pre_board_text, board_str=board_str,
                                          post_board_text=post_board_text)
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
        board_str = self.game.render_board(board, player_x_sn, player_o_sn)

        if status == 'finished':
            winner_name = player_x_sn if str(winner) == player_x else (player_o_sn if player_o else "Unknown")
            post_board_text = f"Game over! Winner: {winner_name}\n\nType 'X' to return to the games menu."
            self._send_game_state_message(sender_id, board_str=board_str, post_board_text=post_board_text)
            return

        # Determine the prompt based on whose turn it is
        if str(sender_id) == current_player:
            player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
            pre_board_text = self.game.get_instruction_board()
            post_board_text = f"It's your turn ({player_symbol}). Enter your move, or E[X]IT to pause."
            self._send_game_state_message(sender_id, pre_board_text=pre_board_text, board_str=board_str,
                                          post_board_text=post_board_text)
        elif player_o is None and str(sender_id) == player_x:
            post_board_text = "Waiting for an opponent to join. Or E[X]IT to pause."
            self._send_game_state_message(sender_id, board_str=board_str, post_board_text=post_board_text)
        else:
            current_player_sn = player_x_sn if str(current_player) == str(player_x) else player_o_sn
            current_player_symbol = 'X' if str(current_player) == str(player_x) else 'O'
            post_board_text = f"It's {current_player_sn} ({current_player_symbol})'s turn. E[X]IT to pause."
            self._send_game_state_message(sender_id, board_str=board_str, post_board_text=post_board_text)

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
            post_board_text = "It's a draw!\n\nType 'X' to return to the games menu."
            self._send_game_state_message(int(p_x_id), board_str=board_str, post_board_text=post_board_text)
            if p_o_id:
                self._send_game_state_message(int(p_o_id), board_str=board_str, post_board_text=post_board_text)
            update_user_state(int(p_x_id), {'command': 'GAMES', 'step': 1})
            if p_o_id:
                update_user_state(int(p_o_id), {'command': 'GAMES', 'step': 1})
            return

        winner_id = current_player
        end_game(game_id, winner_id)
        winner_name = p_x_sn if str(winner_id) == p_x_id else p_o_sn
        loser_id = int(p_o_id) if str(current_player) == p_x_id else int(p_x_id)

        win_post_board_text = "Congratulations! You win!\n\nType 'X' to return to the games menu."
        lose_post_board_text = f"Game over. {winner_name} wins.\n\nType 'X' to return to the games menu."

        self._send_game_state_message(int(winner_id), board_str=board_str, post_board_text=win_post_board_text)
        if loser_id:
            self._send_game_state_message(loser_id, board_str=board_str, post_board_text=lose_post_board_text)

        update_user_state(int(winner_id), {'command': 'GAMES', 'step': 1})
        if loser_id:
            update_user_state(loser_id, {'command': 'GAMES', 'step': 1})

    def _notify_players(self, sender_id, board, next_player, p_x_id, p_o_id, p_x_sn, p_o_sn, mover_symbol):
        """Notifies players of the move that was just made."""
        board_str = self.game.render_board(board, p_x_sn, p_o_sn)
        mover_sn = p_x_sn if str(sender_id) == p_x_id else p_o_sn

        # Notify the other player that it's their turn
        if str(sender_id) == p_x_id and p_o_id is None:  # First move before P2 joins
            pass  # P1 is notified when P2 joins
        elif board.count(mover_symbol) == 1 and str(sender_id) == p_o_id:  # First move by O
            pre_board_text = f"Player {mover_sn} has joined your game!"
            post_board_text = "It is your turn (X)."
            self._send_game_state_message(int(p_x_id), pre_board_text=pre_board_text, board_str=board_str,
                                          post_board_text=post_board_text)
        elif next_player:
            your_symbol = 'O' if mover_symbol == 'X' else 'X'
            post_board_text = f"{mover_sn} ({mover_symbol}) has made a move. It's your turn ({your_symbol})."
            self._send_game_state_message(int(next_player), board_str=board_str, post_board_text=post_board_text)

        # Confirm move to the current player
        waiting_message = "Move made. Waiting for opponent."
        if next_player:
            opponent_sn = p_x_sn if str(next_player) == p_x_id else p_o_sn
            opponent_symbol = 'X' if str(next_player) == p_x_id else 'O'
            waiting_message = f"Move made. Waiting for opponent {opponent_sn} ({opponent_symbol})."

        self._send_game_state_message(sender_id, board_str=board_str, post_board_text=waiting_message)
