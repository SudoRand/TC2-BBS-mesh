import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch
import configparser

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from db_operations import (
    initialize_database,
    create_tic_tac_toe_game,
    get_open_tic_tac_toe_games,
    get_active_tic_tac_toe_games_for_player,
    join_tic_tac_toe_game,
    get_tic_tac_toe_game_by_id,
    update_tic_tac_toe_board,
    end_tic_tac_toe_game
)
from modules.Games.tic_tac_toe import check_winner, handle_tic_tac_toe_steps, handle_tic_tac_toe_command, INSTRUCTION_BOARD
from utils import update_user_state, get_user_state

class TestTicTacToe(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.db_path = 'test_bulletins.db'
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection')
        self.mock_get_db_connection = self.get_db_connection_patcher.start()
        self.mock_get_db_connection.return_value = self.conn

        # Create a dummy config.ini
        with open('config.ini', 'w') as f:
            f.write('[menu]\n')
            f.write('main_menu_items = B,G,U,Q\n')
            f.write('bbs_menu_items = B,M,C,X\n')
            f.write('utilities_menu_items = S,F,W,X\n')
            f.write('games_menu_items = T,X\n')

        initialize_database()

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_create_game(self):
        game_id = create_tic_tac_toe_game("player1")
        self.assertIsNotNone(game_id)
        games = get_open_tic_tac_toe_games()
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0][1], "player1")

    def test_join_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[2], "player2")
        self.assertEqual(game[6], "in_progress")

    def test_make_move(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = json.loads(get_tic_tac_toe_game_by_id(game_db_id)[3])
        board[0] = "X"
        update_tic_tac_toe_board(game_db_id, json.dumps(board), "player2")

        game = get_tic_tac_toe_game_by_id(game_db_id)
        new_board = json.loads(game[3])
        self.assertEqual(new_board[0], "X")
        self.assertEqual(game[4], "player2")

    def test_win_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = ["X", "X", "X", " ", " ", " ", " ", " ", " "]
        self.assertEqual(check_winner(board), "X")

        end_tic_tac_toe_game(game_db_id, "player1")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[5], "player1")
        self.assertEqual(game[6], "finished")

    def test_draw_game(self):
        game_id = create_tic_tac_toe_game("player1")
        games = get_open_tic_tac_toe_games()
        game_db_id = games[0][0]
        join_tic_tac_toe_game(game_db_id, "player2")

        board = ["X", "O", "X", "X", "O", "X", "O", "X", "O"]
        self.assertIsNone(check_winner(board))

        end_tic_tac_toe_game(game_db_id, "draw")
        game = get_tic_tac_toe_game_by_id(game_db_id)
        self.assertEqual(game[5], "draw")
        self.assertEqual(game[6], "finished")

    def test_get_active_games_for_player(self):
        game1_id = create_tic_tac_toe_game("player1")
        game2_id = create_tic_tac_toe_game("player3")

        join_tic_tac_toe_game(game1_id, "player2")

        # Player 1 should have one active game
        player1_games = get_active_tic_tac_toe_games_for_player("player1")
        self.assertEqual(len(player1_games), 1)
        self.assertEqual(player1_games[0][0], game1_id)

        # Player 2 should have one active game
        player2_games = get_active_tic_tac_toe_games_for_player("player2")
        self.assertEqual(len(player2_games), 1)
        self.assertEqual(player2_games[0][0], game1_id)

        # Player 3 should have one active game (waiting for opponent)
        player3_games = get_active_tic_tac_toe_games_for_player("player3")
        self.assertEqual(len(player3_games), 1)
        self.assertEqual(player3_games[0][0], game2_id)

        # Player 4 should have no active games
        player4_games = get_active_tic_tac_toe_games_for_player("player4")
        self.assertEqual(len(player4_games), 0)

        # End game 1
        end_tic_tac_toe_game(game1_id, "player1")
        player1_games_after_end = get_active_tic_tac_toe_games_for_player("player1")
        self.assertEqual(len(player1_games_after_end), 0)

    @patch('modules.Games.tic_tac_toe.send_message')
    def test_continue_game_flow(self, mock_send_message):
        # 1. Setup mock interface and players
        mock_interface = unittest.mock.MagicMock()
        p1_num = 111
        p1_id = '!p1'
        p1_sn = 'P1'
        p2_num = 222
        p2_id = '!p2'
        p2_sn = 'P2'

        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}},
            p2_id: {'num': p2_num, 'user': {'shortName': p2_sn}},
        }

        # 2. Player 1 creates a game
        game_id = create_tic_tac_toe_game(str(p1_num))
        join_tic_tac_toe_game(game_id, str(p2_num))

        # 3. Player 1 goes to the tic-tac-toe menu
        handle_tic_tac_toe_command(p1_num, mock_interface)
        self.assertEqual(mock_send_message.call_count, 1)
        menu_msg = mock_send_message.call_args[0][0]
        self.assertIn("[4] Continue Game", menu_msg)

        # 4. Player 1 chooses to continue a game
        state_p1 = get_user_state(p1_num)
        handle_tic_tac_toe_steps(p1_num, "4", state_p1['step'], state_p1, mock_interface)
        self.assertEqual(mock_send_message.call_count, 2)
        continue_menu_msg = mock_send_message.call_args[0][0]
        self.assertIn(f"ID: {game_id}, Opponent: {p2_sn}, Status: in_progress", continue_menu_msg)

        # 5. Player 1 chooses the game to continue
        state_p1 = get_user_state(p1_num)
        handle_tic_tac_toe_steps(p1_num, str(game_id), state_p1['step'], state_p1, mock_interface)
        self.assertEqual(mock_send_message.call_count, 3)
        redisplay_msg = mock_send_message.call_args[0][0]
        self.assertIn("It's not your turn.", redisplay_msg) # P2 is current player

    @patch('modules.Games.tic_tac_toe.send_message')
    def test_list_open_games_displays_short_name(self, mock_send_message):
        # 2. Setup mock interface and user states
        mock_interface = unittest.mock.MagicMock()
        player1_node_num = 12345
        player1_node_id = '!b827ebf575b0'
        player1_short_name = 'P1'

        mock_interface.nodes = {
            player1_node_id: {'num': player1_node_num, 'user': {'shortName': player1_short_name, 'longName': 'PlayerOne'}},
        }

        # 3. Create a game
        create_tic_tac_toe_game(str(player1_node_num))

        # 4. User requests to join a game
        player2_node_num = 54321
        player2_node_id = '!b827ebf575b1'
        update_user_state(player2_node_id, {'command': 'TIC_TAC_TOE', 'step': 10})
        state = {'command': 'TIC_TAC_TOE', 'step': 10}

        handle_tic_tac_toe_steps(player2_node_id, "2", 10, state, mock_interface)

        # 5. Assert the message contains the short name
        self.assertEqual(mock_send_message.call_count, 1)
        sent_message = mock_send_message.call_args[0][0]
        self.assertIn(f"Started by: {player1_short_name}", sent_message)
        self.assertNotIn(str(player1_node_num), sent_message)

    @patch('modules.Games.tic_tac_toe.send_message')
    def test_remote_game_flow(self, mock_send_message):
        # 1. Setup mock interface and players
        mock_interface = unittest.mock.MagicMock()
        p1_num = 111
        p1_id = '!p1'
        p1_sn = 'P1'
        p2_num = 222
        p2_id = '!p2'
        p2_sn = 'P2'

        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}},
            p2_id: {'num': p2_num, 'user': {'shortName': p2_sn}},
        }

        # 2. Player 1 creates a game
        state_p1 = {'command': 'TIC_TAC_TOE', 'step': 10}
        handle_tic_tac_toe_steps(p1_num, "1", 10, state_p1, mock_interface)

        # Assert P1 gets prompted for first move
        self.assertEqual(mock_send_message.call_count, 1)
        create_msg = mock_send_message.call_args[0][0]
        self.assertIn("New game started.", create_msg)
        self.assertIn(INSTRUCTION_BOARD, create_msg)
        self.assertIn("You are X. Enter 1-9 to make your move, or [M]enu to exit.", create_msg)
        game_id = get_open_tic_tac_toe_games()[0][0]

        # 3. Player 1 makes first move
        state_p1 = {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id}
        handle_tic_tac_toe_steps(p1_num, "5", 12, state_p1, mock_interface)

        # Assert P1 gets confirmation
        self.assertEqual(mock_send_message.call_count, 2)
        move1_msg = mock_send_message.call_args[0][0]
        self.assertIn("Move made. Waiting for opponent.", move1_msg)

        # 4. Player 2 joins the game
        state_p2 = {'command': 'TIC_TAC_TOE', 'step': 11}
        handle_tic_tac_toe_steps(p2_num, str(game_id), 11, state_p2, mock_interface)

        # Assert P2 gets notified and prompted, and P1 is NOT notified yet
        self.assertEqual(mock_send_message.call_count, 3) # Only one message for join
        join_msg_p2 = mock_send_message.call_args[0][0]
        self.assertIn(f"You joined game {game_id}", join_msg_p2)
        self.assertIn(INSTRUCTION_BOARD, join_msg_p2)
        self.assertIn("It's your turn (O).", join_msg_p2)

        # 5. Player 2 makes their first move
        state_p2 = {'command': 'TIC_TAC_TOE', 'step': 12, 'game_id': game_id}
        handle_tic_tac_toe_steps(p2_num, "1", 12, state_p2, mock_interface)

        # Assert P2 gets confirmation AND P1 gets the delayed notification
        self.assertEqual(mock_send_message.call_count, 5) # 2 more messages sent

        # The second to last message is to P1
        delayed_notify_p1 = mock_send_message.call_args_list[-2][0][0]
        self.assertIn(f"Player {p2_sn} has joined your game!", delayed_notify_p1)
        self.assertIn("It is your turn (X).", delayed_notify_p1)

        # The last message is to P2 (the sender)
        move_confirm_p2 = mock_send_message.call_args_list[-1][0][0]
        self.assertIn(f"Move made. Waiting for opponent {p1_sn} (X).", move_confirm_p2)


    @patch('command_handlers.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_pause_and_resume_game(self, mock_game_send_message, mock_cmd_send_message):
        # 1. Setup mock interface and players
        mock_interface = unittest.mock.MagicMock()
        p1_num = 111
        p1_id = '!p1'
        p1_sn = 'P1'

        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn, 'longName': 'PlayerOne'}},
        }
        mock_interface.myInfo.my_node_num = 999 # Some other node

        # 2. Player 1 creates a game
        state_p1 = {'command': 'TIC_TAC_TOE', 'step': 10}
        handle_tic_tac_toe_steps(p1_num, "1", 10, state_p1, mock_interface)
        game_id = get_open_tic_tac_toe_games()[0][0]

        # 3. Player 1 enters 'm' to pause the game and go to the menu
        state_p1 = get_user_state(p1_num)
        handle_tic_tac_toe_steps(p1_num, "m", state_p1['step'], state_p1, mock_interface)

        # Assert that the main menu is shown with the 'Return to Game' option
        self.assertEqual(mock_cmd_send_message.call_count, 1)
        menu_msg = mock_cmd_send_message.call_args[0][0]
        self.assertIn("[RG]eturn to Game", menu_msg)
        self.assertNotIn("[G]ames", menu_msg)

        # 4. Player 1 enters 'rg' to resume the game
        state_p1 = get_user_state(p1_num) # State is now MAIN_MENU
        self.assertEqual(state_p1['command'], 'MAIN_MENU')
        from message_processing import main_menu_handlers
        main_menu_handlers['rg'](p1_num, mock_interface)

        # Assert that the game board is redisplayed
        # Call count is 2: one for creating the game, one for resuming
        self.assertEqual(mock_game_send_message.call_count, 2)
        resume_msg = mock_game_send_message.call_args[0][0]
        self.assertIn("It's your turn (X). Enter 1-9 to make your move, or [M]enu to exit.", resume_msg)


if __name__ == '__main__':
    unittest.main()
