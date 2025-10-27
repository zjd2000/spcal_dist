import itertools
import os

single_port_waveforms = [(0, 0, 0, 1), (0, 0, 1, 1), (0, 1, 1, 1)]


def get_expanded_waveforms(wave_combo):
    N = len(wave_combo)
    product_result = list(itertools.product(*wave_combo))
    port_waves = [[] for _ in range(N)]
    for tup in product_result:
        for i, val in enumerate(tup):
            port_waves[i].append(val)
    return tuple(port_waves)


def generate_all_port_combinations(num_ports):
    combos = list(itertools.product(single_port_waveforms, repeat=num_ports))
    results = []
    for combo in combos:
        expanded = get_expanded_waveforms(combo)
        results.append({"base_combo": combo, "expanded": expanded})
    return results


def save_waveforms_to_file(num_ports, results):
    filename = f"waveforms_{num_ports}.txt"
    filename = os.path.join(os.path.dirname(__file__), filename)
    with open(filename, "w") as f:
        for item in results:
            line_str = (
                f"Base Combo = {item['base_combo']}\n"
                f"Expanded   = {item['expanded']}\n"
                "---------------------------------------------------\n"
            )
            f.write(line_str)
    print(
        f"Written in waveforms_{num_ports}.txt, {3**num_ports*4**num_ports} combinations."
    )


def save_waveforms_to_file_port_by_line(num_ports, results):
    filename = f"waveforms_{num_ports}_portbyline.txt"
    filename = os.path.join(os.path.dirname(__file__), filename)
    all_port_waves = [[] for _ in range(num_ports)]

    for item in results:
        expanded = item["expanded"]
        for port_idx in range(num_ports):
            all_port_waves[port_idx].extend(expanded[port_idx])

    with open(filename, "w") as f:
        for port_idx in range(num_ports):
            f.write(str(all_port_waves[port_idx]) + "\n")


def main():
    for p in range(2, 7):
        print(f"Processing {p} ports...")
        results = generate_all_port_combinations(p)
        save_waveforms_to_file(p, results)
        save_waveforms_to_file_port_by_line(p, results)


if __name__ == "__main__":
    main()
