from __future__ import annotations

# ============================================================
# FULLY COMMENTED LUDO PROGRAM
# ============================================================
#
# This file contains:
#
#   1) A Ludo game engine
#   2) A turtle-based visual board
#   3) A clearly documented AI player interface
#   4) One simple AI class that is instantiated once per player
#
# ------------------------------------------------------------
# HOW STUDENT AI INTEGRATION WORKS
# ------------------------------------------------------------
#
# Students should create a NEW class that subclasses PlayerAgent.
#
# Example:
#
#     class MyStudentAI(PlayerAgent):
#         def select_move(self, state, player_id, roll, legal_moves):
#             if not legal_moves:
#                 return None
#             return legal_moves[0]
#
# Then replace any player in the agents list:
#
#     agents = [
#         MyStudentAI(),   # Red player
#         SimpleAI(),      # Green player
#         SimpleAI(),      # Yellow player
#         SimpleAI(),      # Blue player
#     ]
#
# The board / engine side of the AI hook is intentionally kept
# in ONE MAIN METHOD:
#
#     LudoGame.run_player_turn(...)
#
# That method is responsible for:
#   - rolling the die
#   - generating legal moves
#   - asking the player's AI to choose a move
#   - validating that move
#   - applying the move
#   - handling extra turns on a 6
#   - recording events
#
# That means students only need to supply a substitute class
# for one or more players. They do NOT need to change the board.
#
# ------------------------------------------------------------
# CONTROLS
# ------------------------------------------------------------
#
#   SPACE = play one full turn
#   A     = toggle autoplay on/off
#   R     = redraw board
#
# ------------------------------------------------------------
# RULES ENFORCED
# ------------------------------------------------------------
#
#   - Roll a 6 to leave base
#   - Dice rolls are handled by the engine
#   - Exact roll is required to finish
#   - Star squares are safe
#   - Start squares are safe
#   - Captures send enemy piece back to base
#   - If a player has 2+ pieces on one outer-track square,
#     that square becomes safe and opponents cannot land there
#   - Extra turn on rolling 6
#   - Triple 6 forfeits the rest of the turn
#
# ------------------------------------------------------------
# RULE NOT ENFORCED
# ------------------------------------------------------------
#
#   - Opponents ARE allowed to pass through stacked squares
#
# ============================================================

import random
import turtle
import os
import sys
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional


# ============================================================
# TYPE ALIASES
# ============================================================
#
# These are just readable names for primitive types used
# throughout the program.

PlayerId = int                     # Which player: 0..3
PieceId = int                      # Which piece: 0..3
Move = Tuple[int, int]             # (piece_index, new_progress)


# ============================================================
# EVENT DATA
# ============================================================
#
# The engine records events during a turn. These are useful for:
#   - debugging
#   - logging
#   - teaching
#   - AI observation / learning
#
# Example event:
#   Event("capture", {"by": 0, "captured_player": 2, ...})

@dataclass(frozen=True)
class Event:
    type: str
    data: Dict[str, Any]


# ============================================================
# GAME CONFIGURATION
# ============================================================
#
# Central place to adjust board size and rules if needed.

@dataclass
class GameConfig:
    # Number of players and pieces
    num_players: int = 4
    pieces_per_player: int = 4

    # Standard Ludo movement dimensions:
    #   - 52 shared outer-track squares
    #   - 6 private home-lane squares per player
    #   - final finish position at progress 57
    track_len: int = 52
    home_len: int = 6
    finish_pos: int = 57

    # Must roll this value to leave base
    enter_on_roll: int = 6

    # Whether exact roll is required to reach finish
    require_exact_finish: bool = True

    # Static safe squares on the shared outer track
    start_squares_safe: bool = True
    star_safe_squares: Tuple[int, ...] = (8, 21, 34, 47)

    # If a player has 2+ pieces on the same outer square,
    # that square becomes safe and opponents cannot land there
    stack_creates_safe: bool = True

    # Extra turn rules
    extra_roll_on: int = 6
    triple_extra_roll_forfeit: bool = True


# ============================================================
# AI INTERFACE / STUDENT HOOK CLASS
# ============================================================
#
# Students should subclass THIS class.
#
# The board never needs to know the specific subclass name.
# It only calls these methods.
#
# The most important hook is:
#
#     select_move(state, player_id, roll, legal_moves)
#
# Students receive:
#   - the full visible state
#   - their player id
#   - the die roll
#   - the legal moves they are allowed to choose from
#
# They must return:
#   - one move from legal_moves
#   - or None if there are no legal moves
#
# A move is a tuple:
#   (piece_index, new_progress)
#
# Example:
#   (2, 17)
# means "move piece 2 so its new progress becomes 17"

