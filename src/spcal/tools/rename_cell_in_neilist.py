import logging
import os
import pprint
import re

base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../")

logging.basicConfig(
    filename=os.path.join(base_dir, "src/spcal/tools/log/rename_cell.log"),
    filemode="w",
    level=logging.DEBUG,
    format="%(asctime)s %(name)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


def expand_bit_range(expression):
    match = re.match(r"(\w+)\[(\d+):(\d+)\]", expression)
    if match:
        base, high, low = match.groups()
        high, low = int(high), int(low)
        return [f"{base}[{i}]" for i in range(high, low - 1, -1)]
    return [expression]


def parse_external_replacement_rules(rule_string):
    rules = {}
    port_pattern = r"\.(\w+)\(([^)]+)\)"
    matches = re.findall(port_pattern, rule_string)

    for old_name, new_name in matches:
        if new_name.startswith("{") and new_name.endswith("}"):
            items = [item.strip() for item in new_name[1:-1].split(",")]
            expanded_items = []
            for item in items:
                expanded_items.extend(expand_bit_range(item))
            rules[old_name] = expanded_items
        else:
            expanded = expand_bit_range(new_name)
            rules[old_name] = expanded if len(expanded) > 1 else expanded[0]

    logger.debug("Parsed replacement rules:\n%s", pprint.pformat(rules))

    return rules


def extract_internal_wire_names(verilog_code, prefix):
    if isinstance(verilog_code, list):
        verilog_code = "".join(verilog_code)

    wire_declaration_match = re.search(r"(wire\s+)([\s\S]*?)(;)", verilog_code, re.S)
    if not wire_declaration_match:
        raise ValueError("No wire declaration found in the Verilog code.")
    header, wire_body, tail = wire_declaration_match.groups()
    wire_parts = re.split(r"(,)", wire_body)
    wire_dict = {}
    for i in range(0, len(wire_parts), 2):
        name = wire_parts[i].strip()
        if name:
            wire_dict[name] = f"{prefix}{name}"
            wire_parts[i] = wire_parts[i].replace(name, f"{prefix}{name}", 1)
    new_wire_declaration = header + "".join(wire_parts) + tail
    verilog_code = verilog_code.replace(
        wire_declaration_match.group(0), new_wire_declaration
    )
    logger.debug("Extracted and prefixed wire names: \n%s", pprint.pformat(wire_dict))

    return wire_dict, verilog_code


def apply_external_replacement(entry, rules):
    for old_name, new_name in rules.items():
        if isinstance(new_name, list):
            l = len(new_name)
            for i, name in enumerate(new_name):
                entry = re.sub(rf"\b{old_name}\b\[{l-i-1}\]", name, entry)
                logger.debug(f"Replace {old_name}[{l-i-1}] with {name}")
        else:
            entry = re.sub(rf"\b{old_name}\b", new_name, entry)
            logger.debug(f"Replace {old_name} with {new_name}")
    return entry


def rename_netlist_cells(entries, rules, wires, prefix):
    renamed_entries = []
    cell_pattern = r"(\s*)([A-Z]\S*)\s+(\S+)\s*\((.+)\);(\s*)"

    buffer = ""

    for line in entries:
        buffer += line
        if ";" in line:
            match = re.match(cell_pattern, buffer, re.S)
            if match:
                leading_spaces = match.group(1)
                cell_type = match.group(2)
                old_name = match.group(3)
                ports = match.group(4)
                trailing_spaces = match.group(5)

                port_pattern = r"\.(\w+)\(([^)]+)\)"
                for p, r in re.findall(port_pattern, ports):
                    if r in wires:
                        ports = ports.replace(r, f"{prefix}{r}")

                renamed_entry = f"{leading_spaces}{cell_type} {prefix}_{old_name} ({ports});{trailing_spaces}"
            else:
                renamed_entry = buffer
            renamed_entries.append(apply_external_replacement(renamed_entry, rules))
            buffer = ""
    if buffer.strip():
        renamed_entries.append(buffer)

    return renamed_entries


if __name__ == "__main__":

    input_file_name = "src/spcal/tools/FORWARDING.v"
    output_file_name = "src/spcal/tools/renamed_FORWARDING.v"
    # double underscore as prefix
    prefix = "FORWARDING__"

    rule_string = """ \
.EX_MEM_RegWrite(EX_MEM_RegWrite), 
.MEM_WB_RegWrite(MEM_WB_RegWrite), 
.MEM_WB_MemRead(MEM_WB_MemRead), 
.EX_MEM_rd(EX_MEM_rd), 
.MEM_WB_rd({n36, n34, n52, n33, n12}), 
.ID_EX_rs1({ID_EX_rs1[4:3], n59, n62, n66}), 
.ID_EX_rs2({ID_EX_rs2[4:3], n60, n53, n57}), 
.forwarding_EX_MEM_in(EX_MEM_ALU_result), 
.forwarding_MEM_WB_ALU_in(MEM_WB_ALU_result), 
.forwarding_MEM_WB_MEM_in({MEM_WB_mem_data[31:20], n24, MEM_WB_mem_data[18:14], n5, MEM_WB_mem_data[12:0]}), 
.forwarding_EX_MEM_out(forwarding_EX_MEM), 
.forwarding_MEM_WB_out(forwarding_MEM_WB), 
.ForwardA(ForwardA), 
.ForwardB(ForwardB)
"""

    replacement_rules = parse_external_replacement_rules(rule_string)

    with open(os.path.join(base_dir, input_file_name), "r") as file:
        netlist_entries = file.readlines()

    internal_wires, netlist_entries = extract_internal_wire_names(
        netlist_entries, prefix
    )

    renamed_netlist = rename_netlist_cells(
        netlist_entries, replacement_rules, internal_wires, prefix
    )

    with open(os.path.join(base_dir, output_file_name), "w") as file:
        file.write("".join(renamed_netlist))

    print(
        f"Renamed netlist written to {os.path.normpath(os.path.join(base_dir, output_file_name))}"
    )
