from __future__ import annotations

# DO NOT RUN THIS CODE. RUN "LUDO_V5".
# StudentAI — Feature-weighted Ludo AI  +  Self-play Trainer
# NORMAL USE (playing the game):
#   Just import StudentAI as usual — no external files needed.
#   The weights in DEFAULT_WEIGHTS below are used directly.
#
# TRAINING (improving the weights):
#   Run this file directly:
#       python student_ai.py
#
#   Optional flags:
#       --pop   INT    Population size          (default 24)
#       --gens  INT    Generations to run       (default 50)
#       --games INT    Games per evaluation     (default 16)
#       --sigma FLOAT  Initial mutation size    (default 30)
#
#   The trainer runs a self-play evolution strategy:
#     - A pool of StudentAI genomes compete against EACH OTHER
#       AND against SimpleAI opponents simultaneously
#     - Best genomes are selected and bred each generation
#     - When finished, this file is rewritten in-place so that
#       DEFAULT_WEIGHTS contains the new values permanently
#       (no external files needed)
#
# Features (12):
#   0  finish_piece        - lands exactly on finish_pos
#   1  enter_home_lane     - enters the private home lane
#   2  home_lane_progress  - depth inside the home lane (normalised)
#   3  create_blockade     - forms an impassable 2-stack on outer track
#   4  capture_enemy       - captures at least one enemy piece
#   5  capture_value       - how advanced the captured piece was (normalised)
#   6  land_on_safe        - lands on a static star / start safe square
#   7  advance             - normalised forward progress (quadratic proximity)
#   8  enter_board         - exits base onto square 0
#   9  enter_urgency       - extra incentive when board is sparse
#  10  danger_penalty      - lone piece exposed to nearby threats (NEGATIVE)
#  11  spread_lag          - reward advancing pieces lagging behind the average
# ============================================================

import os
import re
import random
from typing import Any, Dict, List, Optional, Tuple

Move = Tuple[int, int]

FEATURE_NAMES = [
    "finish_piece", "enter_home_lane", "home_lane_progress",
    "create_blockade", "capture_enemy", "capture_value",
    "land_on_safe", "advance", "enter_board", "enter_urgency",
    "danger_penalty", "spread_lag",
]


# DEFAULT_WEIGHTS — patched in-place by the trainer after each run

# Trained weights from last stable run (work from these when retraining)
DEFAULT_WEIGHTS = [  # trained  win_rate=0.6667
     1074.6086,   #  0  finish_piece
      179.9895,   #  1  enter_home_lane
       57.7412,   #  2  home_lane_progress
      -27.6542,   #  3  create_blockade
      170.3739,   #  4  capture_enemy
      -20.6545,   #  5  capture_value
      176.5093,   #  6  land_on_safe
      193.7736,   #  7  advance
      163.0541,   #  8  enter_board
      -73.9021,   #  9  enter_urgency
       -6.1466,   # 10  danger_penalty
     -256.7252   # 11  spread_lag
]

GENOME_SIZE = len(DEFAULT_WEIGHTS)



# Feature extraction  (shared by AI and trainer)