class PlayerAgent:
    """
    Base class for student AI integration.

    Students should subclass this and override one or more methods.

    REQUIRED IN PRACTICE:
        select_move(...)

    OPTIONAL:
        on_game_start(...)
        on_turn_start(...)
        on_turn_end(...)
    """

    def on_game_start(self, state: Dict[str, Any]) -> None:
        """
        Called once when the game is created.

        Parameters:
            state: full visible game state
        """
        pass

    def on_turn_start(self, state: Dict[str, Any], player_id: PlayerId) -> None:
        """
        Called at the beginning of the player's turn.

        Parameters:
            state: full visible game state
            player_id: which player this AI controls
        """
        pass

    def select_move(
        self,
        state: Dict[str, Any],
        player_id: PlayerId,
        roll: int,
        legal_moves: List[Move],
    ) -> Optional[Move]:
        """
        Choose one move from legal_moves.

        Parameters:
            state: full visible game state
            player_id: which player this AI controls
            roll: die roll for this decision
            legal_moves: list of legal moves

        Return:
            - one move from legal_moves
            - or None if no legal moves exist

        IMPORTANT:
            The engine expects the returned move to be exactly one
            of the legal moves provided.
        """
        return None

    def on_turn_end(self, state: Dict[str, Any], player_id: PlayerId, events: List[Event]) -> None:
        """
        Called after the player's full turn is complete.

        Parameters:
            state: updated visible game state
            player_id: which player this AI controls
            events: list of events that happened during the turn
        """
        pass


# ============================================================
# SIMPLE BUILT-IN AI
# ============================================================
#
# This is a separate class, instantiated once per player.
#
# Example:
#     agents = [SimpleAI(), SimpleAI(), SimpleAI(), SimpleAI()]
#
# Students can replace any player by substituting their own class:
#     agents = [MyStudentAI(), SimpleAI(), SimpleAI(), SimpleAI()]
#
# This AI is intentionally simple and easy to understand.

class SimpleAI(PlayerAgent):
    """
    A basic reference AI.

    Strategy:
      1) Prefer a capture
      2) Prefer finishing a piece
      3) Prefer entering a piece from base
      4) Otherwise move the piece with the largest resulting progress

    This class is completely separate from the board.
    The board only knows it as a PlayerAgent.
    """

    def select_move(self, state, player_id, roll, legal_moves):
        """
        Choose a move using a very simple scoring rule.
        """
        if not legal_moves:
            return None

        # Pull useful state fields out for readability
        cfg = state["config"]
        positions = state["positions"]
        start_offset = state["start_offset"]

        # Convert a player's local progress to a global shared track index
        def progress_to_track_index(pid, progress):
            if progress < 0 or progress >= cfg["track_len"]:
                return None
            return (start_offset[pid] + progress) % cfg["track_len"]

        # Build set of static safe squares
        static_safe = set(cfg["star_safe_squares"])
        if cfg["start_squares_safe"]:
            static_safe.update(start_offset)

        # Build shared-track occupancy map from visible state
        occ = {}
        for pid in range(cfg["num_players"]):
            for piece_id, progress in enumerate(positions[pid]):
                ti = progress_to_track_index(pid, progress)
                if ti is not None:
                    occ.setdefault(ti, []).append((pid, piece_id))

        # Determine if a square contains a stack owned by one player
        def stack_owner_if_any(track_index):
            counts = {}
            for pid, _piece in occ.get(track_index, []):
                counts[pid] = counts.get(pid, 0) + 1
            for pid, count in counts.items():
                if count >= 2:
                    return pid
            return None

        # Score each legal move
        scored_moves = []
        for move in legal_moves:
            piece_id, new_pos = move
            old_pos = positions[player_id][piece_id]

            capture_score = 0
            finish_score = 0
            enter_score = 0
            progress_score = new_pos

            # Prefer finishing
            if new_pos == cfg["finish_pos"]:
                finish_score = 1

            # Prefer entering from base
            if old_pos == -1 and new_pos == 0:
                enter_score = 1

            # Prefer captures when landing on non-safe outer squares
            if new_pos < cfg["track_len"]:
                ti = progress_to_track_index(player_id, new_pos)
                if ti is not None and ti not in static_safe:
                    owner = stack_owner_if_any(ti)
                    if owner is None:
                        for pid, _pc in occ.get(ti, []):
                            if pid != player_id:
                                capture_score += 1

            scored_moves.append((capture_score, finish_score, enter_score, progress_score, move))

        # Highest tuple wins
        scored_moves.sort(reverse=True)
        return scored_moves[0][-1]


# ============================================================
# STUDENT AI INTEGRATION HOOK
# ============================================================
#
# The professor's engine stays untouched; we only add a small
# bridge to load the student's AI class from a separate file.
#
# Expected location for student code:
#   /Users/jeeya/Downloads/AI/Ludo/student_ai.py
#
# If that file is present, we import StudentAI and use it for
# the Red player by default. If the import fails, the code
# falls back to SimpleAI so the game still runs.

STUDENT_AI = None
_candidate_path = os.path.join(os.path.dirname(__file__), "AI", "Ludo")
if os.path.exists(os.path.join(_candidate_path, "student_ai.py")):
    sys.path.insert(0, _candidate_path)

try:
    from student_ai import StudentAI  # type: ignore
    STUDENT_AI = StudentAI
except Exception as exc:  # noqa: BLE001
    # Keep running even if the student file is missing or broken
    print("[ludo_v5] StudentAI not loaded ({}). Using SimpleAI instead.".format(exc))


# ============================================================
# LUDO ENGINE
# ============================================================
#
# This class contains all board logic and game rules.
#
# IMPORTANT FOR STUDENT INTEGRATION:
#
# The main board-side AI hook happens in:
#
#     run_player_turn(...)
#
# That one method:
#   - rolls dice
#   - asks the player's AI for its move
#   - validates the move
#   - applies the move
#   - handles extra turns
#
# So if you want to understand where an AI connects to the board,
# that is the main method to look at.

