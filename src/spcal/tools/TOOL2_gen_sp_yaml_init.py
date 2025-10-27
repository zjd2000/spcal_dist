import os

import regex as re
import typer
import yaml


def extract_inputs_from_verilog(verilog_file):
    with open(verilog_file, "r", encoding="utf-8") as f:
        content = f.read()

    input_match = re.search(r"input\s+([^;]+);\s*output", content, re.DOTALL)
    if not input_match:
        return []

    inputs = re.split(r"[\s,]+", input_match.group(1).strip())
    return [i for i in inputs if i]


def parse_saif(saif_file, inputs):
    with open(saif_file, "r") as f:
        content = f.read()

    net_pattern = r"\(NET(?:[^()]*|\((?:[^()]*|\([^()]*\))*\))*\)"

    try:
        net_content = re.findall(net_pattern, content)
        if isinstance(net_content, list):
            net_content = " ".join(net_content)
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
            saif_data[node_name] = 0.5

    return {inp: saif_data.get(inp, 0.5) for inp in inputs}


def generate_yaml(yaml_file, verilog_file, saif_file, libs, port_prefixes):
    inputs = extract_inputs_from_verilog(verilog_file)
    warning_message = None

    if saif_file and os.path.exists(saif_file):
        external_sp_inputs_spec = parse_saif(saif_file, inputs)
    else:
        warning_message = f"Warning: SAIF file '{saif_file}' not found. Init as 0.5."
        typer.echo(typer.style(warning_message, fg=typer.colors.YELLOW))
        external_sp_inputs_spec = {inp: 0.5 for inp in inputs}

    yaml_data = {
        "libs": libs,
        "port_prefixes": port_prefixes,
        "external_sp_inputs_spec": external_sp_inputs_spec,
    }

    with open(yaml_file, "w", encoding="utf-8") as f:
        if warning_message:
            f.write(f"# {warning_message}\n")
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)


def main(yaml_file, verilog_file, saif_file):
    libs = [
        "asap7sc7p5t_SIMPLE_RVT_TT_nldm_211120",
        "asap7sc7p5t_AO_RVT_TT_nldm_211120",
        "asap7sc7p5t_INVBUF_RVT_TT_nldm_220122",
        "asap7sc7p5t_OA_RVT_TT_nldm_211120",
        "asap7sc7p5t_SEQ_RVT_TT_nldm_220123",
        "manual",
    ]
    port_prefixes = {
        "input": [".A", ".B", ".C", ".D", ".E", ".CI", ".H"],
        "output": [".Y", ".QN", ".L", ".SN", ".CON"],
    }

    generate_yaml(yaml_file, verilog_file, saif_file, libs, port_prefixes)


if __name__ == "__main__":

    riscv_arg = {
        "yaml_file": "/home/zhujd/Project/syq_sp/spcal/demo/riscv/riscv.yaml",
        "verilog_file": "/home/zhujd/Project/syq_sp/spcal/demo/riscv/riscv_flattened.v",
        "saif_file": None,
    }

    try:
        main(**riscv_arg)
        typer.echo(typer.style(f"{riscv_arg['yaml_file']} Done", fg=typer.colors.GREEN))
    except Exception as e:
        typer.echo(
            typer.style(
                f"Error processing {riscv_arg['yaml_file']}: {e}", fg=typer.colors.RED
            )
        )
