import os
from dataclasses import dataclass, field
from typing import Dict, List, Union

import regex as re
import typer

from spcal.cell_path_evaluator import read_netlist
from spcal.netlist_graph import load_config, parse_all_netlist_entries


@dataclass
class NetlistEntry:
    """
    Dataclass to represent a cell in the netlist, with input and output wires.
    """

    cell_type: str
    cell_name: str
    input_wires: Dict[str, Dict[str, float]] = field(default_factory=dict)
    output_wires: Dict[str, Dict[str, float]] = field(default_factory=dict)


def parse_saif(name, verilog_file, rpt_file, saif_file, configs, output_path):
    configs = load_config(configs)
    netlist_entries = read_netlist(verilog_file)
    netlist_dict = parse_all_netlist_entries(netlist_entries, configs)

    target_nodes = []
    wires = []
    with open(rpt_file, "r") as f:
        for line in f:
            matches = re.findall(r"\b(U\d+)/(\w+)\b", line)
            for u_num, port in matches:
                target_nodes.append((u_num, port))
                try:
                    wires.append((netlist_dict[u_num].output_wires)[port]["wire"])
                except KeyError:
                    typer.echo(
                        typer.style(
                            f"ERROR: KEYERROR. Sth wrong in '{rpt_file}'.",
                            fg=typer.colors.RED,
                        )
                    )
                    raise typer.Abort()

    if saif_file and os.path.exists(saif_file):
        with open(saif_file, "r") as f:
            content = f.read()
    else:
        typer.echo(typer.style(f"ERROR: {name}.saif Not found.", fg=typer.colors.RED))
        return {}

    net_pattern = r"\(NET(?:[^()]*|\((?:[^()]*|\([^()]*\))*\))*\)"

    try:
        net_content = re.findall(net_pattern, content)
        if isinstance(net_content, list):
            net_content = " ".join(net_content)
            lines = net_content.splitlines()
            if len(lines) > 1:
                lines = lines[1:-1]
            net_content = "\n".join(lines)
    except re.error as e:
        print(f"Error in regex pattern for net content: {e}")
        return {}

    node_pattern = re.compile(
        r"\(\s*(\w+)\s*((?:\([^()]*\)|[^()])*?)\s*\)\s*(?=\(\w+|\Z)", re.DOTALL
    )
    nodes = node_pattern.findall(net_content)

    saif_data = {}
    for node_name, node_body in nodes:
        t0_match = re.search(r"\(T0\s+(\d+)", node_body)
        t1_match = re.search(r"\(T1\s+(\d+)", node_body)
        if t0_match and t1_match:
            t0 = int(t0_match.group(1))
            t1 = int(t1_match.group(1))
            total = t0 + t1
            ratio = t1 / total if total != 0 else 0.5
            saif_data[node_name] = ratio
        else:
            saif_data[node_name] = -1.0

    print(saif_data)

    with open(output_path, "w") as file:
        for i, inp in enumerate(wires):
            file.write(
                f"{target_nodes[i][0]}/{target_nodes[i][1]}: {saif_data.get(inp, 0.5)}\n"
            )

    typer.echo(typer.style(f"{name}.saif Done.", fg=typer.colors.GREEN))


if __name__ == "__main__":

    # FIXME: Input path should not be hardcoded

    all_names = [
        "Priority",
        "adder",
        "arbiter",
        "bar",
        "c1355",
        "c17",
        "c1908",
        "c2670",
        "c3540",
        "c432",
        "c499",
        "c5315",
        "c6288",
        "c7552",
        "c880",
        "cavlc",
        "ctrl",
        "dec",
        "i2c",
        "log2",
        "max",
        "memctrl",
        "multiplier",
        "router",
        "sin",
        "sqrt",
        "square",
        "voter",
    ]

    test_names = ["c17"]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    proj_dir = os.path.join(base_dir, "../../../")

    for name in test_names:

        verilog_file = os.path.join(proj_dir, f"data/netlist/{name}_flattened.v")
        rpt_file = os.path.join(
            proj_dir, f"data/raw/benchmark/{name}/{name}.timing.rpt"
        )
        saif_file = os.path.join(proj_dir, f"data/saif/{name}.saif")
        configs = os.path.join(proj_dir, f"configs/{name}.yaml")
        output_path = os.path.join(proj_dir, f"outputs/{name}/saif_result.txt")

        parse_saif(name, verilog_file, rpt_file, saif_file, configs, output_path)
