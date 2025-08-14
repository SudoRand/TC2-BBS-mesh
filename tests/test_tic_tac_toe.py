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

from db_operations import (
    initialize_database,
    create_game,
    get_open_games,
    get_active_games_for_player,
    join_game,
    get_game_by_id,
    update_game_board,
    end_game
)
from modules.Games.tic_tac_toe import TicTacToeGame, handle_tic_tac_toe_steps, handle_tic_tac_toe_command, INSTRUCTION_BOARD
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

        with open('fortunes.txt', 'w') as f:
            f.write('test fortune\n')

        initialize_database()
        self.game_instance = TicTacToeGame()
        self.initial_board_json = json.dumps(self.game_instance.get_initial_board())


    def tearDown(self):
        self.get_db_connection_patcher.stop()
        self.conn.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_create_game(self):
        game_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        self.assertIsNotNone(game_id)
        games = get_open_games(self.game_instance.game_type)
        self.assertEqual(len(games), 1)
        self.assertEqual(games[0][1], "player1")

    def test_join_game(self):
        game_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        games = get_open_games(self.game_instance.game_type)
        game_db_id = games[0][0]
        join_game(game_db_id, "player2")
        game = get_game_by_id(game_db_id)
        self.assertEqual(game[3], "player2") # player_o is column 3
        self.assertEqual(game[7], "in_progress") # status is column 7

    def test_make_move(self):
        game_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        join_game(game_id, "player2")

        board = json.loads(get_game_by_id(game_id)[4]) # board is column 4
        board[0] = "X"
        update_game_board(game_id, json.dumps(board), "player2")

        game = get_game_by_id(game_id)
        new_board = json.loads(game[4])
        self.assertEqual(new_board[0], "X")
        self.assertEqual(game[5], "player2") # current_player is column 5

    def test_win_game(self):
        game_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        join_game(game_id, "player2")

        board = ["X", "X", "X", " ", " ", " ", " ", " ", " "]
        self.assertEqual(self.game_instance.check_winner(board), "X")

        end_game(game_id, "player1")
        game = get_game_by_id(game_id)
        self.assertEqual(game[6], "player1") # winner is column 6
        self.assertEqual(game[7], "finished") # status is column 7

    def test_draw_game(self):
        game_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        join_game(game_id, "player2")

        board = ["X", "O", "X", "X", "O", "X", "O", "X", "O"]
        self.assertEqual(self.game_instance.check_winner(board), "draw")

        end_game(game_id, "draw")
        game = get_game_by_id(game_id)
        self.assertEqual(game[6], "draw") # winner is column 6
        self.assertEqual(game[7], "finished")

    def test_get_active_games_for_player(self):
        game1_id = create_game(self.game_instance.game_type, "player1", self.initial_board_json)
        game2_id = create_game(self.game_instance.game_type, "player3", self.initial_board_json)
        join_game(game1_id, "player2")

        player1_games = get_active_games_for_player(self.game_instance.game_type, "player1")
        self.assertEqual(len(player1_games), 1)
        self.assertEqual(player1_games[0][0], game1_id)

        end_game(game1_id, "player1")
        player1_games_after_end = get_active_games_for_player(self.game_instance.game_type, "player1")
        self.assertEqual(len(player1_games_after_end), 0)

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_continue_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111; p1_id = '!p1'; p1_sn = 'P1'
        p2_num = 222; p2_id = '!p2'; p2_sn = 'P2'
        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}},
            p2_id: {'num': p2_num, 'user': {'shortName': p2_sn}},
        }

        game_id = create_game(self.game_instance.game_type, str(p1_num), self.initial_board_json)
        join_game(game_id, str(p2_num))
        update_game_board(game_id, self.initial_board_json, str(p2_num))

        with patch('modules.Games.game_logic_driver.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: p1_id, p2_num: p2_id}.get(int(num))):
            # 1. Player goes to the tic-tac-toe menu
            handle_tic_tac_toe_command(p1_num, mock_interface)
            self.assertEqual(mock_ttt_send.call_count, 1)
            self.assertIn("[4] Continue Remote Game", mock_ttt_send.call_args[0][0])

            # 2. Player chooses to continue a game
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, "4", state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_ttt_send.call_count, 2)
            self.assertIn(f"ID: {game_id}, Opponent: {p2_sn}, Status: in_progress", mock_ttt_send.call_args[0][0])

            # 3. Player chooses the game to continue, which calls the driver
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, str(game_id), state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 1)
            self.assertIn(f"It's {p2_sn} (O)'s turn.", mock_driver_send.call_args[0][0])

    @patch('modules.Games.game_logic_driver.send_message')
    def test_list_open_games_displays_short_name(self, mock_send_message):
        mock_interface = MagicMock()
        p1_num = 12345; p1_id = '!p1'; p1_sn = 'P1'
        mock_interface.nodes = { p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}} }

        with patch('modules.Games.game_logic_driver.get_node_id_from_num', return_value=p1_id):
            create_game(self.game_instance.game_type, str(p1_num), self.initial_board_json)
            state = {'command': 'TIC_TAC_TOE', 'step': 10}
            handle_tic_tac_toe_steps('some_other_player', "2", 10, state, mock_interface)

        self.assertEqual(mock_send_message.call_count, 1)
        self.assertIn(f"Started by: {p1_sn}", mock_send_message.call_args[0][0])

    @patch('modules.Games.game_logic_driver.send_message')
    @patch('modules.Games.tic_tac_toe.send_message')
    def test_remote_game_flow(self, mock_ttt_send, mock_driver_send):
        mock_interface = MagicMock()
        p1_num = 111; p1_id = '!p1'; p1_sn = 'P1'
        p2_num = 222; p2_id = '!p2'; p2_sn = 'P2'
        mock_interface.nodes = {
            p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}},
            p2_id: {'num': p2_num, 'user': {'shortName': p2_sn}},
        }
        with patch('modules.Games.game_logic_driver.get_node_id_from_num', side_effect=lambda num, iface: {p1_num: p1_id, p2_num: p2_id}.get(int(num))):
            # P1 starts
            handle_tic_tac_toe_command(p1_num, mock_interface)
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, '3', state_p1['step'], state_p1, mock_interface) # Remote
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, '1', state_p1['step'], state_p1, mock_interface) # New
            self.assertEqual(mock_driver_send.call_count, 1)
            game_id = get_open_games('tic_tac_toe')[0][0]

            # P2 joins
            handle_tic_tac_toe_command(p2_num, mock_interface)
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, '3', state_p2['step'], state_p2, mock_interface) # Remote
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, '2', state_p2['step'], state_p2, mock_interface) # Join
            state_p2 = get_user_state(p2_num)
            handle_tic_tac_toe_steps(p2_num, str(game_id), state_p2['step'], state_p2, mock_interface) # Select
            self.assertEqual(mock_driver_send.call_count, 3)

            # P1 makes a move
            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, "5", state_p1['step'], state_p1, mock_interface)
            self.assertEqual(mock_driver_send.call_count, 5)
            self.assertIn("has made a move. It's your turn", mock_driver_send.call_args_list[-2][0][0])
            self.assertIn("Move made. Waiting for opponent", mock_driver_send.call_args_list[-1][0][0])

    @patch('command_handlers.handle_help_command')
    @patch('modules.Games.game_logic_driver.send_message')
    def test_pause_and_resume_game(self, mock_driver_send, mock_help):
        mock_interface = MagicMock()
        p1_num = 111; p1_id = '!p1'; p1_sn = 'P1'
        mock_interface.nodes = { p1_id: {'num': p1_num, 'user': {'shortName': p1_sn}} }
        mock_interface.myInfo.my_node_num = 999

        with patch('modules.Games.game_logic_driver.get_node_id_from_num', return_value=p1_id):
            state_p1 = {'command': 'TIC_TAC_TOE', 'step': 10}
            handle_tic_tac_toe_steps(p1_num, "1", 10, state_p1, mock_interface)
            game_id = get_open_games('tic_tac_toe')[0][0]

            state_p1 = get_user_state(p1_num)
            handle_tic_tac_toe_steps(p1_num, "x", state_p1['step'], state_p1, mock_interface)
            mock_help.assert_called_once_with(p1_num, mock_interface)

            from message_processing import main_menu_handlers
            main_menu_handlers['rg'](p1_num, mock_interface)

            self.assertEqual(mock_driver_send.call_count, 2) # Create game + resume
            self.assertIn("It's your turn (X).", mock_driver_send.call_args[0][0])

if __name__ == '__main__':
    unittest.main()
