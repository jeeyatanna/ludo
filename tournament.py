import sys
from ludo_v5 import LudoGame, SimpleAI
from student_ai import StudentAI


def run_headless_tournament(num_games=100):
    print(f"Simulating {num_games} games (Red: StudentAI vs Others: SimpleAI)...")
    wins = {0: 0, 1: 0, 2: 0, 3: 0}

    for i in range(1, num_games + 1):
        agents = [StudentAI(), SimpleAI(), SimpleAI(), SimpleAI()]
        game = LudoGame(agents)
        current_player = 0

        while game.winner is None:
            game.run_player_turn(current_player)
            current_player = (current_player + 1) % 4

        wins[game.winner] += 1
        if i % 50 == 0:
            print(f"Game {i}/{num_games} — Red win rate: {(wins[0] / i) * 100:.1f}%")

    print("FINAL TOURNAMENT RESULTS")
    for player, wins_count in wins.items():
        print(f"Player {player}: {wins_count} wins")


if __name__ == "__main__":
    run_headless_tournament(1000)
