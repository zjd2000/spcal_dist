"""
.title <name> //name写CDL上cell的name
.option post probe list //这一行固定
.include '.\7nfet.pm'   //这一行固定
.include '.\7pfet.pm'   //这一行固定
.GLOBAL VDD GND         //这一行固定
.TEMP 25.0              //这一行固定
.PARAM SUPPLY=0.7       //这一行固定

//////////////////////////////////////////////这一块是CDL文件里这一个cell的代码,从.SUBCKT到.ENDS为这一个cell//////////

.SUBCKT DFFASRHQNx1_ASAP7_75t_L CLK D SH MH MS SS RESETn SETn VDD_INST VSS_INST Y   ///不要直接抄过来,要在所有cell的VDD,VSS后面加一个“_INST”
MM20 clkb CLK VSS_INST VSS_INST nfet w=54.0n l=20n nfin=2
MM23 clkn clkb VSS_INST VSS_INST nfet w=54.0n l=20n nfin=2
.ENDS

////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


////////////////////////////////////////////这里例化一下这个cell,格式是:XFF 所有端口(VDD,VSS后面不用加_INST) NAME/////
XFF CLK D QN SH MH MS SS RESETn SETn VDD GND Y DFFASRHQNx1_ASAP7_75t_L
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////


///////////////////////////////////////////这部分是激励,先不管/////////////////////////////////////////////////////////////
V{X} {X} VDD GND PWL(0n 0V 399n 0V 400n SUPPLY)
/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////


////////////////////////////////////////这部分是固定的照抄即可////////////////////////////////////////////////////////
RY Y VSS 10k
VDD VDD GND SUPPLY
VSS VSS GND 0
.tran 1p 2000n
///////////////////////////////////////////////////////////////////////////////////////////////////////////////////

///////////////////////////////////////////这里的格式是： .probe V(...) V(...) V(...) ....括号里填所有节点()，填完为止
.probe V(SH) V(MH) V(MS) V(SS) V(CLK) V(D) V(RESETn) V(SETn) V(QN)
.end                //这行固定有
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////


///////////////////////这是上面的程序用的例子///////////////////////////////////////////////////////////////////////////
.SUBCKT A2O1A1Ixp33_ASAP7_75t_R A1 A2 B C VDD VSS Y
MM7 net06 B VSS VSS nmos_rvt w=81.0n l=20n nfin=3
MM2 Y C net06 VSS nmos_rvt w=81.0n l=20n nfin=3
MM1 net015 A2 VSS VSS nmos_rvt w=81.0n l=20n nfin=3
MM0 net06 A1 net015 VSS nmos_rvt w=81.0n l=20n nfin=3
MM6 Y C VDD VDD pmos_rvt w=54.0n l=20n nfin=2
MM5 Y B net2 VDD pmos_rvt w=81.0n l=20n nfin=3
MM4 net2 A2 VDD VDD pmos_rvt w=81.0n l=20n nfin=3
MM3 net2 A1 VDD VDD pmos_rvt w=81.0n l=20n nfin=3
.ENDS
"""

import ast
import json
import os
import re

import typer

base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../../../")
waveforms_dir = os.path.join(base_dir, "src/spcal/tools/gen_spice")


