import json
import os
import re

import typer
import yaml


def load_config(config_file):
    """
    Load configuration file for input and output port prefixes, and stop_set.
    Supports both single values and lists for `external_sp_inputs_spec` (float or list of floats)
    and `external_signal_inputs_spec` (int or list of ints).
    """

    try:
        with open(config_file, "r") as file:
            config = yaml.safe_load(file)
    except FileNotFoundError:
        typer.echo(
            typer.style(
                f"\nConfiguration file '{config_file}' not found.", fg=typer.colors.RED
            )
        )
        typer.Exit(1)

    libraries = config.get("libs", [])

    input_port_prefixes = config.get("port_prefixes", {}).get("input", [])
    output_port_prefixes = config.get("port_prefixes", {}).get("output", [])

    # Process `external_sp_inputs_spec` to support both float and list of floats
    external_sp_inputs_spec = config.get("external_sp_inputs_spec", {})
    external_sp_inputs_spec = {
        key: float(value) if isinstance(value, float) else [float(v) for v in value]
        for key, value in external_sp_inputs_spec.items()
    }

    # Process `external_signal_inputs_spec` to support both int and list of ints
    external_signal_inputs_spec = config.get("external_signal_inputs_spec", {})
    external_signal_inputs_spec = {
        key: int(value) if isinstance(value, int) else [int(v) for v in value]
        for key, value in external_signal_inputs_spec.items()
    }

    config["libraries"] = libraries
    config["port_prefixes"] = {
        "input": input_port_prefixes,
        "output": output_port_prefixes,
    }
    config["external_sp_inputs_spec"] = external_sp_inputs_spec
    config["external_signal_inputs_spec"] = external_signal_inputs_spec

    return config


def load_netlist(file_path):
    """
    Reads a file and returns a list of lines that match the given pattern,
    excluding empty lines. If a line does not match the pattern, it raises an error and exits.
    """
    pattern = re.compile(r"^(?!module\b)(\S+)\s+(\S+)\s*\((.+?)\);$")

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()

        filtered_lines = []
        for line in lines:
            stripped_line = line.strip()
            if stripped_line:  # Ignore empty lines
                if not pattern.match(stripped_line):
                    raise ValueError(f"\nInvalid line format: {stripped_line}")
                filtered_lines.append(stripped_line)

        return filtered_lines

    except FileNotFoundError:
        typer.echo(typer.style(f"\nFile '{file_path}' not found.", fg=typer.colors.RED))
        raise SystemExit(1)
    except ValueError as ve:
        typer.echo(typer.style(str(ve), fg=typer.colors.RED))
        raise SystemExit(1)
    except Exception as e:
        typer.echo(typer.style(f"\nError reading file: {e}", fg=typer.colors.RED))
        raise SystemExit(1)


def load_functions(lib_dir, configs):
    """
    Load functions from library JSONs into a nested dict: Dict[str, Dict[str, str]]

    - libraries: configs["libraries"] is a list of library base names (without .json)
    """
    functions = {}
    libraries = configs["libraries"]

    if not libraries:
        typer.echo(
            typer.style(
                "\nNo libraries specified in the configuration file.\n",
                fg=typer.colors.RED,
            )
        )
        raise typer.Exit(code=1)

    for lib in libraries:
        lib_path = os.path.join(lib_dir, lib + ".json")
        if not os.path.exists(lib_path):
            typer.echo(
                typer.style(f"\nFile '{lib_path}' not found.", fg=typer.colors.RED)
            )
            raise typer.Exit(code=1)

        with open(lib_path, "r", encoding="utf-8") as file:
            config = json.load(file)

        for cell in config.get("cells", []):
            cell_name = cell.get("cell_name")
            output_pins = cell.get("output_pins", [])
            pin_dict = {}
            for pin in output_pins:
                pin_name = pin.get("pin_name")
                func = pin.get("function")

                if isinstance(func, str):
                    func = re.sub(r"\bIQ\b", "D", func)
                    func = re.sub(r"\bIQN\b", "!D", func)

                pin_dict[pin_name] = func

            functions[cell_name] = pin_dict

    return functions


def load_cdls(base_dir, configs):
    """
    Load CDL files and merge them into a single dictionary.
    Dict[str, Dict[str, Dict[str, str]]]
    """

    cdls_dict = {}
    cdls = configs["cdls"]

    if not cdls:
        typer.echo(
            typer.style("\nNo CDL specified in the config file.\n", fg=typer.colors.RED)
        )
        raise typer.Exit(code=1)

    for cdl in cdls:
        cdl_path = os.path.join(base_dir, "data/cdl", cdl + ".json")
        if not os.path.exists(cdl_path):
            typer.echo(
                typer.style(f"\nFile '{cdl_path}' not found.", fg=typer.colors.RED)
            )
            typer.Exit(code=1)

        with open(cdl_path, "r") as file:
            config = json.load(file)

        for item in config:
            item_type = item.get("type")
            if item_type:
                interfaces = item.get("interfaces", [])

                item["interfaces"] = interfaces

                mos_transistors = item.get("mos_transistors", {})
                if item_type not in cdls_dict:
                    cdls_dict[item_type] = {
                        "mos_transistors": mos_transistors,
                        "interfaces": interfaces,
                    }
                else:
                    cdls_dict[item_type]["mos_transistors"].update(mos_transistors)
                    cdls_dict[item_type]["interfaces"].extend(interfaces)

    return cdls_dict
