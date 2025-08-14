from abc import ABC, abstractmethod

class GameInterface(ABC):
    """
    An interface for turn-based games.

    This class defines the methods that any game wishing to use the
    GameLogicDriver must implement.
    """

    @property
    @abstractmethod
    def game_type(self):
        """
        A unique string identifying the game type, e.g., 'tic_tac_toe'.
        """
        pass

    @abstractmethod
    def get_initial_board(self):
        """
        Returns the initial state of the game board.
        This is typically a list or other serializable object.
        """
        pass

    @abstractmethod
    def render_board(self, board, player_x_name, player_o_name):
        """
        Renders the game board as a string for display to the user.

        Args:
            board: The current state of the board.
            player_x_name (str): The short name of Player X.
            player_o_name (str): The short name of Player O.

        Returns:
            str: A string representation of the board.
        """
        pass

    @abstractmethod
    def get_instruction_board(self):
        """
        Returns a string containing instructions for how to play,
        often including a numbered reference board.

        Returns:
            str: The instruction text.
        """
        pass

    @abstractmethod
    def handle_move(self, board, move, player_symbol):
        """
        Processes a player's move, validates it, and updates the board.

        Args:
            board: The current state of the board.
            move (str): The move input from the player.
            player_symbol (str): The symbol of the current player ('X' or 'O').

        Returns:
            The updated board state.

        Raises:
            ValueError: If the move is invalid.
        """
        pass

    @abstractmethod
    def check_winner(self, board):
        """
        Checks the board for a winner or a draw.

        Args:
            board: The current state of the board.

        Returns:
            str: The symbol of the winner ('X' or 'O'), 'draw' if the game is a draw,
                 or None if the game is still in progress.
        """
        pass

    def get_computer_move(self, board):
        """
        Determines the computer's move for single-player games.
        The default implementation indicates that a computer opponent is not supported.

        Args:
            board: The current state of the board.

        Returns:
            A valid move for the computer.

        Raises:
            NotImplementedError: If the game does not support a computer opponent.
        """
        raise NotImplementedError("This game does not support a computer opponent.")
