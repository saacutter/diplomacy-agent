import random
import numpy as np
from tqdm import tqdm
from game import run_one_game
from collections import defaultdict
from agent_baselines import StaticAgent, RandomAgent, GreedyAgent, AttitudeAgent
from agent import CustomAgent

ALL_POWERS = ['AUSTRIA', 'ENGLAND', 'FRANCE', 'GERMANY', 'ITALY', 'RUSSIA', 'TURKEY']

def scoring(centres):
    scores = {k: min(v, 18) for k, v in centres.items()}
    wins = {}
    for k, v in scores.items():
        if v == 18:
            wins[k] = 'WIN'
        elif v == 0:
            wins[k] = 'DEFEAT'
        else:
            wins[k] = 'SURVIVE'
    return scores, wins

def experiment(player_agent, opponent_agent_pool, repeat_nums=10):
    all_scores = defaultdict(list)
    all_wins = defaultdict(list)
    total_games = repeat_nums * len(ALL_POWERS)

    with tqdm(total=total_games) as pbar:
        for r in range(repeat_nums):
            for i in ALL_POWERS:
                agents_dict = {}
                for p in ALL_POWERS:
                    if p == i:
                        agents_dict[p] = player_agent()
                    else:
                        opponent_agent = random.choice(opponent_agent_pool)
                        agents_dict[p] = opponent_agent()
                results, _ = run_one_game(agents_dict)
                scores, wins = scoring(results)
                all_scores[i].append(scores[i])
                all_scores['ALL'].append(scores[i])
                all_wins[i].append(wins[i])
                all_wins['ALL'].append(wins[i])
                pbar.update(1)

    scores_avg = {k: np.mean(v) for k, v in all_scores.items()}
    scores_std = {k: np.std(v) for k, v in all_scores.items()}

    win_rates, survive_rates, defeat_rates = {}, {}, {}
    for k, v in all_wins.items():
        win_rates[k] = sum([i == 'WIN' for i in v]) / len(v)
        survive_rates[k] = sum([i == 'SURVIVE' for i in v]) / len(v)
        defeat_rates[k] = sum([i == 'DEFEAT' for i in v]) / len(v)
        win_rates[k] = round(win_rates[k] * 100, 2)
        survive_rates[k] = round(survive_rates[k] * 100, 2)
        defeat_rates[k] = round(defeat_rates[k] * 100, 2)

    print('=========================================================================')
    print('----- The Per-Power and the Overall Performance of the Player Agent -----')
    for p in ALL_POWERS + ['ALL']:
        print(f'{p}: SCs - {round(scores_avg[p], 2)}±{round(scores_std[p], 2)}, Wins - {win_rates[p]}%, Survives - {survive_rates[p]}%, Defeats - {defeat_rates[p]}%')
    print('-------------------------------------------------------------------------')

    return all_wins, scores_avg, scores_std

def print_totals(totals):
    print('----- The Total Per-Power and the Overall Performance of the Player Agent -----')
    for p in ALL_POWERS + ['ALL']:
        print(f'{p}: SCs - {round(totals["avg"][p], 2)}±{round(totals["std"][p], 2)}, Wins - {round(totals["wins"][p]*100, 2)}%, Survives - {round(totals["survival"][p]*100, 2)}%, Defeats - {round(totals["defeats"][p]*100, 2)}%')
    print('=========================================================================')


if __name__ == "__main__":
    totals = {"avg": {p: 0 for p in ALL_POWERS + ["ALL"]}, 
              "std": {p: 0 for p in ALL_POWERS + ["ALL"]}, 
              "wins": {p: 0 for p in ALL_POWERS + ["ALL"]}, 
              "survival": {p: 0 for p in ALL_POWERS + ["ALL"]}, 
              "defeats": {p: 0 for p in ALL_POWERS + ["ALL"]}
    }

    print('Evaluating Scenario 1 ...')
    wins, avg, std = experiment(player_agent=StudentAgent, opponent_agent_pool=[StaticAgent], repeat_nums=10)
    for k, v in wins.items():
        totals["avg"][k] = avg[k]
        totals["std"][k] = std[k]
        totals["wins"][k] = sum([i == 'WIN' for i in v]) / len(v)
        totals["survival"][k] = sum([i == 'SURVIVE' for i in v]) / len(v)
        totals["defeats"][k] = sum([i == 'DEFEAT' for i in v]) / len(v)

    print('Evaluating Scenario 2 ...')
    wins, avg, std = experiment(player_agent=StudentAgent, opponent_agent_pool=[RandomAgent, AttitudeAgent, AttitudeAgent, GreedyAgent, GreedyAgent], repeat_nums=10)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("Evaluating 10 games where the opponents are all RandomAgents")
    wins, avg, std = experiment(StudentAgent, [RandomAgent], 10)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\nEvaluating 10 games where the oponnents are all AttitudeAgents")
    wins, avg, std = experiment(StudentAgent, [AttitudeAgent], 10)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\nEvaluating 10 games where the opponents are all GreedyAgents")
    wins, avg, std = experiment(StudentAgent, [GreedyAgent], 10)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\nEvaluating 10 games where the opponents are all StudentAgents")
    wins, avg, std = experiment(StudentAgent, [StudentAgent], 10)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\nEvaluating 20 games where the opponents are randomly selected between RandomAgents and AttitudeAgents")
    wins, avg, std = experiment(StudentAgent, [AttitudeAgent, RandomAgent], 20)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\n Evaluating 100 iterations of scenario 1")
    wins, avg, std = experiment(player_agent=StudentAgent, opponent_agent_pool=[StaticAgent], repeat_nums=100)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)

    print("\n Evaluating 100 iterations of scenario 2")
    wins, avg, std = experiment(player_agent=StudentAgent, opponent_agent_pool=[RandomAgent, AttitudeAgent, AttitudeAgent, GreedyAgent, GreedyAgent], repeat_nums=100)
    for k, v in wins.items():
        totals["avg"][k] = np.mean([totals["avg"][k], avg[k]])
        totals["std"][k] = np.mean([totals["std"][k], std[k]])
        totals["wins"][k] = np.mean([totals["wins"][k], sum([i == 'WIN' for i in v]) / len(v)])
        totals["survival"][k] = np.mean([totals["survival"][k], sum([i == 'SURVIVE' for i in v]) / len(v)])
        totals["defeats"][k] = np.mean([totals["defeats"][k], sum([i == 'DEFEAT' for i in v]) / len(v)])
    print_totals(totals)