import random
import numpy as np
from collections import deque
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense, Input
from tensorflow.keras.optimizers import Adam

tf.get_logger().setLevel("ERROR")


class RLAgent:
    """
    Deep Q-Network agent with Double DQN target calculation.

    Standard DQN picks the best next action AND evaluates it with the same
    (target) network, leading to overestimation.  Double DQN separates the
    two steps:
        action selection  — online network   argmax Q_online(s', .)
        action evaluation — target network   Q_target(s', a*)
    This reduces the upward bias without adding extra networks.
    """

    def __init__(
        self,
        state_size,
        action_size,
        lr=0.001,
        gamma=0.99,
        epsilon=1.0,
        epsilon_min=0.01,
        epsilon_decay=0.9995,
        memory_size=50000,
        batch_size=64,
    ):
        self.state_size    = state_size
        self.action_size   = action_size
        self.lr            = lr
        self.gamma         = gamma
        self.epsilon       = epsilon
        self.epsilon_min   = epsilon_min
        self.epsilon_decay = epsilon_decay
        self.batch_size    = batch_size
        self.memory        = deque(maxlen=memory_size)

        # Online network — trained every replay step
        self.model        = self._build_model()
        # Target network — weights copied from online periodically
        self.target_model = self._build_model()
        self.update_target_network()

    # ── Network architecture ──────────────────────────────────────────────────

    def _build_model(self):
        model = Sequential([
            Input(shape=(self.state_size,)),
            Dense(512, activation="relu"),
            Dense(512, activation="relu"),
            Dense(256, activation="relu"),
            Dense(self.action_size, activation="linear"),
        ])
        # Huber loss is more robust than MSE to noisy reward signals
        model.compile(
            optimizer=Adam(learning_rate=self.lr, clipnorm=1.0),
            loss=tf.keras.losses.Huber(),
        )
        return model

    # ── Action selection ──────────────────────────────────────────────────────

    def select_action(self, state, forbidden=None):
        forbidden = forbidden or set()
        available = [i for i in range(self.action_size) if i not in forbidden]
        if not available:
            available = list(range(self.action_size))

        if random.random() < self.epsilon:
            return random.choice(available)

        q_values = self.model(state.reshape(1, -1), training=False).numpy()[0]
        for i in forbidden:
            q_values[i] = -np.inf
        return int(np.argmax(q_values))

    # ── Memory ────────────────────────────────────────────────────────────────

    def remember(self, state, action, reward, next_state, done):
        self.memory.append((state, action, reward, next_state, done))

    # ── Double DQN replay ─────────────────────────────────────────────────────

    def replay(self):
        if len(self.memory) < self.batch_size:
            return

        batch       = random.sample(self.memory, self.batch_size)
        states      = np.array([e[0] for e in batch], dtype=np.float32)
        actions     = np.array([e[1] for e in batch])
        rewards     = np.array([e[2] for e in batch], dtype=np.float32)
        next_states = np.array([e[3] for e in batch], dtype=np.float32)
        dones       = np.array([e[4] for e in batch], dtype=np.float32)

        # Single forward pass through online net for both states and next_states
        bs = len(batch)
        combined      = self.model(np.vstack([states, next_states]), training=False).numpy()
        cur_q         = combined[:bs].copy()
        next_q_online = combined[bs:]

        # Double DQN target:
        #   a* = argmax  Q_online(s', .)      — online net SELECTS the action
        #   y  = r + γ * Q_target(s', a*)     — target net EVALUATES it
        next_q_target     = self.target_model(next_states, training=False).numpy()
        best_next_actions = np.argmax(next_q_online, axis=1)

        # Vectorised target update — no Python loop
        idx         = np.arange(bs)
        best_next_q = next_q_target[idx, best_next_actions]
        targets     = np.where(dones, rewards, rewards + self.gamma * best_next_q)
        cur_q[idx, actions] = targets

        self.model.train_on_batch(states, cur_q)

    # ── Target network ────────────────────────────────────────────────────────

    def update_target_network(self):
        """Hard update: copy online weights to target network."""
        self.target_model.set_weights(self.model.get_weights())

    def soft_update_target(self, tau=0.005):
        """Polyak averaging: target slowly tracks online — prevents sudden jumps that cause forgetting."""
        online_w = self.model.get_weights()
        target_w = self.target_model.get_weights()
        self.target_model.set_weights([
            tau * ow + (1.0 - tau) * tw
            for ow, tw in zip(online_w, target_w)
        ])

    # ── Epsilon decay ─────────────────────────────────────────────────────────

    def decay_epsilon(self):
        self.epsilon = max(self.epsilon_min, self.epsilon * self.epsilon_decay)

    # ── Persistence ───────────────────────────────────────────────────────────

    def save(self, path):
        self.model.save_weights(path)

    def load(self, path):
        self.model.load_weights(path)
        self.update_target_network()