def compute_features(
    state: Dict[str, Any],
    player_id: int,
    move: Move,
) -> List[float]:
    """Return a GENOME_SIZE-element feature vector for one candidate move."""

    cfg       = state["config"]
    positions = state["positions"]
    offsets   = state["start_offset"]

    track_len  = cfg["track_len"]
    finish_pos = cfg["finish_pos"]
    n_players  = cfg["num_players"]

    piece_id, new_pos = move
    old_pos = positions[player_id][piece_id]

    static_safe = set(cfg["star_safe_squares"])
    if cfg["start_squares_safe"]:
        static_safe.update(offsets)

    def to_ti(pid, prog):
        if 0 <= prog < track_len:
            return (offsets[pid] + prog) % track_len
        return None

    occ = {}
    for pid in range(n_players):
        for pc, prog in enumerate(positions[pid]):
            ti = to_ti(pid, prog)
            if ti is not None:
                occ.setdefault(ti, []).append((pid, pc))

    def is_safe_ti(ti):
        if ti in static_safe:
            return True
        counts = {}
        for pid, _ in occ.get(ti, []):
            counts[pid] = counts.get(pid, 0) + 1
        return any(v >= 2 for v in counts.values())

    def my_count_at(ti):
        return sum(1 for pid, _ in occ.get(ti, []) if pid == player_id)

    def threat_count(ti):
        n = 0
        for op in range(n_players):
            if op == player_id:
                continue
            for prog in positions[op]:
                op_ti = to_ti(op, prog)
                if op_ti is None:
                    continue
                if 1 <= (ti - op_ti) % track_len <= 6:
                    n += 1
        return n

    my_positions    = positions[player_id]
    pieces_on_board = sum(1 for p in my_positions if 0 <= p < finish_pos)
    avg_progress    = (
        sum(p for p in my_positions if p >= 0) / pieces_on_board
        if pieces_on_board > 0 else 0.0
    )

    landed_ti = to_ti(player_id, new_pos)
    f = [0.0] * GENOME_SIZE

    # 0 finish_piece
    if new_pos == finish_pos:
        f[0] = 1.0

    # 1 & 2 home lane
    if track_len <= new_pos < finish_pos:
        f[1] = 1.0
        f[2] = (new_pos - track_len) / max(1, finish_pos - track_len)

    if landed_ti is not None:
        # 3 create_blockade
        if my_count_at(landed_ti) == 1:
            f[3] = 1.0 + 0.5 * (new_pos / finish_pos)

        # 4 & 5 capture
        if not is_safe_ti(landed_ti):
            enemies_there = [
                (ep, ec) for ep, ec in occ.get(landed_ti, [])
                if ep != player_id
            ]
            if enemies_there:
                ecounts = {}
                for ep, _ in enemies_there:
                    ecounts[ep] = ecounts.get(ep, 0) + 1
                if not any(v >= 2 for v in ecounts.values()):
                    f[4] = 1.0
                    f[5] = sum(
                        positions[ep][ec] / finish_pos
                        for ep, ec in enemies_there
                    ) / len(enemies_there)

        # 6 safe square
        if landed_ti in static_safe:
            f[6] = 1.0

        # 10 danger penalty
        allies_after = my_count_at(landed_ti) + 1
        if not is_safe_ti(landed_ti) and allies_after < 2:
            threats = threat_count(landed_ti)
            if threats > 0:
                piece_value = 1.0 + (new_pos / finish_pos) * 2.0
                f[10] = threats * piece_value

    # 7 advance (quadratic proximity boost)
    old_clamped = max(old_pos, 0)
    if new_pos > old_clamped:
        proximity = (new_pos / finish_pos) ** 2
        f[7] = ((new_pos - old_clamped) / finish_pos) * (1.0 + proximity)

    # 8 & 9 enter board
    if old_pos == -1 and new_pos == 0:
        f[8] = 1.0
        f[9] = max(0.0, 1.0 - pieces_on_board / 4.0)

    # 11 spread lag
    if old_pos >= 0:
        lag = max(0.0, avg_progress - old_pos) / max(1.0, finish_pos)
        f[11] = lag

    return f


def pick_best_move(weights, state, player_id, legal_moves):
    if not legal_moves:
        return None
    return max(
        legal_moves,
        key=lambda m: sum(w * fv for w, fv in zip(weights, compute_features(state, player_id, m)))
    )


# StudentAI class

