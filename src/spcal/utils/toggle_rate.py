from typing import List


def calculate_toggle_rate(sequence: List[int]) -> float:
    """
    Calculate the toggle rate in a binary sequence.
    toggle is defined as a change from 0 to 1 or from 1 to 0.

    :param sequence: A list of binary values (0 and 1).
    :return: The toggle rate as a float (number of flips / total transitions).
    """
    if len(sequence) < 2:
        return 0.0  # No transitions possible in a sequence with less than 2 elements

    toggles = sum(1 for i in range(1, len(sequence)) if sequence[i] != sequence[i - 1])
    total_transitions = len(sequence) - 1
    toggle_rate = toggles / total_transitions

    return toggle_rate


if __name__ == "__main__":
    sequence1 = [0, 1, 0, 1, 1, 0, 0]
    sequence2 = [1, 1, 1, 1, 0, 0, 0]
    sequence3 = [0, 0]
    sequence4 = []

    print(calculate_toggle_rate(sequence1))  # Output: 0.6666
    print(calculate_toggle_rate(sequence2))  # Output: 0.1666
    print(calculate_toggle_rate(sequence3))  # Output: 0.0
    print(calculate_toggle_rate(sequence4))  # Output: 0.0
