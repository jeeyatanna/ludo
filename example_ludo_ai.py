from __future__ import annotations

#ludo ai

import random
from typing import List, Dict, Any, Optional

from ludo_v5 import (
    PlayerAgent, LudoGame, LudoApp,
    SimpleAI, Move, PlayerId
)

#genome
#
#   0  finish_piece   
#   1  capture_enemy  
#   2  enter_board    
#   3  advance        
#   4  home_lane      
#   5  bias constant 1.0

GENOME_SIZE = 6

FEATURE_NAMES = [
    "finish_piece",
    "capture_enemy",
    "enter_board",
    "advance",
    "home_lane",
    "bias",
]


def rand_genome(scale=1.0):
    return [random.uniform(-scale, scale) for _ in range(GENOME_SIZE)]


def dot(weights, features):
    return sum(w * f for w, f in zip(weights, features))


def mutate(genome, rate=0.15, sigma=0.30):
    g = genome[:]
    for i in range(len(g)):
        if random.random() < rate:
            g[i] += random.gauss(0.0, sigma)
    return g


def crossover(a, b):
    return [a[i] if random.random() < 0.5 else b[i] for i in range(len(a))]


# move ft

def compute_features(state, player_id, move):
    """Return 6-feature vector for one candidate move."""
    cfg          = state["config"]
    positions    = state["positions"]
    start_offset = state["start_offset"]

    track_len  = cfg["track_len"]
    finish_pos = cfg["finish_pos"]
    num_players = cfg["num_players"]

    piece_id, new_pos = move
    old_pos = positions[player_id][piece_id]

    static_safe = set(cfg["star_safe_squares"])
    if cfg["start_squares_safe"]:
        static_safe.update(start_offset)

    def to_ring(pid, progress):
        if progress < 0 or progress >= track_len:
            return None
        return (start_offset[pid] + progress) % track_len

    my_new_ring = to_ring(player_id, new_pos)

    # 0 finish
    finish_f = 1.0 if new_pos == finish_pos else 0.0

    # 1 capture
    capture_f = 0.0
    if my_new_ring is not None and my_new_ring not in static_safe:
        for pid in range(num_players):
            if pid == player_id:
                continue
            for prog in positions[pid]:
                if to_ring(pid, prog) == my_new_ring:
                    capture_f = 1.0

    # 2 enter
    enter_f = 1.0 if (old_pos == -1 and new_pos == 0) else 0.0

    # 3 advance
    old_clamped = max(old_pos, 0)
    advance_f = max(0.0, (new_pos - old_clamped) / finish_pos)

    # 4 home lane
    home_f = 1.0 if new_pos >= track_len else 0.0

    # 5 bias
    bias_f = 1.0

    return [finish_f, capture_f, enter_f, advance_f, home_f, bias_f]


def score_move(genome, state, player_id, move):
    return dot(genome, compute_features(state, player_id, move)) + 0.02 * random.random()


def pick_best_move(genome, state, player_id, legal_moves):
    if not legal_moves:
        return None
    return max(legal_moves, key=lambda m: score_move(genome, state, player_id, m))


#ga player red 0

class GeneticPlayerAI(PlayerAgent):
    """Genetic Algorithm AI — evolves a population of genomes."""
    def __init__(self, genome=None):
        self.genome = genome if genome is not None else rand_genome()

    def select_move(self, state, player_id, roll, legal_moves):
        return pick_best_move(self.genome, state, player_id, legal_moves)


#es player green 1

class ESPlayerAI(PlayerAgent):
    """Evolution Strategy AI — hill-climbs a single genome."""
    def __init__(self, genome=None):
        self.genome = genome if genome is not None else rand_genome()

    def select_move(self, state, player_id, roll, legal_moves):
        return pick_best_move(self.genome, state, player_id, legal_moves)

#training game

def play_training_game(agents, seed=None, max_turns=800):
    game = LudoGame(agents, seed=seed)
    for _ in range(max_turns):
        game.step_turn()
        if game.winner is not None:
            return game.winner
    totals = [sum(p for p in game.pos[pid] if p >= 0) for pid in range(4)]
    return totals.index(max(totals))


# self play — GA and ES train against each other

def train_selfplay(pop_size=20, rounds=30, games_per_round=4):
    print("Training GA (Red) vs ES (Green) via self-play...")

    ga_pop    = [[rand_genome(), 0.0] for _ in range(pop_size)]
    es_genome = rand_genome()
    es_fitness = 0.0

    for rnd in range(1, rounds + 1):

        # evaluate every GA genome against current ES
        for ind in ga_pop:
            wins = sum(
                1 for _ in range(games_per_round)
                if play_training_game([GeneticPlayerAI(ind[0]),
                                       ESPlayerAI(es_genome),
                                       SimpleAI(), SimpleAI()]) == 0
            )
            ind[1] = wins / games_per_round

        ga_pop.sort(key=lambda i: i[1], reverse=True)
        top_ga = [ind[0] for ind in ga_pop[:max(3, pop_size // 4)]]

        # ES hill-climb against best GA genomes
        def eval_es(g):
            wins = sum(
                1 for _ in range(games_per_round)
                if play_training_game([GeneticPlayerAI(random.choice(top_ga)),
                                       ESPlayerAI(g),
                                       SimpleAI(), SimpleAI()]) == 1
            )
            return wins / games_per_round

        best_g, best_f = es_genome, eval_es(es_genome)
        for _ in range(4):
            cand = mutate(es_genome)
            f    = eval_es(cand)
            if f > best_f:
                best_f, best_g = f, cand
        if best_g is not es_genome:
            es_genome  = best_g
            es_fitness = best_f

        # replace worst GA with children of best
        elite_n   = max(2, int(pop_size * 0.25))
        replace_n = max(1, int(pop_size * 0.30))
        elites    = ga_pop[:elite_n]
        for r in range(replace_n):
            p1, p2 = random.sample(elites, 2)
            child  = mutate(crossover(p1[0], p2[0]))
            ga_pop[-(r + 1)] = [child, 0.0]

        if rnd % 10 == 0 or rnd == rounds:
            avg = sum(i[1] for i in ga_pop) / len(ga_pop)
            print(f"  round {rnd:3d}/{rounds}  GA best={ga_pop[0][1]:.2f} avg={avg:.2f}  ES fit={es_fitness:.2f}")

    print(f"\n  Done! GA={ga_pop[0][1]:.2f}  ES={es_fitness:.2f}\n")
    return ga_pop[0][0], es_genome


# main

if __name__ == "__main__":

    ga_genome, es_genome = train_selfplay(pop_size=20, rounds=30, games_per_round=4)

    print("Learned GA weights:")
    for name, w in zip(FEATURE_NAMES, ga_genome):
        print(f"  {name:<16} {w:+.3f}")
    print()

    agents = [
        GeneticPlayerAI(ga_genome),
        ESPlayerAI(es_genome),
        SimpleAI(),
        SimpleAI(),
    ]

    print("Opening game window...")
    print("SPACE = one turn  |  A = autoplay on/off  |  R = redraw\n")
    app = LudoApp(agents, seed=None)
    app.run()
