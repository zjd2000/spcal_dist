import json
import os
import re
import time

import typer
import yaml
from yaspin import yaspin


def extract_block(content, start_pattern):
    match = re.search(start_pattern, content)
    if not match:
        return None, content

    start_idx = match.start()
    brace_count = 1
    end_idx = match.end()

    while brace_count > 0 and end_idx < len(content):
        if content[end_idx] == "{":
            brace_count += 1
        elif content[end_idx] == "}":
            brace_count -= 1
        end_idx += 1

    return content[start_idx:end_idx], content[end_idx:]


def parse_lib_file(file_content):
    cells = []
    remaining_content = file_content
    while True:
        cell_block, remaining_content = extract_block(
            remaining_content, r"\bcell\b\s+\(([\w\d_]+)\)\s*{"
        )
        if not cell_block:
            break

        cell_name_match = re.search(r"cell\s+\(([\w\d_]+)\)", cell_block)
        cell_name = cell_name_match.group(1) if cell_name_match else None

        pins = []
        pin_content = cell_block
        while True:
            pin_block, pin_content = extract_block(
                pin_content, r"\bpin\b\s+\(([\w\d_]+)\)\s*{"
            )
            if not pin_block:
                break

            pin_name_match = re.search(r"\bpin\b\s+\(([\w\d_]+)\)", pin_block)
            pin_name = pin_name_match.group(1) if pin_name_match else None

            direction_match = re.search(r"\bdirection\b\s*:\s*output", pin_block)

            if direction_match:
                function_match = re.search(r"\bfunction\b\s*:\s*\"(.*?)\"", pin_block)
                pin_function = function_match.group(1) if function_match else None
                pins.append({"pin_name": pin_name, "function": pin_function})

        if cell_name and pins:
            cells.append({"cell_name": cell_name, "output_pins": pins})

    return {"cells": cells}


def generate_lib_json(parsed_data):
    return json.dumps(parsed_data, indent=2)


def main(lib, override=True):
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")
    input_file_path = os.path.join(base_dir, "data/raw/lib", lib + ".cdl")
    output_file_path = os.path.join(base_dir, "data/lib", lib + ".json")
    file_content = ""

    if os.path.exists(output_file_path):
        if override:
            os.remove(output_file_path)
        else:
            typer.echo(
                typer.style(
                    f"File '{os.path.normpath(output_file_path)}' already exists.",
                    fg=typer.colors.YELLOW,
                )
            )
            return

    try:
        with open(input_file_path, "r") as file:
            file_content = file.read()
    except FileNotFoundError:
        typer.echo(
            typer.style(f"File '{input_file_path}' not found.", fg=typer.colors.RED)
        )
        typer.Exit(code=1)

    parsed_data = parse_lib_file(file_content)
    output_content = generate_lib_json(parsed_data)
    output_file_path = os.path.join(base_dir, "data/lib", lib + ".json")

    with open(output_file_path, "w") as file:
        file.write(output_content)

    typer.echo(typer.style(f"{lib} DONE.", fg=typer.colors.GREEN))


if __name__ == "__main__":
    """
    Put the LIB files in the data/raw/lib directory.
    The script will parse the LIB files and generate JSON files in the data/lib directory.
    If override is set to True, the script will remove the existing JSON files.
    """

    lib_names = [
        "asap7sc7p5t_SIMPLE_RVT_TT_nldm_211120",
        "asap7sc7p5t_AO_RVT_TT_nldm_211120",
        "asap7sc7p5t_INVBUF_RVT_TT_nldm_220122",
        "asap7sc7p5t_OA_RVT_TT_nldm_211120",
        "asap7sc7p5t_SEQ_RVT_TT_nldm_220123",
        "custom_lib",
    ]

    for lib in lib_names:
        try:
            main(lib, override=False)
        except Exception as e:
            print(e)
