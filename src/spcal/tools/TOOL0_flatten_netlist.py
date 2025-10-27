import os
import re

import typer


def process_netlist(input_file, output_file, log_file):
    with open(input_file, "r", encoding="utf-8") as infile:
        lines = infile.readlines()

    new_lines = []
    temp_line = ""

    for line in lines:
        stripped_line = line.lstrip().rstrip()

        if stripped_line.startswith("//"):
            continue

        temp_line += " " + stripped_line if temp_line else stripped_line

        if stripped_line.endswith(";"):
            new_lines.append(temp_line)
            temp_line = ""

    if temp_line:
        new_lines.append(temp_line)

    pattern = re.compile(r"^(?!module\b)(\S+)\s+(\S+)\s*\((.+?)\);$")

    valid_lines = []
    invalid_lines = []

    for line in new_lines:
        if pattern.match(line):
            valid_lines.append(line)
        else:
            invalid_lines.append(line)

    with open(output_file, "w", encoding="utf-8") as outfile:
        for line in valid_lines:
            outfile.write(line + "\n")

    typer.echo(
        typer.style(f"{os.path.normpath(output_file)} completed", fg=typer.colors.GREEN)
    )

    if log_file is not None:
        with open(log_file, "w", encoding="utf-8") as logfile:
            for line in invalid_lines:
                logfile.write(line + "\n")
        print(f"Invalid lines logged in {log_file}")


def main(input_path, output_path, exclude_suffix_in_dir):
    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")

    if os.path.isfile(input_path):
        input_file = input_path
        name = os.path.splitext(os.path.basename(input_file))[0]

        if exclude_suffix_in_dir in name:
            print(
                f"Skipping file {input_file} due to excluded suffix '{exclude_suffix_in_dir}'"
            )
            return

        output_file = output_path
        log_file = os.path.normpath(
            os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "tmp", name + "_invalid.log"
            )
        )
        process_netlist(input_file, output_file, None)

    elif os.path.isdir(input_path):
        for root, dirs, files in os.walk(input_path):
            for filename in files:
                if filename.endswith(".v"):
                    if exclude_suffix_in_dir in filename:
                        continue

                    file_path = os.path.join(root, filename)
                    name = os.path.splitext(filename)[0]
                    output_file = os.path.normpath(
                        os.path.join(base_dir, "data/netlist/", name + "_flattened.v")
                    )
                    log_file = os.path.normpath(
                        os.path.join(
                            os.path.dirname(os.path.abspath(__file__)),
                            "log",
                            name + "_invalid.log",
                        )
                    )
                    process_netlist(file_path, output_file, None)

    else:
        print(f"{input_path} is not a valid file or directory.")


if __name__ == "__main__":
    """
    input_path and output_path use ABSOLUTE PATH. Could be a file or a directory.
    exclude_suffix_in_dir is the suffix of the file name to be excluded when input_path is a directory.
    """

    riscv_arg = {
        "input_path": "/home/zhujd/Project/syq_sp/spcal/demo/riscv/riscv.v",
        "output_path": "/home/zhujd/Project/syq_sp/spcal/demo/riscv/riscv_flattened.v",
        "exclude_suffix_in_dir": "_rtl",
    }

    main(**riscv_arg)
