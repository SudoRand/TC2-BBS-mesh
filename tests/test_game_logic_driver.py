import unittest
import sqlite3
import json
import os
import sys
import tempfile
import shutil
from unittest.mock import patch, MagicMock

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from db_operations import initialize_database, create_game, join_game, get_game_by_id, update_game_board
from modules.Games.game_interface import GameInterface
from modules.Games.game_logic_driver import GameLogicDriver

class MockGame(GameInterface):
    @property
    def game_type(self):
        return 'mock_game'
    def get_initial_board(self):
        return [" "] * 4
    def render_board(self, board, player_x_name, player_o_name):
        return f"Board: {''.join(board)}"
    def get_instruction_board(self):
        return "Mock Instructions"
    def handle_move(self, board, move, player_symbol):
        pos = int(move)
        board[pos] = player_symbol
        return board
    def check_winner(self, board):
        if "XX" in "".join(board): return "X"
        if "OO" in "".join(board): return "O"
        return None

class TestGameLogicDriver(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.original_cwd = os.getcwd()
        os.chdir(self.test_dir)
        self.patcher = patch('db_operations.get_db_connection', return_value=sqlite3.connect('test.db'))
        self.mock_db = self.patcher.start()
        initialize_database()

        self.mock_interface = MagicMock()
        self.p1_num, self.p1_id, self.p1_sn = 111, '!p1', 'P1'
        self.p2_num, self.p2_id, self.p2_sn = 222, '!p2', 'P2'
        self.mock_interface.nodes = {
            self.p1_id: {'num': self.p1_num, 'user': {'shortName': self.p1_sn}},
            self.p2_id: {'num': self.p2_num, 'user': {'shortName': self.p2_sn}},
        }
        self.get_node_id_patcher = patch('utils.get_node_id_from_num', side_effect=lambda num, iface: {self.p1_num: self.p1_id, self.p2_num: self.p2_id}.get(int(num)))
        self.mock_get_node_id = self.get_node_id_patcher.start()
        self.send_message_patcher = patch('modules.Games.game_logic_driver.send_message')
        self.mock_send_message = self.send_message_patcher.start()
        self.update_user_state_patcher = patch('modules.Games.game_logic_driver.update_user_state')
        self.mock_update_user_state = self.update_user_state_patcher.start()
        self.mock_game = MockGame()
        self.driver = GameLogicDriver(self.mock_game, self.mock_interface)

    def tearDown(self):
        self.patcher.stop()
        self.send_message_patcher.stop()
        self.update_user_state_patcher.stop()
        self.get_node_id_patcher.stop()
        self.mock_db.return_value.close()
        os.chdir(self.original_cwd)
        shutil.rmtree(self.test_dir)

    def test_board_sent_in_separate_message(self):
        # 1. Create a game
        board_after_move = ["X", " ", " ", " "]
        game_id = self.driver.create_game_with_first_move(self.p1_num, board_after_move)

        # 2. Check that send_message was called twice
        self.assertEqual(self.mock_send_message.call_count, 2)

        # 3. Check that the first message is the pre-board text
        self.assertIn(f"Your game (ID: {game_id}) is now listed", self.mock_send_message.call_args_list[0][0][0])

        # 4. Check that the second message is the board
        self.assertIn("Board: X   ", self.mock_send_message.call_args_list[1][0][0])

    def test_join_game_by_id(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps(["X", " ", " ", " "]))
        with patch('modules.Games.game_logic_driver.get_node_short_name', side_effect=['P1', 'P2']):
            returned_game_id = self.driver.join_game_by_id(self.p2_num, str(game_id))

        self.assertEqual(returned_game_id, game_id)
        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[3], str(self.p2_num))
        self.assertEqual(db_game[5], str(self.p2_num))

        # Check that P2 (the joining player) gets all the info
        self.assertEqual(self.mock_send_message.call_count, 3)
        self.assertIn(f"You joined game {game_id}", self.mock_send_message.call_args_list[0][0][0])
        self.assertIn("Mock Instructions", self.mock_send_message.call_args_list[0][0][0])
        self.assertIn("Board: X   ", self.mock_send_message.call_args_list[1][0][0])
        self.assertIn("It's your turn (O)", self.mock_send_message.call_args_list[2][0][0])

    def test_play_move_and_notify(self):
        game_id = create_game('mock_game', str(self.p1_num), json.dumps(["X", " ", " ", " "]))
        join_game(game_id, str(self.p2_num))
        update_game_board(game_id, json.dumps(["X", " ", " ", " "]), str(self.p2_num))


        state_p2 = {'game_id': game_id}
        with patch('modules.Games.game_logic_driver.get_node_short_name', side_effect=['P1', 'P2', 'P2', 'P1']):
            self.driver.play_move(self.p2_num, "2", state_p2)

        self.assertEqual(self.mock_send_message.call_count, 5)

        # Notification to P1 (other player)
        self.assertEqual(self.mock_send_message.call_args_list[0][0][1], self.p1_num)
        self.assertIn("Player P2 has joined your game!", self.mock_send_message.call_args_list[0][0][0])
        self.assertEqual(self.mock_send_message.call_args_list[1][0][1], self.p1_num)
        self.assertIn("Board: X O ", self.mock_send_message.call_args_list[1][0][0])
        self.assertEqual(self.mock_send_message.call_args_list[2][0][1], self.p1_num)
        self.assertIn("It is your turn (X)", self.mock_send_message.call_args_list[2][0][0])


        # Confirmation to P2 (current player)
        self.assertEqual(self.mock_send_message.call_args_list[3][0][1], self.p2_num)
        self.assertIn("Board: X O ", self.mock_send_message.call_args_list[3][0][0])
        self.assertEqual(self.mock_send_message.call_args_list[4][0][1], self.p2_num)
        self.assertIn("Move made. Waiting for opponent", self.mock_send_message.call_args_list[4][0][0])

        db_game = get_game_by_id(game_id)
        self.assertEqual(db_game[5], str(self.p1_num))

    def test_show_games_and_menu(self):
        # P1 creates a game
        create_game('mock_game', str(self.p1_num), json.dumps([" ", " ", " ", " "]))
        # Another player (P3) creates a game
        p3_num = 333
        create_game('mock_game', str(p3_num), json.dumps([" ", " ", " ", " "]))

        with patch('modules.Games.game_logic_driver.get_node_short_name', return_value='P3'):
            self.driver.show_games_and_menu(self.p1_num, 'MOCK_CMD')

        # Expected:
        self.assertEqual(self.mock_send_message.call_count, 1)
        full_message = self.mock_send_message.call_args_list[0][0][0]

        # Check for P1's waiting game
        self.assertIn("You need opponent:\n[1] vs ?", full_message)

        # Check for P3's joinable game
        self.assertIn("Join game:\n[2] vs P3", full_message)

        # Check for menu
        self.assertIn("[N]ew Game", full_message)

    def test_show_games_and_menu_with_continuable(self):
        # P1 and P2 are in a game
        game_id = create_game('mock_game', str(self.p1_num), json.dumps([" " , " ", " ", " "]))
        join_game(game_id, str(self.p2_num))

        with patch('modules.Games.game_logic_driver.get_node_short_name', return_value='P2'):
            self.driver.show_games_and_menu(self.p1_num, 'MOCK_CMD')

        self.assertEqual(self.mock_send_message.call_count, 1)
        continuable_message = self.mock_send_message.call_args_list[0][0][0]
        self.assertIn("Opponent's turn:", continuable_message)
        self.assertIn(f"[{game_id}] vs P2", continuable_message)
        self.assertIn("[N]ew Game", continuable_message)

    def test_show_stats_menu(self):
        self.driver.show_stats_menu(self.p1_num, 'MOCK_CMD')
        self.mock_send_message.assert_called_once_with(
            "[M]y Stats\n[A]ctive Games\n[L]eaderboard\nE[X]IT",
            self.p1_num,
            self.mock_interface
        )
        self.mock_update_user_state.assert_called_once_with(
            self.p1_num,
            {'command': 'MOCK_CMD', 'step': 2}
        )

    def test_show_leaderboard(self):
        # P1 beats P2
        game1_id = create_game('mock_game', str(self.p1_num), '[]')
        join_game(game1_id, str(self.p2_num))
        update_game_board(game1_id, '[]', str(self.p1_num))
        from db_operations import end_game
        end_game(game1_id, str(self.p1_num))

        # P2 and P1 tie
        game2_id = create_game('mock_game', str(self.p2_num), '[]')
        join_game(game2_id, str(self.p1_num))
        update_game_board(game2_id, '[]', str(self.p2_num))
        end_game(game2_id, 'tie')

        with patch('modules.Games.game_logic_driver.get_node_short_name', side_effect=['P1', 'P2']):
            self.driver.show_leaderboard(self.p1_num)

        self.mock_send_message.assert_called_once()
        leaderboard_text = self.mock_send_message.call_args[0][0]
        self.assertIn("MOCK_GAME LEADERBOARD", leaderboard_text)
        self.assertIn("1. P1: 4 pts (1W-1T-0L)", leaderboard_text)
        self.assertIn("2. P2: 1 pts (0W-1T-1L)", leaderboard_text)

    def test_show_player_stats(self):
        # P1 beats P2
        game1_id = create_game('mock_game', str(self.p1_num), '[]')
        join_game(game1_id, str(self.p2_num))
        update_game_board(game1_id, '[]', str(self.p1_num))
        from db_operations import end_game
        end_game(game1_id, str(self.p1_num))

        # P2 and P1 tie
        game2_id = create_game('mock_game', str(self.p2_num), '[]')
        join_game(game2_id, str(self.p1_num))
        update_game_board(game2_id, '[]', str(self.p2_num))
        end_game(game2_id, 'tie')

        with patch('modules.Games.game_logic_driver.get_node_short_name', side_effect=['P1', 'P2', 'P1', 'P2']):
            self.driver.show_player_stats(self.p1_num)

        self.mock_send_message.assert_called_once()
        stats_text = self.mock_send_message.call_args[0][0]
        self.assertIn("STATS for P1", stats_text)
        self.assertIn("Rank: 1/2 | Points: 4", stats_text)
        self.assertIn("Overall: 1W-1T-0L", stats_text)
        self.assertIn("Vs:", stats_text)
        self.assertIn("P2: 1W-1T-0L", stats_text)

    def test_show_active_games(self):
        # P1 vs P2
        game1_id = create_game('mock_game', str(self.p1_num), '[]')
        join_game(game1_id, str(self.p2_num))

        # P1 vs P3 (waiting)
        p3_num = 333
        p3_id = '!p3'
        p3_sn = 'P3'
        self.mock_interface.nodes[p3_id] = {'num': p3_num, 'user': {'shortName': p3_sn}}
        self.mock_get_node_id.side_effect = lambda num, iface: {self.p1_num: self.p1_id, self.p2_num: self.p2_id, p3_num: p3_id}.get(int(num))
        game2_id = create_game('mock_game', str(self.p1_num), '[]')


        with patch('modules.Games.game_logic_driver.get_node_short_name', side_effect=['P1', 'P2', 'P1', 'P3']):
            self.driver.show_active_games(self.p1_num)

        self.mock_send_message.assert_called_once()
        active_games_text = self.mock_send_message.call_args[0][0]
        self.assertIn("ACTIVE MOCK_GAME GAMES", active_games_text)
        self.assertIn("P1 vs P2", active_games_text)
        self.assertNotIn("P1 vs ?", active_games_text)


if __name__ == '__main__':
    unittest.main()
