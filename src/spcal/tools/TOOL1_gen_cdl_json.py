import json
import os
import re

import typer


def parse_subckt_file(file_content):

    subckt_blocks = re.findall(r"(\.SUBCKT.*?\.ENDS)", file_content, re.DOTALL)

    subckt_data = []

    for block in subckt_blocks:
        lines = block.strip().splitlines()

        subckt_info = lines[0].split()
        cell_type = subckt_info[1]
        interfaces = subckt_info[2:]

        mos_transistors = {}
        for line in lines[1:]:

            if line.startswith("MM"):
                mos_info = line.split()
                mos_transistors[mos_info[0]] = {
                    "ND": mos_info[1],
                    "NG": mos_info[2],
                    "NS": mos_info[3],
                    "NB": mos_info[4],
                    "Type": mos_info[5],
                    "w": mos_info[6],
                    "l": mos_info[7],
                    "nfin": mos_info[8],
                }

        subckt_data.append(
            {
                "type": cell_type,
                "interfaces": interfaces,
                "mos_transistors": mos_transistors,
            }
        )

    return subckt_data


def generate_cdl_json(parsed_data):
    return json.dumps(parsed_data, indent=4)


def main(cdl, override=True):

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")
    input_file_path = os.path.join(base_dir, "data/raw/cdl", cdl + ".cdl")
    output_file_path = os.path.join(base_dir, "data/cdl", cdl + ".json")
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
            file_content = file
    except FileNotFoundError:
        typer.echo(
            typer.style(f"File '{input_file_path}' not found.", fg=typer.colors.RED)
        )
        typer.Exit(code=1)

    parsed_data = parse_subckt_file(file_content)
    output_content = generate_cdl_json(parsed_data)
    output_file_path = os.path.join(base_dir, "data/cdl", cdl + ".json")

    with open(output_file_path, "w") as file:
        file.write(output_content)

    typer.echo(typer.style(f"{cdl} DONE.", fg=typer.colors.GREEN))


if __name__ == "__main__":
    """
    Put the CDL files in the data/raw/cdl directory.
    The script will parse the CDL files and generate JSON files in the data/cdl directory.
    The script will also remove the existing JSON files if override is set to True.
    """

    cdl_names = [
        "asap7sc7p5t_28_L",
        "asap7sc7p5t_28_R",
        "asap7sc7p5t_28_SL",
        "asap7sc7p5t_28_SRAM",
        "custom_cdl",
    ]

    for cdl in cdl_names:
        try:
            main(cdl, override=False)
        except Exception as e:
            print(e)
