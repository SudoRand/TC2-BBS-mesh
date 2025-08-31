import json
from db_operations import (
    create_game,
    get_open_games,
    get_waiting_games_for_creator,
    get_active_games_for_player,
    join_game,
    get_game_by_id,
    update_game_board,
    end_game, get_player_stats, get_all_finished_games, get_active_games_by_type, count_active_games_by_type,
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

    def show_games_and_menu(self, sender_id, command_str):
        """Shows lists of games a player can join or continue, plus the menu."""
        player_id_str = str(sender_id)
        response_parts = []

        # Show games the user can continue
        all_active_games = get_active_games_for_player(self.game_type, player_id_str)
        # Assuming get_active_games_for_player returns (game_id, player_x, player_o, status, current_player)
        continuable_games = [g for g in all_active_games if g[3] == 'in_progress']

        your_turn_games = []
        opponents_turn_games = []

        for game in continuable_games:
            current_player = game[4]
            if str(current_player) == player_id_str:
                your_turn_games.append(game)
            else:
                opponents_turn_games.append(game)

        if your_turn_games:
            lines = ["Your turn:"]
            for game_id, player_x, player_o, _, _ in your_turn_games:
                opponent_id = player_o if player_id_str == str(player_x) else player_x
                opponent_node_id = get_node_id_from_num(int(opponent_id), self.interface)
                opponent_sn = get_node_short_name(opponent_node_id, self.interface) if opponent_node_id else "Unknown"
                lines.append(f"[{game_id}] vs {opponent_sn}")
            response_parts.append("\n".join(lines))

        if opponents_turn_games:
            lines = ["Opponent's turn:"]
            for game_id, player_x, player_o, _, _ in opponents_turn_games:
                opponent_id = player_o if player_id_str == str(player_x) else player_x
                opponent_node_id = get_node_id_from_num(int(opponent_id), self.interface)
                opponent_sn = get_node_short_name(opponent_node_id, self.interface) if opponent_node_id else "Unknown"
                lines.append(f"[{game_id}] vs {opponent_sn}")
            response_parts.append("\n".join(lines))

        # Games waiting for an opponent that were created by the user
        waiting_games = get_waiting_games_for_creator(self.game_type, player_id_str)
        if waiting_games:
            waiting_game_lines = [f'[{game[0]}] vs ?' for game in waiting_games]
            response_parts.append("You need opponent:\n" + "\n".join(waiting_game_lines))

        # Show open games that the user can join
        open_games = get_open_games(self.game_type)
        joinable_games = [game for game in open_games if str(game[1]) != player_id_str]
        if joinable_games:
            lines = ["Join game:"]
            for game in joinable_games:
                game_id, player_x_id, _ = game
                node_id = get_node_id_from_num(int(player_x_id), self.interface)
                short_name = get_node_short_name(node_id, self.interface)
                lines.append(f"[{game_id}] vs {short_name}")
            response_parts.append("\n".join(lines))

        if not response_parts:
            response_parts.append("No open games available. Why not start one?")

        response = "\n\n".join(response_parts)
        menu = "\n[N]ew Game\n"
        menu += "[S]tats\n"
        menu += "E[X]it"
        response += "\n" + menu
        send_message(response, sender_id, self.interface)
        update_user_state(sender_id, {'command': command_str, 'step': 1})

    def _calculate_leaderboard_data(self):
        """Calculates scores and stats for all players."""
        games = get_all_finished_games(self.game_type)
        if not games:
            return None

        player_stats = {}

        def get_player(player_id):
            if player_id not in player_stats:
                player_stats[player_id] = {'score': 0, 'wins': 0, 'losses': 0, 'ties': 0}
            return player_stats[player_id]

        for player_x_id, player_o_id, winner_id in games:
            player_x = get_player(player_x_id)
            player_o = get_player(player_o_id)

            if winner_id == 'tie':
                player_x['score'] += 1
                player_x['ties'] += 1
                player_o['score'] += 1
                player_o['ties'] += 1
            else:
                if winner_id == player_x_id:
                    winner_stats = player_x
                    loser_stats = player_o
                else:
                    winner_stats = player_o
                    loser_stats = player_x

                winner_stats['score'] += 3
                winner_stats['wins'] += 1
                loser_stats['losses'] += 1

        return sorted(player_stats.items(), key=lambda item: item[1]['score'], reverse=True)

    def show_leaderboard(self, sender_id):
        """Calculates and displays the leaderboard."""
        sorted_players = self._calculate_leaderboard_data()

        if not sorted_players:
            send_message("No games have been played yet.", sender_id, self.interface)
            return

        response = f"--- {self.game.game_type.upper()} LEADERBOARD ---\n"
        for i, (player_id, stats) in enumerate(sorted_players):
            player_node_id = get_node_id_from_num(int(player_id), self.interface)
            player_sn = get_node_short_name(player_node_id, self.interface)
            response += f"{i+1}. {player_sn}: {stats['score']} pts ({stats['wins']}W-{stats['ties']}T-{stats['losses']}L)\n"

        send_message(response, sender_id, self.interface)

    def show_stats_menu(self, sender_id, command_str):
        """Displays the stats menu and updates the user's state."""
        menu = "[M]y Stats\n"
        menu += "[A]ctive Games\n"
        menu += "[L]eaderboard\n"
        menu += "E[X]IT"
        send_message(menu, sender_id, self.interface)
        update_user_state(sender_id, {'command': command_str, 'step': 2})

    def show_active_games(self, sender_id):
        """Calculates and displays the active games list."""
        games = get_active_games_by_type(self.game_type)
        total_games = count_active_games_by_type(self.game_type)

        if not games:
            send_message("No active games.", sender_id, self.interface)
            return

        response = f"--- ACTIVE {self.game.game_type.upper()} GAMES ---\n"
        for player_x, player_o, last_activity in games:
            p1_sn = get_node_short_name(get_node_id_from_num(int(player_x), self.interface), self.interface)
            p2_sn = get_node_short_name(get_node_id_from_num(int(player_o), self.interface), self.interface) if player_o else "?"
            # format last_activity to just date
            date_str = last_activity.split(" ")[0]
            response += f"{p1_sn} vs {p2_sn} ({date_str})\n"

        if total_games > 10:
            response += f"+ {total_games - 10} older"

        send_message(response, sender_id, self.interface)

    def show_player_stats(self, sender_id):
        """Calculates and displays the player's game stats."""
        player_id_str = str(sender_id)
        stats = get_player_stats(self.game_type, player_id_str)

        if not stats:
            send_message("No game history found.", sender_id, self.interface)
            return

        wins = losses = ties = 0
        opponent_stats = {}

        for player_x, player_o, winner in stats:
            if winner == player_id_str:
                wins += 1
            elif winner == 'tie':
                ties += 1
            else:
                losses += 1

            opponent_id = None
            if player_x == player_id_str:
                opponent_id = player_o
            else:
                opponent_id = player_x

            if opponent_id:
                if opponent_id not in opponent_stats:
                    opponent_stats[opponent_id] = {'w': 0, 't': 0, 'l': 0}

                if winner == player_id_str:
                    opponent_stats[opponent_id]['w'] += 1
                elif winner == 'tie':
                    opponent_stats[opponent_id]['t'] += 1
                else:
                    opponent_stats[opponent_id]['l'] += 1

        sorted_players = self._calculate_leaderboard_data()
        player_rank = "N/A"
        player_points = 0
        total_players = 0
        if sorted_players:
            total_players = len(sorted_players)
            for i, (player_id, p_stats) in enumerate(sorted_players):
                if player_id == player_id_str:
                    player_rank = i + 1
                    player_points = p_stats['score']
                    break

        player_node_id = get_node_id_from_num(int(player_id_str), self.interface)
        player_sn = get_node_short_name(player_node_id, self.interface)

        response = f"STATS for {player_sn}\n"
        response += f"Rank: {player_rank}/{total_players} | Points: {player_points}\n"
        response += f"Overall: {wins}W-{ties}T-{losses}L \n\n"

        if opponent_stats:
            response += "Vs:\n"
            for opponent_id, s in opponent_stats.items():
                opponent_node_id = get_node_id_from_num(int(opponent_id), self.interface)
                opponent_sn = get_node_short_name(opponent_node_id, self.interface) if opponent_node_id else "Unknown"
                response += f"{opponent_sn}: {s['w']}W-{s['t']}T-{s['l']}L \n"

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

            _, _, player_x_id, player_o_id, board_json, _, _, status, _, _ = game_data
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
        """Handles the logic when a game has ended (win or tie)."""
        board_str = self.game.render_board(board, p_x_sn, p_o_sn)

        if winner_symbol == 'tie':
            end_game(game_id, "tie")
            post_board_text = "It's a tie!\n\nType 'X' to return to the games menu."
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
        is_flat_board = not(isinstance(board[0], list))
        if is_flat_board:
            symbol_count = board.count(mover_symbol)
        else:
            symbol_count = sum(row.count(mover_symbol) for row in board)

        if str(sender_id) == p_x_id and p_o_id is None:  # First move before P2 joins
            pass  # P1 is notified when P2 joins
        elif symbol_count == 1 and str(sender_id) == p_o_id:  # First move by O
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

def count_my_turn_games(game_type, node_id, interface):
    """
    Counts the number of active games of a specific type where it's the given node's turn.

    Args:
        game_type (str): The type of the game (e.g., 'tic_tac_toe', 'connect_four').
        node_id (str): The ID of the node to check.
        interface: The interface object for interacting with the system.

    Returns:
        int: The count of games where it's the node's turn.
    """
    active_games = get_active_games_by_type(game_type)
    my_turn_count = 0

    for game in active_games:
        game_id, _, p_x_id, p_o_id = game
        game_data = get_game_by_id(game_id)
        if not game_data:
            continue

        # game_data[2] is the current turn ('X' or 'O')
        current_turn = game_data[2] if len(game_data) > 2 else None
        if current_turn == 'X' and p_x_id == node_id:
            my_turn_count += 1
        elif current_turn == 'O' and p_o_id == node_id:
            my_turn_count += 1

    return my_turn_count