class LudoGame:
    # Display names and colors used by the renderer/info panel
    PLAYER_NAMES = ["Red", "Green", "Yellow", "Blue"]
    PLAYER_COLORS = ["red", "green", "gold", "blue"]

    def __init__(
        self,
        agents: List[PlayerAgent],
        config: Optional[GameConfig] = None,
        seed: Optional[int] = None
    ):
        """
        Create a new Ludo game.

        Parameters:
            agents: one PlayerAgent instance per player
            config: optional GameConfig
            seed: optional RNG seed for reproducibility
        """
        self.cfg = config or GameConfig(num_players=len(agents))

        if len(agents) != self.cfg.num_players:
            raise ValueError("agents length must match config.num_players")

        # Random generator used for dice and fallback forced moves
        self.rng = random.Random(seed)

        # Store one AI object per player
        self.agents = agents

        # Piece positions:
        #   -1          = in base
        #    0..51      = on outer track (local progress for that player)
        #    52..57     = in home lane / finish path
        self.pos: List[List[int]] = [
            [-1 for _ in range(self.cfg.pieces_per_player)]
            for _ in range(self.cfg.num_players)
        ]

        # Start offsets on the shared 52-cell ring:
        # player 0 -> 0
        # player 1 -> 13
        # player 2 -> 26
        # player 3 -> 39
        step = self.cfg.track_len // self.cfg.num_players
        self.start_offset: List[int] = [i * step for i in range(self.cfg.num_players)]

        # Turn state
        self.current_player: PlayerId = 0
        self.winner: Optional[PlayerId] = None
        self.turn_counter: int = 0

        # Rendering / status support
        self.last_summary: Optional[Dict[str, Any]] = None
        self.last_rolls: List[int] = []

        # Notify all AIs that the game has started
        state = self.get_state()
        for agent in self.agents:
            agent.on_game_start(state)

    # --------------------------------------------------------
    # STATE EXPORT
    # --------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """
        Return the full visible game state.

        Students receive this state in their hook methods.
        """
        return {
            "config": self.cfg.__dict__.copy(),
            "positions": [row[:] for row in self.pos],
            "current_player": self.current_player,
            "start_offset": self.start_offset[:],
            "winner": self.winner,
            "turn_counter": self.turn_counter,
            "player_names": self.PLAYER_NAMES[:self.cfg.num_players],
            "player_colors": self.PLAYER_COLORS[:self.cfg.num_players],
        }

    # --------------------------------------------------------
    # BASIC RULE HELPERS
    # --------------------------------------------------------

    def roll_die(self) -> int:
        """
        Roll a standard 6-sided die.
        """
        return self.rng.randint(1, 6)

    def is_finished(self, player_id: PlayerId) -> bool:
        """
        Return True if all of a player's pieces are finished.
        """
        return all(p == self.cfg.finish_pos for p in self.pos[player_id])

    def progress_to_track_index(self, player_id: PlayerId, progress: int) -> Optional[int]:
        """
        Convert player-local outer-track progress to the shared outer-track index.

        Example:
            Red progress 0 -> global track index 0
            Green progress 0 -> global track index 13
            Yellow progress 0 -> global track index 26
            Blue progress 0 -> global track index 39
        """
        if progress < 0 or progress >= self.cfg.track_len:
            return None
        return (self.start_offset[player_id] + progress) % self.cfg.track_len

    def outer_static_safe(self) -> set[int]:
        """
        Return the set of static safe squares:
          - star squares
          - optionally the start squares
        """
        safe = set(self.cfg.star_safe_squares)
        if self.cfg.start_squares_safe:
            safe.update(self.start_offset)
        return safe

    def square_occupants(self) -> Dict[int, List[Tuple[PlayerId, PieceId]]]:
        """
        Build occupancy map for the shared outer track.

        Returns:
            {
                global_track_index: [(player_id, piece_id), ...]
            }

        Home-lane squares are not included here, because captures only
        happen on the shared outer track.
        """
        occ: Dict[int, List[Tuple[PlayerId, PieceId]]] = {}
        for pid in range(self.cfg.num_players):
            for piece_id, progress in enumerate(self.pos[pid]):
                ti = self.progress_to_track_index(pid, progress)
                if ti is not None:
                    occ.setdefault(ti, []).append((pid, piece_id))
        return occ

    def stack_owner_if_any(self, track_index: int) -> Optional[PlayerId]:
        """
        Return the player id if one player has 2+ pieces on a track square.
        Otherwise return None.
        """
        occ = self.square_occupants().get(track_index, [])
        counts: Dict[int, int] = {}
        for pid, _piece in occ:
            counts[pid] = counts.get(pid, 0) + 1

        for pid, count in counts.items():
            if count >= 2:
                return pid
        return None

    def is_safe_square(self, track_index: int) -> bool:
        """
        A square is safe if:
          - it is a static safe square, or
          - stack safety is enabled and someone has a 2+ stack there
        """
        if track_index in self.outer_static_safe():
            return True
        if self.cfg.stack_creates_safe and self.stack_owner_if_any(track_index) is not None:
            return True
        return False

    def landing_blocked_by_opponent_stack(self, mover: PlayerId, track_index: int) -> bool:
        """
        Opponents cannot LAND on a square occupied by a 2+ stack.
        """
        owner = self.stack_owner_if_any(track_index)
        return owner is not None and owner != mover

    # --------------------------------------------------------
    # MOVE GENERATION
    # --------------------------------------------------------

    def legal_moves_for_roll(self, player_id: PlayerId, roll: int) -> List[Move]:
        """
        Return all legal moves for a given player and die roll.
        """
        legal: List[Move] = []

        for piece_id, cur in enumerate(self.pos[player_id]):
            # If the piece is in base, it can only enter on the configured roll
            if cur == -1:
                if roll != self.cfg.enter_on_roll:
                    continue

                new_pos = 0
                ti = self.progress_to_track_index(player_id, new_pos)
                if ti is None:
                    continue

                if self.landing_blocked_by_opponent_stack(player_id, ti):
                    continue

                legal.append((piece_id, new_pos))
                continue

            # Already finished -> cannot move
            if cur == self.cfg.finish_pos:
                continue

            # Regular move
            new_pos = cur + roll

            # Exact finish required
            if new_pos > self.cfg.finish_pos:
                continue

            # If landing on shared outer track, cannot land on opponent stack
            if new_pos < self.cfg.track_len:
                ti = self.progress_to_track_index(player_id, new_pos)
                if ti is None:
                    continue
                if self.landing_blocked_by_opponent_stack(player_id, ti):
                    continue

            legal.append((piece_id, new_pos))

        return legal

    # --------------------------------------------------------
    # MOVE APPLICATION
    # --------------------------------------------------------

    def apply_move(self, player_id: PlayerId, move: Move) -> List[Event]:
        """
        Apply a chosen move and return the list of generated events.
        """
        piece_id, new_pos = move
        events: List[Event] = []

        # Move the piece
        old_pos = self.pos[player_id][piece_id]
        self.pos[player_id][piece_id] = new_pos

        events.append(Event("move", {
            "player": player_id,
            "piece": piece_id,
            "from": old_pos,
            "to": new_pos,
        }))

        # If the piece is now in the home lane / finish area,
        # no capture can happen there
        if new_pos >= self.cfg.track_len:
            if new_pos == self.cfg.finish_pos:
                events.append(Event("piece_finished", {
                    "player": player_id,
                    "piece": piece_id,
                }))
            return events

        # Otherwise, we landed on the shared outer track
        landing_ti = self.progress_to_track_index(player_id, new_pos)
        if landing_ti is None:
            return events

        # Safe square -> no capture
        if self.is_safe_square(landing_ti):
            events.append(Event("safe_square", {
                "player": player_id,
                "piece": piece_id,
                "track_index": landing_ti,
            }))
            return events

        # Capture all enemy pieces on that outer-track square
        occ = self.square_occupants().get(landing_ti, [])
        for op_pid, op_piece in occ:
            if op_pid != player_id:
                self.pos[op_pid][op_piece] = -1
                events.append(Event("capture", {
                    "by": player_id,
                    "piece": piece_id,
                    "captured_player": op_pid,
                    "captured_piece": op_piece,
                    "track_index": landing_ti,
                }))

        return events

    # --------------------------------------------------------
    # MAIN AI-INTEGRATION METHOD
    # --------------------------------------------------------
    #
    # This is the main board-side hook method for AI players.
    #
    # The board calls ONE player's AI from this method.
    #
    # This is the method students / instructors should understand
    # if they want to see how an AI integrates with the board.

    def run_player_turn(self, player_id: PlayerId) -> Dict[str, Any]:
        """
        Run one complete turn for a single player.

        This method:
          - calls on_turn_start(...)
          - rolls the die
          - generates legal moves
          - calls select_move(...)
          - validates / fixes bad choices
          - applies the move
          - handles extra rolls on 6
          - calls on_turn_end(...)

        This is the main board-side integration point for AI players.
        """
        # If game is already over, do nothing
        if self.winner is not None:
            summary = {"status": "game_over", "winner": self.winner}
            self.last_summary = summary
            return summary

        # Get the agent for the current player
        agent = self.agents[player_id]

        # Notify AI that turn is starting
        agent.on_turn_start(self.get_state(), player_id)

        events: List[Event] = []
        rolls: List[int] = []
        consecutive_sixes = 0

        # A single Ludo turn may include multiple rolls if the player rolls 6
        while True:
            # Roll die
            roll = self.roll_die()
            rolls.append(roll)
            events.append(Event("roll", {"player": player_id, "roll": roll}))

            # Triple-six forfeit rule
            if self.cfg.triple_extra_roll_forfeit and roll == self.cfg.extra_roll_on:
                consecutive_sixes += 1
                if consecutive_sixes >= 3:
                    events.append(Event("triple_six_forfeit", {"player": player_id}))
                    break
            else:
                consecutive_sixes = 0

            # Generate legal moves for this roll
            legal_moves = self.legal_moves_for_roll(player_id, roll)

            # Ask the player's AI what move it wants to make
            chosen = agent.select_move(self.get_state(), player_id, roll, legal_moves)

            # If AI returned None but a move existed, force a random legal move
            if chosen is None:
                if legal_moves:
                    chosen = self.rng.choice(legal_moves)
                    events.append(Event("agent_none_forced", {
                        "player": player_id,
                        "forced": chosen,
                    }))
                else:
                    # No legal moves at all
                    events.append(Event("pass_no_legal_moves", {"player": player_id}))
                    break

            # If AI returned an illegal move, force a random legal move
            if chosen not in legal_moves:
                forced = self.rng.choice(legal_moves) if legal_moves else None
                events.append(Event("agent_illegal_forced", {
                    "player": player_id,
                    "chosen": chosen,
                    "forced": forced,
                }))
                if forced is None:
                    break
                chosen = forced

            # Apply the chosen move
            events.extend(self.apply_move(player_id, chosen))

            # Check win condition
            if self.is_finished(player_id):
                self.winner = player_id
                events.append(Event("win", {"player": player_id}))
                break

            # If the player rolled a 6, they get another roll
            if roll == self.cfg.extra_roll_on:
                events.append(Event("extra_roll", {"player": player_id}))
                continue

            # Otherwise turn ends
            break

        # Notify AI that turn ended
        agent.on_turn_end(self.get_state(), player_id, events)

        # Build turn summary
        self.last_rolls = rolls[:]
        summary = {
            "status": "ok",
            "player": player_id,
            "rolls": rolls,
            "events": events,
            "winner": self.winner,
        }
        self.last_summary = summary
        return summary

    # --------------------------------------------------------
    # TURN ADVANCE
    # --------------------------------------------------------

    def step_turn(self) -> Dict[str, Any]:
        """
        Advance the game by one player's turn.
        """
        if self.winner is not None:
            summary = {"status": "game_over", "winner": self.winner}
            self.last_summary = summary
            return summary

        player_id = self.current_player
        self.turn_counter += 1

        summary = self.run_player_turn(player_id)

        # Advance to next player after this turn completes
        self.current_player = (self.current_player + 1) % self.cfg.num_players
        return summary


# ============================================================
# TURTLE BOARD RENDERER
# ============================================================
#
# This class only draws the game. It does not contain game logic.

class TurtleLudoRenderer:
    # Pixel size of one board cell
    CELL = 34

    def __init__(self, game: LudoGame):
        """
        Create renderer and cache board geometry.
        """
        self.game = game

        # Create turtle window
        self.screen = turtle.Screen()
        self.screen.title("Ludo Board")
        self.screen.setup(width=1250, height=900)
        self.screen.bgcolor("white")

        # Pen used for board background / cell drawing
        self.pen = turtle.Turtle(visible=False)
        self.pen.speed(0)
        self.pen.penup()

        # Pen used for status text
        self.info_pen = turtle.Turtle(visible=False)
        self.info_pen.speed(0)
        self.info_pen.penup()

        # Pen used for pieces
        self.piece_pen = turtle.Turtle(visible=False)
        self.piece_pen.speed(0)
        self.piece_pen.penup()

        # Pen used for drawing die panel
        self.dice_pen = turtle.Turtle(visible=False)
        self.dice_pen.speed(0)
        self.dice_pen.penup()

        # Top-left board origin in screen coordinates
        self.origin_x = -255
        self.origin_y = 255

        self.player_colors = ["red", "green", "gold", "blue"]

        # Board cell maps
        self.track_cells = self._build_outer_track_cells()
        if len(self.track_cells) != 52:
            raise ValueError(f"track_cells must contain 52 cells, got {len(self.track_cells)}")

        self.home_lane_cells = self._build_home_lane_cells()
        self.base_piece_cells = self._build_base_piece_cells()

    # --------------------------------------------------------
    # GEOMETRY HELPERS
    # --------------------------------------------------------

    def board_to_xy(self, row: int, col: int) -> Tuple[float, float]:
        """
        Convert board grid position (row, col) to turtle top-left cell corner.
        """
        x = self.origin_x + col * self.CELL
        y = self.origin_y - row * self.CELL
        return x, y

    def cell_center(self, row: int, col: int) -> Tuple[float, float]:
        """
        Return center pixel coordinate of a board cell.
        """
        x, y = self.board_to_xy(row, col)
        return x + self.CELL / 2, y - self.CELL / 2

    # --------------------------------------------------------
    # BASIC DRAWING HELPERS
    # --------------------------------------------------------

    def draw_square(self, row: int, col: int, fill: str = "white", outline: str = "black"):
        """
        Draw one filled board cell.
        """
        x, y = self.board_to_xy(row, col)
        self.pen.goto(x, y)
        self.pen.color(outline, fill)
        self.pen.setheading(0)
        self.pen.pendown()
        self.pen.begin_fill()
        for _ in range(4):
            self.pen.forward(self.CELL)
            self.pen.right(90)
        self.pen.end_fill()
        self.pen.penup()

    def draw_text_in_cell(self, row: int, col: int, text: str, size: int = 8, color: str = "black"):
        """
        Draw centered text inside one board cell.
        """
        cx, cy = self.cell_center(row, col)
        self.pen.goto(cx, cy - size / 2)
        self.pen.color(color)
        self.pen.write(text, align="center", font=("Arial", size, "normal"))

    def draw_star_in_cell(self, row: int, col: int, color: str = "black"):
        """
        Draw a star marker in a safe cell.
        """
        cx, cy = self.cell_center(row, col)
        self.pen.goto(cx, cy - 8)
        self.pen.color(color)
        self.pen.write("★", align="center", font=("Arial", 14, "bold"))

    # --------------------------------------------------------
    # BOARD MAPS
    # --------------------------------------------------------

    def _build_outer_track_cells(self) -> List[Tuple[int, int]]:
        """
        Return the 52-cell shared outer track in movement order.
        """
        return [
            (6, 1), (6, 2), (6, 3), (6, 4), (6, 5),
            (5, 6), (4, 6), (3, 6), (2, 6), (1, 6), (0, 6),
            (0, 7), (0, 8),
            (1, 8), (2, 8), (3, 8), (4, 8), (5, 8),
            (6, 9), (6,10), (6,11), (6,12), (6,13), (6,14),
            (7,14),
            (8,14), (8,13), (8,12), (8,11), (8,10), (8, 9),
            (9, 8), (10,8), (11,8), (12,8), (13,8), (14,8),
            (14,7), (14,6),
            (13,6), (12,6), (11,6), (10,6), (9, 6),
            (8, 5), (8, 4), (8, 3), (8, 2), (8, 1), (8, 0),
            (7, 0), (6, 0),
        ]

    def _build_home_lane_cells(self) -> Dict[int, List[Tuple[int, int]]]:
        """
        Return the 6-cell home lane for each player.
        """
        return {
            0: [(7,1), (7,2), (7,3), (7,4), (7,5), (7,6)],
            1: [(1,7), (2,7), (3,7), (4,7), (5,7), (6,7)],
            2: [(7,13), (7,12), (7,11), (7,10), (7,9), (7,8)],
            3: [(13,7), (12,7), (11,7), (10,7), (9,7), (8,7)],
        }

    def _build_base_piece_cells(self) -> Dict[int, List[Tuple[int, int]]]:
        """
        Return yard/base positions for each player's 4 starting pieces.
        """
        return {
            0: [(1,1), (1,3), (3,1), (3,3)],
            1: [(1,11), (1,13), (3,11), (3,13)],
            2: [(11,11), (11,13), (13,11), (13,13)],
            3: [(11,1), (11,3), (13,1), (13,3)],
        }

    # --------------------------------------------------------
    # BACKGROUND DRAWING
    # --------------------------------------------------------

    def _fill_rect(self, row0: int, col0: int, h: int, w: int, color: str):
        """
        Fill a rectangular region of cells with a color.
        """
        for r in range(row0, row0 + h):
            for c in range(col0, col0 + w):
                self.draw_square(r, c, color, "gray")

    def _draw_center_home(self):
        """
        Draw the center home region.
        """
        for r in range(6, 9):
            for c in range(6, 9):
                self.draw_square(r, c, "white", "black")
        self.draw_text_in_cell(7, 7, "HOME", size=12, color="black")

    def _draw_start_indicators(self):
        """
        Draw color letters at each player's entry/start square.
        """
        self.draw_text_in_cell(6, 1, "R", size=12, color="red")
        self.draw_text_in_cell(1, 8, "G", size=12, color="green")
        self.draw_text_in_cell(8, 13, "Y", size=12, color="goldenrod")
        self.draw_text_in_cell(13, 6, "B", size=12, color="blue")

    def draw_background_regions(self):
        """
        Draw the full static board.
        """
        # Base white grid
        for r in range(15):
            for c in range(15):
                self.draw_square(r, c, "white", "gray")

        # Player yard quadrants
        self._fill_rect(0, 0, 6, 6, "#ffd6d6")   # Red yard
        self._fill_rect(0, 9, 6, 6, "#d8f5d8")   # Green yard
        self._fill_rect(9, 9, 6, 6, "#fff1b8")   # Yellow yard
        self._fill_rect(9, 0, 6, 6, "#d8e8ff")   # Blue yard

        # Center
        self._draw_center_home()

        # Shared track
        for row, col in self.track_cells:
            self.draw_square(row, col, "white", "black")

        # Home lanes
        for row, col in self.home_lane_cells[0]:
            self.draw_square(row, col, "#ffb3b3", "black")
        for row, col in self.home_lane_cells[1]:
            self.draw_square(row, col, "#bff0bf", "black")
        for row, col in self.home_lane_cells[2]:
            self.draw_square(row, col, "#ffe680", "black")
        for row, col in self.home_lane_cells[3]:
            self.draw_square(row, col, "#b3d1ff", "black")

        # Labels / indicators
        self._draw_start_indicators()

        # Static star safe squares
        for ti in self.game.cfg.star_safe_squares:
            row, col = self.track_cells[ti]
            self.draw_star_in_cell(row, col)

        # Start squares
        for pid, ti in enumerate(self.game.start_offset):
            row, col = self.track_cells[ti]
            self.draw_text_in_cell(row, col, "S", size=12, color=self.player_colors[pid])

    # --------------------------------------------------------
    # PIECE DRAWING
    # --------------------------------------------------------

    def _draw_piece_with_label(self, row: int, col: int, color: str, piece_id: int):
        """
        Draw a full-size base piece with a label.
        """
        cx, cy = self.cell_center(row, col)
        self.piece_pen.goto(cx, cy - 10)
        self.piece_pen.dot(20, color)
        self.piece_pen.goto(cx, cy - 4)
        self.piece_pen.color("white")
        self.piece_pen.write(str(piece_id), align="center", font=("Arial", 9, "bold"))

    def _pieces_in_cell(self, row: int, col: int) -> List[Tuple[int, int]]:
        """
        Return all pieces currently displayed in a specific screen cell.
        Used so stacked pieces can be spread out visually.
        """
        result: List[Tuple[int, int]] = []

        for pid in range(self.game.cfg.num_players):
            for piece_id, progress in enumerate(self.game.pos[pid]):
                if progress == -1:
                    if self.base_piece_cells[pid][piece_id] == (row, col):
                        result.append((pid, piece_id))
                elif progress < self.game.cfg.track_len:
                    ti = self.game.progress_to_track_index(pid, progress)
                    if ti is not None and 0 <= ti < len(self.track_cells):
                        if self.track_cells[ti] == (row, col):
                            result.append((pid, piece_id))
                else:
                    lane_index = progress - self.game.cfg.track_len
                    if 0 <= lane_index < len(self.home_lane_cells[pid]):
                        if self.home_lane_cells[pid][lane_index] == (row, col):
                            result.append((pid, piece_id))

        return result

    def _draw_stacked_piece_on_cell(self, row: int, col: int, pid: int, piece_id: int):
        """
        Draw a smaller piece in a possibly crowded cell using offsets.
        """
        occupants = self._pieces_in_cell(row, col)
        color = self.player_colors[pid]

        try:
            idx = occupants.index((pid, piece_id))
        except ValueError:
            idx = 0

        offsets = [
            (-8, 8), (8, 8), (-8, -8), (8, -8),
            (0, 0), (-12, 0), (12, 0), (0, 12),
        ]
        dx, dy = offsets[idx % len(offsets)]

        cx, cy = self.cell_center(row, col)
        self.piece_pen.goto(cx + dx, cy + dy - 6)
        self.piece_pen.dot(14, color)
        self.piece_pen.goto(cx + dx, cy + dy - 11)
        self.piece_pen.color("white")
        self.piece_pen.write(str(piece_id), align="center", font=("Arial", 7, "bold"))

    def draw_pieces(self):
        """
        Draw all pieces in their current positions.
        """
        self.piece_pen.clear()

        for pid in range(self.game.cfg.num_players):
            color = self.player_colors[pid]
            for piece_id, progress in enumerate(self.game.pos[pid]):
                # Base
                if progress == -1:
                    row, col = self.base_piece_cells[pid][piece_id]
                    self._draw_piece_with_label(row, col, color, piece_id)

                # Shared outer track
                elif progress < self.game.cfg.track_len:
                    ti = self.game.progress_to_track_index(pid, progress)
                    if ti is not None and 0 <= ti < len(self.track_cells):
                        row, col = self.track_cells[ti]
                        self._draw_stacked_piece_on_cell(row, col, pid, piece_id)

                # Home lane / finish path
                else:
                    lane_index = progress - self.game.cfg.track_len
                    if 0 <= lane_index < len(self.home_lane_cells[pid]):
                        row, col = self.home_lane_cells[pid][lane_index]
                        self._draw_stacked_piece_on_cell(row, col, pid, piece_id)

    # --------------------------------------------------------
    # DIE PANEL
    # --------------------------------------------------------

    def draw_die(self):
        """
        Draw the most recent die result in a separate panel.
        """
        self.dice_pen.clear()

        # Positioned far enough right to avoid overlap with board/info
        x = 455
        y = 110
        size = 90

        self.dice_pen.goto(x, y)
        self.dice_pen.color("black", "white")
        self.dice_pen.setheading(0)
        self.dice_pen.pendown()
        self.dice_pen.begin_fill()
        for _ in range(4):
            self.dice_pen.forward(size)
            self.dice_pen.right(90)
        self.dice_pen.end_fill()
        self.dice_pen.penup()

        value = self.game.last_rolls[-1] if self.game.last_rolls else None

        self.dice_pen.goto(x + size / 2, y + 10)
        self.dice_pen.color("black")
        self.dice_pen.write("DIE", align="center", font=("Arial", 11, "bold"))

        self.dice_pen.goto(x + size / 2, y - 60)
        self.dice_pen.write("-" if value is None else str(value),
                            align="center", font=("Arial", 28, "bold"))

    # --------------------------------------------------------
    # INFO PANEL
    # --------------------------------------------------------

    def _event_to_text(self, ev: Event) -> str:
        """
        Convert an event to a readable one-line description.
        """
        t = ev.type
        d = ev.data

        if t == "roll":
            return f"roll: {d['roll']}"
        if t == "move":
            return f"move P{d['piece']} {d['from']} -> {d['to']}"
        if t == "safe_square":
            return f"safe square at {d['track_index']}"
        if t == "capture":
            return f"captured {self.game.PLAYER_NAMES[d['captured_player']]} P{d['captured_piece']}"
        if t == "piece_finished":
            return f"P{d['piece']} finished"
        if t == "extra_roll":
            return "extra roll"
        if t == "triple_six_forfeit":
            return "triple six forfeit"
        if t == "pass_no_legal_moves":
            return "no legal moves"
        if t == "agent_none_forced":
            return "agent returned None, forced move"
        if t == "agent_illegal_forced":
            return "illegal move, forced move"
        if t == "win":
            return "WIN"

        return t

    def draw_info_panel(self, autoplay: bool = False):
        """
        Draw status / controls / recent turn information.
        """
        self.info_pen.clear()

        x = 320
        y = 300
        self.info_pen.goto(x, y)
        self.info_pen.color("black")
        self.info_pen.write("LUDO STATUS", font=("Arial", 16, "bold"))

        y -= 30
        current = self.game.current_player
        winner = self.game.winner
        current_name = self.game.PLAYER_NAMES[current]

        self.info_pen.goto(x, y)
        self.info_pen.write(f"Turn: {self.game.turn_counter}", font=("Arial", 12, "normal"))

        y -= 22
        self.info_pen.goto(x, y)
        self.info_pen.write(f"Current: {current_name}", font=("Arial", 12, "normal"))

        y -= 22
        self.info_pen.goto(x, y)
        self.info_pen.write(f"Winner: {winner}", font=("Arial", 12, "normal"))

        y -= 22
        self.info_pen.goto(x, y)
        self.info_pen.write(f"Autoplay: {'ON' if autoplay else 'OFF'}", font=("Arial", 12, "normal"))

        y -= 30
        self.info_pen.goto(x, y)
        self.info_pen.write("Controls:", font=("Arial", 12, "bold"))

        y -= 20
        self.info_pen.goto(x, y)
        self.info_pen.write("SPACE = play one turn", font=("Arial", 11, "normal"))

        y -= 20
        self.info_pen.goto(x, y)
        self.info_pen.write("A = autoplay on/off", font=("Arial", 11, "normal"))

        y -= 20
        self.info_pen.goto(x, y)
        self.info_pen.write("R = redraw", font=("Arial", 11, "normal"))

        y -= 30
        self.info_pen.goto(x, y)
        self.info_pen.write("Last turn:", font=("Arial", 12, "bold"))

        if self.game.last_summary is None:
            y -= 20
            self.info_pen.goto(x, y)
            self.info_pen.write("No turns played yet.", font=("Arial", 11, "normal"))
        else:
            summary = self.game.last_summary
            pid = summary["player"]
            rolls = summary["rolls"]

            y -= 20
            self.info_pen.goto(x, y)
            self.info_pen.write(
                f"{self.game.PLAYER_NAMES[pid]} rolled {rolls}",
                font=("Arial", 11, "normal"),
            )

            for ev in summary["events"][:10]:
                y -= 18
                self.info_pen.goto(x, y)
                self.info_pen.write(self._event_to_text(ev), font=("Arial", 10, "normal"))

    # --------------------------------------------------------
    # FULL DRAW
    # --------------------------------------------------------

    def draw(self, autoplay: bool = False):
        """
        Draw the full current board state.
        """
        self.screen.tracer(0, 0)
        self.pen.clear()
        self.draw_background_regions()
        self.draw_pieces()
        self.draw_info_panel(autoplay=autoplay)
        self.draw_die()
        self.screen.tracer(1, 0)


# ============================================================
# APP / CONTROLLER
# ============================================================
#
# This class ties together:
#   - the engine
#   - the renderer
#   - keyboard controls
#   - autoplay

class LudoApp:
    def __init__(self, agents: List[PlayerAgent], seed: Optional[int] = 1):
        """
        Create a playable Ludo application window.
        """
        self.game = LudoGame(agents, seed=seed)
        self.renderer = TurtleLudoRenderer(self.game)

        # Autoplay starts on by default
        self.autoplay = True

        # Initial draw
        self.renderer.draw(autoplay=self.autoplay)

        # Keyboard bindings
        self.renderer.screen.listen()
        self.renderer.screen.onkey(self.play_one_turn, "space")
        self.renderer.screen.onkey(self.toggle_autoplay, "a")
        self.renderer.screen.onkey(self.redraw, "r")

        # Start timer loop
        self.renderer.screen.ontimer(self._autoplay_step, 50)

    def play_one_turn(self):
        """
        Play one turn manually.
        """
        if self.game.winner is None:
            self.game.step_turn()
        self.renderer.draw(autoplay=self.autoplay)

    def redraw(self):
        """
        Force redraw.
        """
        self.renderer.draw(autoplay=self.autoplay)

    def toggle_autoplay(self):
        """
        Turn autoplay on or off.
        """
        self.autoplay = not self.autoplay
        self.renderer.draw(autoplay=self.autoplay)

    def _autoplay_step(self):
        """
        Timer callback used for autoplay.
        Runs about 10x faster than the earlier 500ms version.
        """
        if self.autoplay and self.game.winner is None:
            self.game.step_turn()
            self.renderer.draw(autoplay=self.autoplay)

        # Reschedule the timer
        self.renderer.screen.ontimer(self._autoplay_step, 50)

    def run(self):
        """
        Start turtle main loop.
        """
        turtle.done()


# ============================================================
# MAIN
# ============================================================
#
# One SimpleAI instance is created for each player.
#
# To substitute student AIs, replace one or more entries below.
#
# Example:
#
#     agents = [
#         MyStudentAI(),
#         SimpleAI(),
#         SimpleAI(),
#         SimpleAI(),
#     ]

if __name__ == "__main__":
    # --------------------------------------------------------
    # STUDENT AI INTEGRATION (Red player)
    # --------------------------------------------------------
    # If StudentAI was imported successfully above, use it for
    # the Red seat. Otherwise default to SimpleAI.
    red_agent = STUDENT_AI() if STUDENT_AI is not None else SimpleAI()

    agents = [
        red_agent,     # Red player AI (student slot)
        SimpleAI(),    # Green player AI
        SimpleAI(),    # Yellow player AI
        SimpleAI(),    # Blue player AI
    ]

    # Using a fixed seed makes every run identical (same winner every time).
    # Set seed=None to randomize games so outcomes vary.
    app = LudoApp(agents, seed=None)
    app.run()
