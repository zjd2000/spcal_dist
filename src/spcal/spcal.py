# main.py
import os
import sys
import time
from typing import Any, Dict, List, Union, Optional
import typer

os.environ["LOG_LEVEL"] = (
    "DEBUG" if os.getenv("LOG_LEVEL") is None else os.getenv("LOG_LEVEL")
)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from spcal.cell_iterator import CellIterator
from spcal.fixed_point import FixedPointConfig, solve_placeholders
from spcal.netlist_graph import NetlistGraph
from spcal.sp_eval import evaluate_cells
from spcal.utils.load_files import load_config, load_netlist
from spcal.utils.logger import logger
from spcal.utils.visulize import (visualize_interactive_netlist_graph,
                                  visualize_netlist_graph)

app = typer.Typer()
base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../")

@app.command(name="sp")
def sp(
    cell_name: Optional[Union[str, List[str]]] = typer.Option(
        None, help="The target cell to compute the SP on the call path."
    ),
    data_dir: Optional[str] = typer.Option(
        None, help="The data dir to use for the computation. path = ./data_dir"
    ),
    netlist: Optional[str] = typer.Option(
        None, help="The netlist file to use for the computation. path = ./data/netlist.v"
    ),
    config: Optional[str] = typer.Option(
        None, help="The configs file to use for the computation. path = ./configs.yaml"
    ),
    bdd_backend: Optional[str] = typer.Option(
        None, help="The BDD backend to use for the computation. options: cudd, sylvan, autoref",
    ),
    visual: str = typer.Option(
        "false", help="Visualize the computation results.options: [true, false, partial]"
    ),
    output_dir: str = typer.Option(
        "outputs", help="The output folder name to store the results."
    ),
    bdd_dump_path: Optional[str] = typer.Option(
        None, help="The path to dump the BDD graph. path = ./outputs/netlist_bdd.json"
    ),
    bdd_dump_format: str = typer.Option(
        "dag", help="The format to dump the BDD graph. options: [dag, expr]"
    ),
    overwrite: bool = typer.Option(
        False, help="Overwrite the output folder if it exists."
    ),
):
    # Convert OptionInfo/None into the strict types expected by sp_core
    if not cell_name:
        raise typer.BadParameter("require cell_name.")
    if not data_dir:
        raise typer.BadParameter("require data_dir.")
    if not netlist:
        raise typer.BadParameter("require netlist.")
    if not config:
        raise typer.BadParameter("require config.")

    sp_core(
        cell_name=cell_name,
        data_dir=data_dir,
        netlist=netlist,
        config=config,
        bdd_backend=bdd_backend,
        visual=visual,
        output_dir=output_dir,
        bdd_dump_path=bdd_dump_path,
        bdd_dump_format=bdd_dump_format,
        overwrite=overwrite,
    )

