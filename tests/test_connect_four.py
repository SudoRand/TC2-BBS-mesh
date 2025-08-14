import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

# Add the parent directory to the Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, create_game, get_open_games, join_game, get_game_by_id, update_game_board, end_game, get_active_games_for_player
from modules.Games.connect_four import ConnectFourGame, handle_connect_four_steps, handle_connect_four_command
from utils import update_user_state, get_user_state

class TestConnectFour(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.db_path = 'test_bulletins.db'
        self.conn = sqlite3.connect(self.db_path)
        self.get_db_connection_patcher = patch('db_operations.get_db_connection')
        self.mock_get_db_connection = self.get_db_connection_patcher.start()
        self.mock_get_db_connection.return_value = self.conn

        # Create a dummy config.ini and fortunes.txt
        with open('config.ini', 'w') as f:
            f.write('[menu]\n')
            f.write('main_menu_items = B,G,U,Q,X\n')
            f.write('bbs_menu_items = M,B,C,J,X\n')
            f.write('utilities_menu_items = S,F,W,X\n')
            f.write('games_menu_items = T,C,X\n')
        with open('fortunes.txt', 'w') as f:
            f.write('test fortune\n')

        initialize_database()
        self.game_instance = ConnectFourGame()
        self.initial_board_json = json.dumps(self.game_instance.get_initial_board())

    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_initial_board(self):
        board = self.game_instance.get_initial_board()
        self.assertEqual(len(board), 6)  # 6 rows
        self.assertEqual(len(board[0]), 7)  # 7 columns
        self.assertTrue(all(cell == " " for row in board for cell in row))

    def test_handle_move(self):
        board = self.game_instance.get_initial_board()
        board = self.game_instance.handle_move(board, "3", "X")
        self.assertEqual(board[0][2], "X")
        board = self.game_instance.handle_move(board, "3", "O")
        self.assertEqual(board[1][2], "O")

    def test_handle_full_column(self):
        board = self.game_instance.get_initial_board()
        for i in range(6):
            board = self.game_instance.handle_move(board, "1", "X")
        with self.assertRaisesRegex(ValueError, "Invalid move! That column is full."):
            self.game_instance.handle_move(board, "1", "O")

    def test_handle_invalid_move(self):
        board = self.game_instance.get_initial_board()
        with self.assertRaisesRegex(ValueError, "Invalid move! Column must be between 1 and 7."):
            self.game_instance.handle_move(board, "8", "X")
        with self.assertRaisesRegex(ValueError, "Invalid move! Column must be a number."):
            self.game_instance.handle_move(board, "abc", "X")

    def test_win_horizontal(self):
        board = self.game_instance.get_initial_board()
        board[0][1] = board[0][2] = board[0][3] = board[0][4] = "X"
        self.assertEqual(self.game_instance.check_winner(board), "X")

    def test_win_vertical(self):
        board = self.game_instance.get_initial_board()
        board[0][2] = board[1][2] = board[2][2] = board[3][2] = "O"
        self.assertEqual(self.game_instance.check_winner(board), "O")

    def test_win_positive_diagonal(self):
        board = self.game_instance.get_initial_board()
        board[0][0] = board[1][1] = board[2][2] = board[3][3] = "X"
        self.assertEqual(self.game_instance.check_winner(board), "X")

    def test_win_negative_diagonal(self):
        board = self.game_instance.get_initial_board()
        board[3][0] = board[2][1] = board[1][2] = board[0][3] = "O"
        self.assertEqual(self.game_instance.check_winner(board), "O")

    def test_draw_game(self):
        board = [
            ['X', 'O', 'X', 'O', 'X', 'O', 'X'],
            ['X', 'O', 'X', 'O', 'X', 'O', 'X'],
            ['O', 'X', 'O', 'X', 'O', 'X', 'O'],
            ['O', 'X', 'O', 'X', 'O', 'X', 'O'],
            ['X', 'O', 'X', 'O', 'X', 'O', 'X'],
            ['X', 'O', 'X', 'O', 'X', 'O', 'X']
        ]
        self.assertEqual(self.game_instance.check_winner(board), "draw")

    @patch('modules.Games.connect_four.send_message')
    def test_local_game_flow(self, mock_send_message):
        sender_id = 123
        mock_interface = MagicMock()

        # Start game
        handle_connect_four_command(sender_id, mock_interface)
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "1", state['step'], state, mock_interface)
        self.assertIn("Player vs Player (Local) mode selected", mock_send_message.call_args[0][0])

        # P1 Move 1
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "1", state['step'], state, mock_interface)
        self.assertIn("Next turn: 🟡", mock_send_message.call_args[0][0])

        # P2 Move 1
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "2", state['step'], state, mock_interface)

        # P1 Move 2
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "1", state['step'], state, mock_interface)

        # P2 Move 2
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "2", state['step'], state, mock_interface)

        # P1 Move 3
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "1", state['step'], state, mock_interface)

        # P2 Move 3
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "2", state['step'], state, mock_interface)

        # P1 Wins
        state = get_user_state(sender_id)
        handle_connect_four_steps(sender_id, "1", state['step'], state, mock_interface)

        # Check for win message
        self.assertIn("Congratulations! 🔴 wins!", mock_send_message.call_args[0][0])
        state = get_user_state(sender_id)
        self.assertEqual(state['step'], 1) # Should be back at the menu

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.connect_four.send_message')
    def test_remote_game_flow(self, mock_c4_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111; p1_id = '!p1'; p1_sn = 'P1'
        p2_num = 222; p2_id = '!p2'; p2_sn = 'P2'
        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}},
            p2_id: {'num': p2_num, 'user': {'shortName': p2_sn}},
        }

        with patch('modules.Games.game_logic_driver.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: p1_id, p2_num: p2_id}.get(int(num))):
            # P1 starts a new game
            handle_connect_four_command(p1_num, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_connect_four_steps(p1_num, '2', state_p1['step'], state_p1, mock_interface) # Remote
            state_p1 = get_user_state(p1_num)
            handle_connect_four_steps(p1_num, '1', state_p1['step'], state_p1, mock_interface) # New Game
            self.assertEqual(mock_driver_send.call_count, 1)
            game_id = get_open_games('connect_four')[0][0]

            # P2 joins
            handle_connect_four_command(p2_num, mock_interface)
            state_p2 = get_user_state(p2_num)
            handle_connect_four_steps(p2_num, '2', state_p2['step'], state_p2, mock_interface) # Remote
            state_p2 = get_user_state(p2_num)
            handle_connect_four_steps(p2_num, '2', state_p2['step'], state_p2, mock_interface) # Join Game
            self.assertEqual(mock_driver_send.call_count, 2) # show_open_games
            state_p2 = get_user_state(p2_num)
            handle_connect_four_steps(p2_num, str(game_id), state_p2['step'], state_p2, mock_interface) # Select Game
            self.assertEqual(mock_driver_send.call_count, 3) # join_game_by_id

            # P1 makes a move
            state_p1 = get_user_state(p1_num)
            handle_connect_four_steps(p1_num, '4', state_p1['step'], state_p1, mock_interface)
            # This should send one message to P1 and one to P2
            self.assertEqual(mock_driver_send.call_count, 5)
            self.assertIn("has made a move. It's your turn", mock_driver_send.call_args_list[-2][0][0]) # Message to P2
            self.assertIn("Move made. Waiting for opponent", mock_driver_send.call_args_list[-1][0][0]) # Message to P1

if __name__ == '__main__':
    unittest.main()
