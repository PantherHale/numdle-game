class QuestionSpace:
    def __init__(self, number_range=(1, 1000)):
        self.number_range  = number_range
        self.all_questions = []
        self._build_questions()

    def _build_questions(self):
        # RANGE (44) — various window sizes and positions
        range_pairs = [
            # prefix ranges
            (1, 100), (1, 200), (1, 300), (1, 400), (1, 500),
            (1, 600), (1, 700), (1, 800), (1, 900),
            # century bands
            (101, 200), (201, 300), (301, 400), (401, 500),
            (501, 600), (601, 700), (701, 800), (801, 900), (901, 1000),
            # bisections
            (1, 500), (251, 750), (1, 333), (334, 666), (667, 1000),
            # quarter splits
            (1, 250), (251, 500), (501, 750), (751, 1000),
            # fifth splits
            (201, 400), (401, 600), (601, 800), (801, 1000),
            # eighth bands
            (1, 125), (126, 250), (251, 375), (376, 500),
            (501, 625), (626, 750), (751, 875), (876, 1000),
            # centered symmetric
            (300, 700), (350, 650), (400, 600),
            # three-quarter spans
            (1, 750), (251, 1000),
        ]
        for low, high in range_pairs:
            self.all_questions.append({"type": "range", "low": low, "high": high})

        # PROXIMITY (12) — landmark distance comparisons
        proximity_pairs = [
            (250, 750), (100, 900), (200, 800), (300, 700), (400, 600),
            (150, 850), (333, 666), (50, 950), (450, 550), (100, 500),
            (125, 875), (375, 625),
        ]
        for a, b in proximity_pairs:
            self.all_questions.append({"type": "proximity", "a": a, "b": b})

        # PARITY (1)
        self.all_questions.append({"type": "parity"})

        # MODULAR (4) — mod-10 excluded: it directly reveals the units digit
        for divisor in [2, 3, 4, 5]:
            self.all_questions.append({"type": "modular", "divisor": divisor})

        # DIGIT SUM THRESHOLD (5)
        for threshold in [5, 10, 15, 20, 25]:
            self.all_questions.append({"type": "digit_sum", "threshold": threshold})

        # SPECIAL PROPERTIES (8)
        for prop in [
            "perfect_square",  # 31 numbers in 1–1000
            "prime",           # 168 numbers
            "palindrome",      # 108 numbers
            "fibonacci",       # 16 numbers
            "repeated_digit",
            "power_of_2",      # 10 numbers
            "triangular",      # 44 numbers
            "digit_sum_prime",
        ]:
            self.all_questions.append({"type": "special", "property": prop})

        # DIGIT COMPARISON (3)
        for pos1, pos2 in [("hundreds", "units"), ("tens", "hundreds"), ("units", "tens")]:
            self.all_questions.append({"type": "digit_compare", "pos1": pos1, "pos2": pos2})

        # DIVISIBILITY YES/NO (5)
        for divisor in [6, 7, 9, 11, 25]:
            self.all_questions.append({"type": "divisible", "divisor": divisor})

    def decode_action(self, i):
        if i < 0 or i >= len(self.all_questions):
            return self.all_questions[0]
        return self.all_questions[i]

    def size(self):
        return len(self.all_questions)

    def describe(self, i):
        q     = self.decode_action(i)
        qtype = q["type"]

        if qtype == "range":
            return f"Is the number between {q['low']} and {q['high']}?"
        elif qtype == "proximity":
            return f"Is the number closer to {q['a']} or {q['b']}?"
        elif qtype == "parity":
            return "Is the number even or odd?"
        elif qtype == "modular":
            return f"What is the number modulo {q['divisor']}?"
        elif qtype == "digit_sum":
            return f"Is the digit sum greater than {q['threshold']}?"
        elif qtype == "special":
            labels = {
                "perfect_square":  "Is the number a perfect square?",
                "prime":           "Is the number prime?",
                "palindrome":      "Is the number a palindrome?",
                "fibonacci":       "Is the number a Fibonacci number?",
                "repeated_digit":  "Does the number have a repeated digit?",
                "power_of_2":      "Is the number a power of 2?",
                "triangular":      "Is the number a triangular number?",
                "digit_sum_prime": "Is the digit sum itself a prime number?",
            }
            return labels.get(q["property"], "Unknown special property")
        elif qtype == "digit_compare":
            return f"Is the {q['pos1']} digit greater than the {q['pos2']} digit?"
        elif qtype == "divisible":
            return f"Is the number divisible by {q['divisor']}?"
        return "Unknown question type"
