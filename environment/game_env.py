import random
import numpy as np
from environment.question_space import QuestionSpace


# ── Pre-computed math sets ──────────────────────────────────────────────────

def _sieve(n):
    flags = [True] * (n + 1)
    flags[0] = flags[1] = False
    for i in range(2, int(n ** 0.5) + 1):
        if flags[i]:
            for j in range(i * i, n + 1, i):
                flags[j] = False
    return {i for i in range(2, n + 1) if flags[i]}

_PRIME_SET = _sieve(1000)


def _fib_set(n):
    fibs, a, b = set(), 1, 1
    while a <= n:
        fibs.add(a)
        a, b = b, a + b
    return fibs

_FIBONACCI_SET    = _fib_set(1000)
_POWER_OF_2_SET   = {2 ** i for i in range(10) if 2 ** i <= 1000}
_PERFECT_CUBE_SET = {i ** 3 for i in range(1, 11) if i ** 3 <= 1000}
_SMALL_PRIMES     = {2, 3, 5, 7, 11, 13, 17, 19, 23}


def _tri_set(n):
    tris, k = set(), 1
    while (t := k * (k + 1) // 2) <= n:
        tris.add(t)
        k += 1
    return tris

_TRIANGULAR_SET = _tri_set(1000)


def _abundant_set(n):
    s = set()
    for x in range(1, n + 1):
        total = 1
        d = 2
        while d * d <= x:
            if x % d == 0:
                total += d
                if d != x // d:
                    total += x // d
            d += 1
        if total > x:
            s.add(x)
    return s

_ABUNDANT_SET = _abundant_set(1000)


def _square_free_set(n):
    s = set()
    for x in range(1, n + 1):
        free = True
        p = 2
        while p * p <= x:
            if x % (p * p) == 0:
                free = False
                break
            p += 1
        if free:
            s.add(x)
    return s

_SQUARE_FREE_SET = _square_free_set(1000)


# ── Digit helpers ────────────────────────────────────────────────────────────

def _digit_sum(n):
    return sum(int(d) for d in str(n))


def _product_digits(n):
    p = 1
    for d in str(n):
        p *= int(d)
    return p


def _get_digit(n, pos):
    if pos == "hundreds":
        return (n // 100) % 10
    elif pos == "tens":
        return (n // 10) % 10
    return n % 10


# ── Special-property matcher (shared by answer and filter) ───────────────────

def _special_matches(n, prop):
    if prop == "perfect_square":
        r = int(n ** 0.5)
        return r * r == n
    if prop == "perfect_cube":
        r = round(n ** (1 / 3))
        return r * r * r == n
    if prop == "prime":
        return n in _PRIME_SET
    if prop == "palindrome":
        s = str(n)
        return s == s[::-1]
    if prop == "fibonacci":
        return n in _FIBONACCI_SET
    if prop == "repeated_digit":
        s = str(n)
        return len(s) != len(set(s))
    if prop == "power_of_2":
        return n in _POWER_OF_2_SET
    if prop == "triangular":
        return n in _TRIANGULAR_SET
    if prop == "digit_sum_prime":
        return _digit_sum(n) in _SMALL_PRIMES
    if prop == "abundant":
        return n in _ABUNDANT_SET
    if prop == "harshad":
        ds = _digit_sum(n)
        return ds > 0 and n % ds == 0
    if prop == "two_digit":
        return 10 <= n <= 99
    if prop == "three_digit":
        return 100 <= n <= 999
    if prop == "product_gt_50":
        return _product_digits(n) > 50
    if prop == "all_digits_odd":
        return all(int(d) % 2 != 0 for d in str(n))
    if prop == "ends_in_same":
        s = str(n)
        return s[0] == s[-1]
    if prop == "all_digits_even":
        return all(int(d) % 2 == 0 for d in str(n))
    if prop == "contains_zero":
        return "0" in str(n)
    if prop == "ascending_digits":
        ds = [int(d) for d in str(n)]
        return all(ds[i] < ds[i + 1] for i in range(len(ds) - 1))
    if prop == "descending_digits":
        ds = [int(d) for d in str(n)]
        return all(ds[i] > ds[i + 1] for i in range(len(ds) - 1))
    if prop == "digit_sum_square":
        ds = _digit_sum(n)
        r = round(ds ** 0.5)
        return r * r == ds
    if prop == "alternating_parity":
        ds = [int(d) for d in str(n)]
        return all((ds[i] % 2) != (ds[i + 1] % 2) for i in range(len(ds) - 1))
    if prop == "square_free":
        return n in _SQUARE_FREE_SET
    if prop == "digit_product_gt_digit_sum":
        return _product_digits(n) > _digit_sum(n)
    return False


# ── Environment ──────────────────────────────────────────────────────────────

class NumberGuessingEnv:
    # Fixed order so type-usage state features are always at the same index
    _TYPE_ORDER = [
        "range", "proximity", "parity", "modular",
        "digit_sum", "special", "digit_compare", "divisible",
    ]

    # Number of spatial histogram buckets (each covers 100 numbers for range 1-1000)
    _N_BUCKETS = 10

    def __init__(self, number_range=(1, 1000), max_questions=6):
        self.number_range         = number_range
        self.max_questions        = max_questions
        self.question_space       = QuestionSpace(number_range)
        self.secret_number        = None
        self.questions_asked      = 0
        self.remaining_candidates = []
        self.question_history     = []
        self.asked_action_set     = set()
        self.asked_type_counts    = {}

    def reset(self):
        low, high = self.number_range
        self.secret_number        = random.randint(low, high)
        self.remaining_candidates = list(range(low, high + 1))
        self.questions_asked      = 0
        self.question_history     = []
        self.asked_action_set     = set()
        self.asked_type_counts    = {}
        return self.get_state()

    def get_forbidden_actions(self):
        forbidden = set()
        for i, q in enumerate(self.question_space.all_questions):
            if i in self.asked_action_set:
                forbidden.add(i)
            elif self.asked_type_counts.get(q["type"], 0) >= 2:
                forbidden.add(i)
        return forbidden

    def step(self, action):
        self.asked_action_set.add(action)
        qtype = self.question_space.decode_action(action)["type"]
        self.asked_type_counts[qtype] = self.asked_type_counts.get(qtype, 0) + 1

        q   = self.question_space.decode_action(action)
        ans = self.answer_question(q)
        self.update_candidates(q, ans)
        self.question_history.append((q, ans))
        self.questions_asked += 1
        done = self.questions_asked >= self.max_questions

        info = {"secret": self.secret_number, "guess": None}

        # Early termination: nailed it down to one number, guess immediately
        if len(self.remaining_candidates) == 1:
            guess         = self.remaining_candidates[0]
            reward        = self.calculate_reward(guess)
            info["guess"] = guess
            return self.get_state(), reward, True, info

        if done:
            mid           = len(self.remaining_candidates) // 2
            guess         = self.remaining_candidates[mid]
            reward        = self.calculate_reward(guess)
            info["guess"] = guess
        else:
            reward = -1

        return self.get_state(), reward, done, info

    # ── Answering questions ──────────────────────────────────────────────────

    def answer_question(self, q):
        secret = self.secret_number
        qtype  = q["type"]

        if qtype == "range":
            return "yes" if q["low"] <= secret <= q["high"] else "no"

        if qtype == "proximity":
            dist_a = abs(secret - q["a"])
            dist_b = abs(secret - q["b"])
            if dist_a < dist_b:
                return f"closer to {q['a']}"
            elif dist_b < dist_a:
                return f"closer to {q['b']}"
            return "equidistant"

        if qtype == "parity":
            return "even" if secret % 2 == 0 else "odd"

        if qtype == "modular":
            return str(secret % q["divisor"])

        if qtype == "digit_sum":
            return "yes" if _digit_sum(secret) > q["threshold"] else "no"

        if qtype == "divisible":
            return "yes" if secret % q["divisor"] == 0 else "no"

        if qtype == "digit_compare":
            d1 = _get_digit(secret, q["pos1"])
            d2 = _get_digit(secret, q["pos2"])
            return "yes" if d1 > d2 else "no"

        if qtype == "special":
            return "yes" if _special_matches(secret, q["property"]) else "no"

        return ""

    # ── Filtering candidates ─────────────────────────────────────────────────

    def update_candidates(self, q, ans):
        prev  = self.remaining_candidates
        qtype = q["type"]

        if qtype == "range":
            new_cands = [n for n in prev if (q["low"] <= n <= q["high"]) == (ans == "yes")]

        elif qtype == "proximity":
            def _prox_matches(n):
                da, db = abs(n - q["a"]), abs(n - q["b"])
                if ans == "equidistant":
                    return da == db
                if ans == f"closer to {q['a']}":
                    return da < db
                return db < da
            new_cands = [n for n in prev if _prox_matches(n)]

        elif qtype == "parity":
            new_cands = [n for n in prev if (n % 2 == 0) == (ans == "even")]

        elif qtype == "modular":
            rem = int(ans)
            new_cands = [n for n in prev if n % q["divisor"] == rem]

        elif qtype == "digit_sum":
            t = q["threshold"]
            new_cands = [n for n in prev if (_digit_sum(n) > t) == (ans == "yes")]

        elif qtype == "divisible":
            new_cands = [n for n in prev if (n % q["divisor"] == 0) == (ans == "yes")]

        elif qtype == "digit_compare":
            new_cands = [n for n in prev
                         if (_get_digit(n, q["pos1"]) > _get_digit(n, q["pos2"])) == (ans == "yes")]

        elif qtype == "special":
            prop = q["property"]
            new_cands = [n for n in prev if _special_matches(n, prop) == (ans == "yes")]

        else:
            new_cands = prev

        self.remaining_candidates = new_cands if new_cands else prev

    # ── State representation ─────────────────────────────────────────────────

    def get_state(self):
        """
        26-feature state vector:
          [0]   candidate count / total range
          [1]   min candidate / range_max
          [2]   max candidate / range_max
          [3]   questions asked / max_questions
          [4]   questions remaining / max_questions
          [5]   mean of remaining candidates / range_max
          [6]   median of remaining candidates / range_max    ← optimal guess signal
          [7]   std dev of remaining candidates / (range_max / 2)
          [8-17] 10 spatial histogram buckets (each: fraction of that 100-wide band still active)
          [18-25] 8 per-type question-usage counts (0 / 0.5 / 1.0)
        """
        cands     = self.remaining_candidates
        lo, hi    = self.number_range
        span      = hi - lo + 1
        cand_arr  = np.array(cands, dtype=np.float32)

        # Base features
        base = np.array([
            len(cands) / span,
            float(cand_arr.min()) / hi,
            float(cand_arr.max()) / hi,
            self.questions_asked / self.max_questions,
            (self.max_questions - self.questions_asked) / self.max_questions,
        ], dtype=np.float32)

        # Distribution summary
        mean_f   = float(cand_arr.mean()) / hi
        median_f = float(np.median(cand_arr)) / hi
        std_f    = float(cand_arr.std()) / (hi / 2.0)
        dist_feats = np.array([mean_f, median_f, std_f], dtype=np.float32)

        # Spatial histogram: 10 buckets of 100 numbers each (1-100, 101-200, …, 901-1000)
        counts, _ = np.histogram(cand_arr, bins=self._N_BUCKETS, range=(lo, hi + 1))
        hist = counts.astype(np.float32) / (span / self._N_BUCKETS)

        # Type-usage counts
        type_counts = np.array([
            self.asked_type_counts.get(t, 0) / 2.0
            for t in self._TYPE_ORDER
        ], dtype=np.float32)

        return np.concatenate([base, dist_feats, hist, type_counts])

    # ── Reward ───────────────────────────────────────────────────────────────

    def calculate_reward(self, guess):
        if guess == self.secret_number:
            return 100 - (self.questions_asked * 2)
        proximity_bonus = max(0, 50 - abs(guess - self.secret_number) * 0.1)
        return -50 + proximity_bonus

    def render(self):
        last_qa = self.question_history[-1] if self.question_history else ("—", "—")
        print(
            f"Secret: {self.secret_number} | "
            f"Asked: {self.questions_asked} | "
            f"Candidates: {len(self.remaining_candidates)} | "
            f"Last: {last_qa}"
        )