class spice_testbench:

    def __init__(self, cell):
        self.cell = cell
        self.cell_name = cell["type"]
        self.interfaces = cell["interfaces"]
        self.mos_transistors = cell["mos_transistors"]
        self.raw = cell["raw"]
        self.testbench = self.generate_testbench()

    def generate_testbench(self):

        part0 = f""".title {self.cell_name}
.option post probe list
.include '.\\7nfet.pm'
.include '.\\7pfet.pm'
.GLOBAL VDD GND
.TEMP 25.0
.PARAM SUPPLY=0.7"""

        part1 = "\n".join(
            [
                self.raw.splitlines()[0]
                .replace("VDD", "VDD_INST")
                .replace("VSS", "VSS_INST")
            ]
            + self.raw.splitlines()[1:]
        )

        part2 = f"""XFF """ + " ".join(self.interfaces) + f""" {self.cell_name}"""

        pattern = r"\.SUBCKT\s+\S+\s+([^VDD]+)"
        match = re.search(pattern, self.raw.splitlines()[0])

        if match:
            input_ports_str = match.group(1).strip()
            input_ports = input_ports_str.split()
        else:
            raise ValueError("Failed to extract input ports from .SUBCKT line")

        wave = self.generate_waveforms(len(input_ports))
        part3 = ""
        for i, p in enumerate(input_ports):
            part3 += f"V{p} {p} VDD GND PWL({wave.get(i)})\n\n"

        part3 = part3[:-2]

        part4 = f"""RY Y VSS 10k
VDD VDD GND SUPPLY
VSS VSS GND 0
.tran 1p 2000n"""

        nodes = set()
        nodes.update(
            transistor[key]
            for transistor in self.mos_transistors.values()
            for key in ["ND", "NS", "NG", "NB"]
            if key in transistor
        )
        part5 = (
            f""".probe """ + " ".join([f"V({node})" for node in nodes]) + f"""\n.end """
        )

        return "\n\n".join([part0, part1, part2, part3, part4, part5])

    def generate_waveforms(self, num_of_ports, cycle_ns=10, edge_ns=1):
        filename = f"waveforms_{num_of_ports}_portbyline.txt"
        filename = os.path.join(waveforms_dir, filename)

        if not os.path.exists(filename):
            raise FileNotFoundError(
                f"File {filename} NOT exists. RUN 'gen_waveforms.py' first"
            )

        with open(filename, "r") as f:
            lines = f.readlines()

        waveforms = []
        for i in range(num_of_ports):
            waveform = ast.literal_eval(lines[i].strip())
            waveforms.append(waveform)

        output = {}
        for port_idx, waveform in enumerate(waveforms):
            time = 0
            wave_str = ""
            for value in waveform:
                wave_str += f"{time}n {'0V' if value == 0 else 'SUPPLY'} "
                time += cycle_ns - edge_ns
                wave_str += f"{time}n {'0V' if value == 0 else 'SUPPLY'} "
                time += edge_ns

            output[port_idx] = wave_str[:-1]

        return output

    def write_testbench(self, output_path):
        with open(output_path, "w") as file:
            file.write(self.testbench)


def main(cdl_names, output_dir):
    count = 0
    for cdl in cdl_names:
        input_file_path = os.path.join(base_dir, "data/raw/cdl", cdl + ".cdl")
        with open(input_file_path, "r") as file:
            file_content = file.read()
            subckt_blocks = re.findall(r"(\.SUBCKT.*?\.ENDS)", file_content, re.DOTALL)
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

                testbench = spice_testbench(
                    {
                        "type": cell_type,
                        "interfaces": interfaces,
                        "mos_transistors": mos_transistors,
                        "raw": block,
                    }
                )

                testbench.write_testbench(os.path.join(output_dir, f"{cell_type}.sp"))

                count += 1

    typer.echo(
        typer.style(f"SUCCESS: Generated {count} testbenches.", fg=typer.colors.GREEN)
    )


if __name__ == "__main__":
    cdl_names = [
        "asap7sc7p5t_28_L",
        "asap7sc7p5t_28_R",
        "asap7sc7p5t_28_SL",
        "asap7sc7p5t_28_SRAM",
    ]

    test_names = ["custom_cdl"]

    output_dir = os.path.join(base_dir, "data/spice")

    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for cdl in cdl_names:
        raw_cdl_path = os.path.join(base_dir, "data/raw/cdl", cdl + ".cdl")
        if not os.path.exists(raw_cdl_path):
            typer.echo(
                typer.style(
                    f"\nERROR: File '{os.path.normpath(raw_cdl_path)}' not exists.",
                    fg=typer.colors.RED,
                )
            )
            typer.Exit(code=1)

    try:
        main(cdl_names, output_dir)
    except Exception as e:
        print(e)