class StudentAI:
    """Feature-weighted heuristic Ludo AI."""

    # Rollout tuning
    SIM_PLAYOUTS = 24         # default rollouts per move
    SIM_MAX_TURNS = 120       # cap playout length
    SIM_SCORE_BOOST = 2000.0  # scales win-prob into heuristic space
    GLOBAL_RISK_SCALE = 120.0 # extra penalty for exposing any piece
    STACK_BONUS = 120.0       # reward creating a safe stack

    def __init__(self, weights=None, enable_rollouts: Optional[bool] = None):
        self.weights = weights if weights is not None else DEFAULT_WEIGHTS[:]
        # Default: rollouts ON for stronger play (set STUDENT_AI_ROLLOUTS=0 to disable)
        env_rollouts = os.getenv("STUDENT_AI_ROLLOUTS")
        if enable_rollouts is None:
            self.enable_rollouts = (env_rollouts != "0")
        else:
            self.enable_rollouts = enable_rollouts

        # Allow runtime tuning without editing code
        self.sim_playouts = self._safe_int(os.getenv("STUDENT_AI_PLAYOUTS"), self.SIM_PLAYOUTS)
        self.sim_max_turns = self._safe_int(os.getenv("STUDENT_AI_MAX_TURNS"), self.SIM_MAX_TURNS)
        # Default: pick by rollout win-prob only (less bias from weights)
        self.rollouts_only = os.getenv("STUDENT_AI_ROLLOUTS_ONLY", "1") == "1"

    @staticmethod
    def _safe_int(val: Optional[str], default: int) -> int:
        try:
            return int(val) if val is not None else default
        except ValueError:
            return default

    def on_game_start(self, state):
        pass

    def on_turn_start(self, state, player_id):
        pass

    def on_turn_end(self, state, player_id, events):
        pass

    def select_move(self, state, player_id, roll, legal_moves):
        if not legal_moves:
            return None
        if len(legal_moves) == 1:
            return legal_moves[0]
        # Fast path: weighted heuristic (default) to stay quick and stable
        if not self.enable_rollouts:
            best_move = None
            best_score = float("-inf")
            for mv in legal_moves:
                score = self._score_move(state, player_id, mv)
                if score > best_score:
                    best_score = score
                    best_move = mv
            return best_move

        # Heuristic + Monte Carlo rollouts to favor true win rate
        best_move = None
        best_score = float("-inf")
        # Shared seeds to reduce rollout noise between candidate moves
        seeds = [random.randint(0, 1_000_000) for _ in range(self.sim_playouts)]
        for mv in legal_moves:
            base = sum(
                w * fv
                for w, fv in zip(self.weights, compute_features(state, player_id, mv))
            )
            win_prob = self._simulate_win_prob(state, player_id, roll, mv, seeds)
            if self.rollouts_only:
                score = win_prob
            else:
                score = base + win_prob * self.SIM_SCORE_BOOST
            if score > best_score:
                best_score = score
                best_move = mv
        return best_move

    # Deterministic scoring (no rollouts)

    def _score_move(self, state, player_id, move):
        base = sum(
            w * fv
            for w, fv in zip(self.weights, compute_features(state, player_id, move))
        )

        cfg = state["config"]
        offsets = state["start_offset"]
        positions = [row[:] for row in state["positions"]]

        piece_id, new_pos = move
        positions[player_id][piece_id] = new_pos

        # Apply capture in the local copy to get a better risk estimate
        landed_ti = self._to_ti(cfg, offsets, player_id, new_pos)
        if landed_ti is not None:
            if not self._is_safe_ti(cfg, offsets, positions, landed_ti):
                # If landing on a non-safe square, capture any single enemies there
                for op in range(cfg["num_players"]):
                    if op == player_id:
                        continue
                    for pc, prog in enumerate(positions[op]):
                        if self._to_ti(cfg, offsets, op, prog) == landed_ti:
                            positions[op][pc] = -1

        risk = self._global_risk(cfg, offsets, positions, player_id)
        stack_bonus = 0.0
        if landed_ti is not None:
            if self._count_at_ti(cfg, offsets, positions, player_id, landed_ti) >= 2:
                stack_bonus = 1.0

        return base - (risk * self.GLOBAL_RISK_SCALE) + (stack_bonus * self.STACK_BONUS)

    def _to_ti(self, cfg, offsets, pid, prog):
        if prog < 0 or prog >= cfg["track_len"]:
            return None
        return (offsets[pid] + prog) % cfg["track_len"]

    def _count_at_ti(self, cfg, offsets, positions, pid, ti):
        return sum(
            1
            for pc, prog in enumerate(positions[pid])
            if self._to_ti(cfg, offsets, pid, prog) == ti
        )

    def _is_safe_ti(self, cfg, offsets, positions, ti):
        static_safe = set(cfg["star_safe_squares"])
        if cfg["start_squares_safe"]:
            static_safe.update(offsets)
        if ti in static_safe:
            return True
        # Any player stack creates a safe square
        counts = {}
        for pid in range(cfg["num_players"]):
            for prog in positions[pid]:
                if self._to_ti(cfg, offsets, pid, prog) == ti:
                    counts[pid] = counts.get(pid, 0) + 1
        return any(v >= 2 for v in counts.values())

    def _global_risk(self, cfg, offsets, positions, player_id):
        risk = 0.0
        for prog in positions[player_id]:
            ti = self._to_ti(cfg, offsets, player_id, prog)
            if ti is None:
                continue
            if self._is_safe_ti(cfg, offsets, positions, ti):
                continue
            # Count opponents within 6 behind
            threats = 0
            for op in range(cfg["num_players"]):
                if op == player_id:
                    continue
                for opp_prog in positions[op]:
                    op_ti = self._to_ti(cfg, offsets, op, opp_prog)
                    if op_ti is None:
                        continue
                    if 1 <= (ti - op_ti) % cfg["track_len"] <= 6:
                        threats += 1
            if threats > 0:
                piece_value = 1.0 + (prog / cfg["finish_pos"]) * 2.0
                risk += threats * piece_value
        return risk

    # Greedy safety-aware chooser (fast default)
   
    def _greedy_safe_choice(self, state, player_id, legal_moves):
        cfg = state["config"]
        positions = state["positions"]
        offsets = state["start_offset"]

        def to_ti(pid, prog):
            if prog < 0 or prog >= cfg["track_len"]:
                return None
            return (offsets[pid] + prog) % cfg["track_len"]

        # Occupancy map
        occ = {}
        for pid in range(cfg["num_players"]):
            for pc, prog in enumerate(positions[pid]):
                ti = to_ti(pid, prog)
                if ti is not None:
                    occ.setdefault(ti, []).append((pid, pc))

        static_safe = set(cfg["star_safe_squares"])
        if cfg["start_squares_safe"]:
            static_safe.update(offsets)

        def is_stack_safe(ti):
            counts = {}
            for pid, _ in occ.get(ti, []):
                counts[pid] = counts.get(pid, 0) + 1
            return any(v >= 2 for v in counts.values())

        def threat_count(ti):
            n = 0
            for op in range(cfg["num_players"]):
                if op == player_id:
                    continue
                for prog in positions[op]:
                    op_ti = to_ti(op, prog)
                    if op_ti is None:
                        continue
                    if 1 <= (ti - op_ti) % cfg["track_len"] <= 6:
                        n += 1
            return n

        scored = []
        for mv in legal_moves:
            piece_id, new_pos = mv
            old_pos = positions[player_id][piece_id]

            finish = 1 if new_pos == cfg["finish_pos"] else 0
            enter = 1 if old_pos == -1 and new_pos == 0 else 0

            landed_ti = to_ti(player_id, new_pos)
            capture = 0
            safe_land = 0
            risk = 0

            if landed_ti is not None:
                # Capture count (only if landing not on safe/stack)
                if landed_ti not in static_safe and not is_stack_safe(landed_ti):
                    for pid, _pc in occ.get(landed_ti, []):
                        if pid != player_id:
                            capture += 1

                # Safe landing (star/start/stack)
                if landed_ti in static_safe or is_stack_safe(landed_ti):
                    safe_land = 1

                # Risk: exposed to any opponent within 6 behind
                threats = threat_count(landed_ti)
                if threats > 0 and not safe_land:
                    risk = threats

            progress = new_pos

            score = (
                finish * 1200
                + capture * 400
                + safe_land * 120
                - risk * 120
                + enter * 150
                + progress * 3
            )
            scored.append((score, capture, finish, safe_land, -risk, progress, mv))

        scored.sort(reverse=True)
        return scored[0][-1]

  
    # Lightweight rollouts (one-step apply + future playouts)

    def _simulate_win_prob(self, state, player_id, roll, move, seeds=None):
        """
        Estimate win probability for a candidate move using shallow playouts.
        Uses rollouts with StudentAI disabled (pure heuristic) to avoid recursion.
        """
        try:
            from ludo_v5 import LudoGame, SimpleAI, GameConfig  # lazy import to avoid circulars
        except Exception:
            return 0.0

        # Build agents: our StudentAI without rollouts + SimpleAI opponents
        num_players = state["config"]["num_players"]
        agents_proto = [StudentAI(self.weights, enable_rollouts=False)] + [
            SimpleAI() for _ in range(num_players - 1)
        ]

        wins = 0
        seed_list = seeds if seeds is not None else [random.randint(0, 1_000_000) for _ in range(self.sim_playouts)]
        for seed in seed_list:
            agents = []
            for proto in agents_proto:
                if isinstance(proto, StudentAI):
                    agents.append(StudentAI(self.weights, enable_rollouts=False))
                else:
                    agents.append(proto.__class__())
            cfg = GameConfig(**state["config"])
            g = LudoGame(agents, config=cfg, seed=seed)

            # Restore state snapshot
            g.pos = [row[:] for row in state["positions"]]
            g.current_player = state["current_player"]
            g.turn_counter = state["turn_counter"]
            g.winner = state["winner"]

            # Apply the candidate move
            g.apply_move(player_id, move)
            if g.is_finished(player_id):
                wins += 1
                continue

            # Decide who moves next (approximate extra-roll behavior)
            g.current_player = player_id if roll == g.cfg.extra_roll_on else (player_id + 1) % g.cfg.num_players

            # Play forward
            for _ in range(self.sim_max_turns):
                g.step_turn()
                if g.winner is not None:
                    break
            if g.winner == player_id:
                wins += 1

        return wins / max(1, len(seed_list))



