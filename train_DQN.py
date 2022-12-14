"""
# 학습 코드

## env.step 결과
observation:
  Robot: array(5)
    distance
    v_pref
    velocity_x
    velocity_y
    radius

  human1~5: array(7)
    distance
    position_vector_x
    position_vector_y
    velocity_vector_x
    velocity_vector_y
    radius
    human_radius + robot_radius

action: array(2)
  v_pref
  angle

info:
  distance: float

"""
import collections
import random

import numpy as np

import gym_examples
import gymnasium as gym
import time
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F


learning_rate = 0.005
gamma = 0.98
buffer_limit = 50000  # size of replay buffer
batch_size = 32

device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")


class ReplayBuffer():
    def __init__(self):
        self.buffer = collections.deque(maxlen=buffer_limit)  # double-ended queue

    def put(self, transition):
        self.buffer.append(transition)

    def sample(self, n):
        mini_batch = random.sample(self.buffer, n)
        s_lst, a_lst, r_lst, s_prime_lst, done_mask_lst = [], [], [], [], []

        for transition in mini_batch:
            s, a, r, s_prime, done_mask = transition
            s_lst.append(s)
            a_lst.append([a])
            r_lst.append([r])
            s_prime_lst.append(s_prime)
            done_mask_lst.append([done_mask])

        return torch.tensor(s_lst, dtype=torch.float).to(device),\
               torch.tensor(a_lst).to(device), \
               torch.tensor(r_lst, dtype=torch.float).to(device),\
               torch.tensor(s_prime_lst, dtype=torch.float).to(device), \
               torch.tensor(done_mask_lst).to(device)

    def size(self):
        return len(self.buffer)


class Qnet(nn.Module):
    def __init__(self):
        super(Qnet, self).__init__()
        self.fc1 = nn.Linear(40, 256)
        self.fc2 = nn.Linear(256, 256)
        self.fc3 = nn.Linear(256, 2)

    def forward(self, x):
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        return x

    def sample_action(self, obs, epsilon=0):
        out = self.forward(obs)
        coin = random.random()
        if coin < epsilon:
            return random.randint(0, 1)
        else:
            # return out.argmax().item()
            return out


def train(q, q_target, memory, optimizer):
    for i in range(10):
        s, a, r, s_prime, done_mask = memory.sample(batch_size)

        q_out = q(s)
        # q_a = q_out.gather(1, a)

        # DQN
        # max_q_prime = q_target(s_prime).max(1)[0].unsqueeze(1)
        max_q_prime = q_target(s_prime)

        # Double DQN
        # argmax_Q = q(s_prime).max(1)[1].unsqueeze(1)
        # max_q_prime = q_target(s_prime).gather(1, argmax_Q)

        target = r + gamma * max_q_prime * done_mask

        # MSE Loss
        loss = F.mse_loss(q_out, target)

        # Smooth L1 Loss
        # loss = F.smooth_l1_loss(q_a, target)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()


def state_to_nparray(state):
    state_array = None
    for key, value in state.items():
        if state_array is None:
            state_array = value
        else:
            state_array = np.concatenate((state_array, value), dtype=np.float32)

    return state_array


def main():
    env = gym.make('gym_examples/GridWorld-v0', render_mode='rgb_array')
    env.action_space.seed(42)

    episode = 20000
    total_reward = 0

    done = False

    q = Qnet().to(device)
    q_target = Qnet().to(device)
    q_target.load_state_dict(q.state_dict())
    memory = ReplayBuffer()
    epsilon = 0.1

    optimizer = optim.Adam(q.parameters(), lr=learning_rate)

    for episode_num in range(1, episode + 1):
        state, info = env.reset(seed=episode_num)
        state = state_to_nparray(state)

        while not done:
            # if random.uniform(0, 1) < epsilon:
            #     action = env.action_space.sample()
            # else:
            action = q.sample_action(torch.tensor(state).to(device))

            action = action.cpu().detach().numpy()

            next_state, reward, terminated, truncated, info = env.step(action)
            next_state = state_to_nparray(next_state)
            total_reward += reward
            # print(observation)

            if terminated or truncated:
                done = True

            done_mask = 0.0 if done else 1.0
            memory.put((state, action, reward, next_state, done_mask))
            state = next_state

            if done:
                break

        if memory.size() > 2000:
            train(q, q_target, memory, optimizer)

        if episode_num % 10 == 0:
            print(f'n_episode: {episode_num}, avg_reward: {total_reward / episode_num:.4f}')

    env.close()


if __name__ == '__main__':
    main()