def sp_core(
    *,
    cell_name: Union[str, List[str]],
    data_dir: str,
    netlist: str,
    config: str,
    bdd_backend: Optional[str],
    visual: str,
    output_dir: str,
    bdd_dump_path: Optional[str],
    bdd_dump_format: str,
    overwrite: bool,
) -> None:

    assert cell_name, "require cell_name."
    assert data_dir, "require data_dir."
    assert netlist, "require netlist."
    assert config, "require config."

    visual = visual.lower()
    if visual not in ["true", "false", "partial"]:
        typer.echo(
            typer.style(
                "Invalid visual option specified. Please choose either 'True', 'False', or 'Partial'.",
                fg=typer.colors.RED,
            )
        )
        visual = typer.prompt("visual:")

    output_dir = os.path.join(base_dir, output_dir)
    lib_dir = os.path.join(base_dir, data_dir, "lib")
    bdd_dump_path = os.path.join(output_dir, bdd_dump_path) if bdd_dump_path else None

    os.makedirs(os.path.join(base_dir, "outputs"), exist_ok=True)

    # file names
    visualize_netlist_graph_file = os.path.join(output_dir, "netlist.png")
    visualize_interactive_netlist_graph_file = os.path.join(
        output_dir, "netlist_interactive.html"
    )

    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
    elif overwrite:
        os.system(f"rm -rf {output_dir}")
        os.makedirs(output_dir, exist_ok=True)
    else:
        typer.confirm(
            f"Output directory '{output_dir}' already exists. Do you want to continue?",
            abort=True,
        )

    time_start = time.perf_counter()

    cfg: Dict[str, Any] = load_config(os.path.join(base_dir, config))
    netlist_entries = load_netlist(os.path.join(base_dir, netlist))
    netlist_graph_obj = NetlistGraph(
        lib_dir, cfg, netlist_entries, bdd_backend=bdd_backend
    )

    if visual == "true":
        visualize_netlist_graph(
            netlist_graph_obj.get_graph(), visualize_netlist_graph_file
        )
        visualize_interactive_netlist_graph(
            netlist_graph_obj.get_graph(), visualize_interactive_netlist_graph_file
        )

    it = CellIterator(netlist_graph_obj)
    summary = it.run(
        max_rounds=2000,
        dump_path=bdd_dump_path,
        dump_format=bdd_dump_format,
    )
    logger.info(summary)

    tasks = it.collect_fixed_point_tasks()

    if tasks:
        fixed_point_config = FixedPointConfig()
        placeholder_probs = solve_placeholders(
            bdd=netlist_graph_obj.get_bdd(),
            external_sp_inputs_spec=cfg.get("external_sp_inputs_spec"),
            tasks=tasks,
            config=fixed_point_config,
        )
        logger.debug(f"{placeholder_probs=}")

    pi_probs: Dict[str, float] = cfg.get("external_sp_inputs_spec", {}) or {}
    merged_probs: Dict[str, float] = {**pi_probs, **placeholder_probs}
    logger.debug(f"[main] merged_probs={merged_probs}")

    if cell_name in ["ALL", "all", "All"]:
        cell_name = netlist_graph_obj.get_cell_names()
    else:
        if isinstance(cell_name, str):
            cell_name = [cell_name]

    sp_results = evaluate_cells(
        netlist_graph=netlist_graph_obj,
        probs=merged_probs,
        cell_names=cell_name,
    )
    logger.info(f"{sp_results=}")

    time_end = time.perf_counter()

    logger.info(f"SP analysis done.\nCost:{(time_end - time_start) * 1000:.4f} ms")


if __name__ == "__main__":

    #    demo_simple_cycle_arg = {
    #        "cell_name": "all",
    #        "data_dir": "spcal_data",
    #        "netlist": "demo/simple_cycle/simple_cycle_flattened.v",
    #        "config": "demo/simple_cycle/simple_cycle.yaml",
    #        "visual": "True",
    #        "output_dir": "demo/simple_cycle/outputs",
    #        "overwrite": "True",
    #    }

    #    demo_riscv_arg = {
    #        "cell_name": "all",
    #        "data_dir": "spcal_data",
    #        "netlist": "demo/riscv/riscv_flattened.v",
    #        "config": "demo/riscv/riscv.yaml",
    #        "visual": "False",
    #        "output_dir": "demo/riscv/outputs",
    #        "overwrite": "True",
    #    }

    demo_mac20_arg = {
        "cell_name": "bl16_U2",
        "data_dir": "spcal_data",
        "netlist": "demo/mac_20/mac_20_flattened.v",
        "config": "demo/mac_20/mac_20.yaml",
        "bdd_backend": "autoref",
        "visual": "False",
        "output_dir": "demo/mac_20/outputs",
        "bdd_dump_path": None,
        "bdd_dump_format": "dag",
        "overwrite": True,
    }

    sp_core(**demo_mac20_arg)

# "cell_name": "bl35b7_f_b_U5",