# Self-play Trainer  (runs only when: python student_ai.py)

def _play_game(agents, seed=None, max_turns=600):
    """Headless game -> winner id, or most-advanced player on timeout."""
    from ludo_v5 import LudoGame
    game = LudoGame(agents, seed=seed)
    for _ in range(max_turns):
        game.step_turn()
        if game.winner is not None:
            return game.winner
    totals = [sum(p for p in game.pos[pid] if p >= 0) for pid in range(4)]
    return totals.index(max(totals))


def _evaluate(weights, pool, games, seed_offset=0):
    """
    Mixed evaluation: half games vs SimpleAI, half vs pool (self-play).
    Returns overall win-rate.
    """
    from ludo_v5 import SimpleAI as Sim

    wins = 0
    half = max(1, games // 2)

    # vs SimpleAI
    for i in range(half):
        agents = [StudentAI(weights, enable_rollouts=False), Sim(), Sim(), Sim()]
        if _play_game(agents, seed=seed_offset + i) == 0:
            wins += 1

    # vs pool members (self-play)
    for i in range(games - half):
        opponents = random.choices(pool, k=3)
        agents = [
            StudentAI(weights, enable_rollouts=False),
            StudentAI(opponents[0], enable_rollouts=False),
            StudentAI(opponents[1], enable_rollouts=False),
            StudentAI(opponents[2], enable_rollouts=False),
        ]
        if _play_game(agents, seed=seed_offset + half + i) == 0:
            wins += 1

    return wins / games


def _mutate(genome, sigma):
    return [g + random.gauss(0.0, sigma) for g in genome]


def _crossover(a, b):
    # Weighted blend crossover
    return [a[i] * t + b[i] * (1.0 - t) for i, t in enumerate(random.random() for _ in a)]


def _patch_file(weights, win_rate):
    """
    Rewrite DEFAULT_WEIGHTS inside this source file with the trained values.
    Uses a regex to find and replace the entire list block.
    """
    this_file = os.path.abspath(__file__)
    with open(this_file, "r") as fh:
        source = fh.read()

    # Build replacement block
    lines = ["DEFAULT_WEIGHTS = [  # trained  win_rate={:.4f}\n".format(win_rate)]
    for i, (w, name) in enumerate(zip(weights, FEATURE_NAMES)):
        comma = "," if i < len(weights) - 1 else ""
        lines.append("    {:>10.4f}{}   # {:>2}  {}\n".format(w, comma, i, name))
    lines.append("]\n")
    new_block = "".join(lines)

    pattern = re.compile(
        r"^DEFAULT_WEIGHTS\s*=\s*\[.*?^\]\s*$",
        re.MULTILINE | re.DOTALL,
    )
    new_source, count = pattern.subn(new_block, source, count=1)

    if count == 0:
        print("  WARNING: regex did not match DEFAULT_WEIGHTS block.")
        print("  Paste these weights manually:\n", weights)
        return

    with open(this_file, "w") as fh:
        fh.write(new_source)
    print("  Weights hardcoded into {}".format(this_file))


def train(pop_size=24, generations=50, games_per_eval=16, sigma_init=30.0, sigma_decay=0.93, elite_frac=0.25):
    """
    (mu + lambda) Evolution Strategy with self-play.

    Evaluation mixes:
      - Games vs SimpleAI  ->  tests general competence
      - Games vs pool      ->  tests adaptability against smart play

    After training, DEFAULT_WEIGHTS in this file is overwritten.
    """
    print("=" * 62)
    print("  StudentAI  —  Self-Play Evolutionary Trainer")
    print("  pop={}  gens={}  games/eval={}".format(pop_size, generations, games_per_eval))
    print("  Opponents: 50% SimpleAI  +  50% pool self-play")
    print("=" * 62)

    # Seed population from current defaults
    population = [DEFAULT_WEIGHTS[:]]
    for _ in range(pop_size - 1):
        population.append(_mutate(DEFAULT_WEIGHTS, sigma_init))

    best_weights = DEFAULT_WEIGHTS[:]
    best_fitness = _evaluate(best_weights, population, games_per_eval)
    sigma = sigma_init

    print("\n  Baseline win-rate: {:.3f}\n".format(best_fitness))

    for gen in range(1, generations + 1):
        scored = []
        for ind in population:
            fit = _evaluate(ind, population, games_per_eval, seed_offset=gen * 1000)
            scored.append((fit, ind))
        scored.sort(key=lambda x: x[0], reverse=True)

        top_fit, top_ind = scored[0]
        avg_fit = sum(s[0] for s in scored) / len(scored)

        if top_fit > best_fitness:
            best_fitness = top_fit
            best_weights = top_ind[:]

        print("  gen {:3d}/{}  best={:.3f}  avg={:.3f}  all-time={:.3f}  sigma={:.2f}".format(
            gen, generations, top_fit, avg_fit, best_fitness, sigma))

        # Select elites
        n_elite = max(2, int(pop_size * elite_frac))
        elites = [ind for _, ind in scored[:n_elite]]

        # Breed next generation — elites survive + offspring fill rest
        next_gen = elites[:]
        while len(next_gen) < pop_size:
            p1, p2 = random.sample(elites, 2)
            next_gen.append(_mutate(_crossover(p1, p2), sigma))

        population = next_gen
        sigma *= sigma_decay

    # ---- Final report ----
    print("\n" + "=" * 62)
    print("  Done!  Best win-rate: {:.3f}  ({:.1f}%)".format(best_fitness, best_fitness * 100))
    print("=" * 62)
    print("\n  {:<22} {:>10}  {:>10}  {}".format("Feature", "Before", "After", "Change"))
    print("  " + "-" * 54)
    for name, w_old, w_new in zip(FEATURE_NAMES, DEFAULT_WEIGHTS, best_weights):
        diff = w_new - w_old
        tag = ("(+{:.1f})".format(diff) if diff > 0.5 else
               "(-{:.1f})".format(abs(diff)) if diff < -0.5 else "(~)")
        print("  {:<22} {:>+10.3f}  {:>+10.3f}  {}".format(name, w_old, w_new, tag))

    print()
    _patch_file(best_weights, best_fitness)
    print("\n  Run ludo_v5.py to play with your trained AI.\n")
    return best_weights, best_fitness


# Entry point

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(
        description="Train StudentAI weights via self-play evolution, then hardcode them into this file."
    )
    p.add_argument("--pop",   type=int,   default=24,   help="Population size        (default: 24)")
    p.add_argument("--gens",  type=int,   default=50,   help="Generations            (default: 50)")
    p.add_argument("--games", type=int,   default=16,   help="Games per evaluation   (default: 16)")
    p.add_argument("--sigma", type=float, default=30.0, help="Initial mutation size  (default: 30)")
    args = p.parse_args()

    train(
        pop_size=args.pop,
        generations=args.gens,
        games_per_eval=args.games,
        sigma_init=args.sigma,
    )
