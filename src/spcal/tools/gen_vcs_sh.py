def generate_script(names, output_file="generated_scripts.sh"):
    lib_files = [
        "/mnt/mydata/asap7sc7p5t_SEQ_RVT_TT_220101.v",
        "/mnt/mydata/asap7sc7p5t_SIMPLE_RVT_TT_201020.v",
        "/mnt/mydata/asap7sc7p5t_OA_RVT_TT_201020.v",
        "/mnt/mydata/asap7sc7p5t_INVBUF_RVT_TT_201020.v",
        "/mnt/mydata/asap7sc7p5t_AO_RVT_TT_201020.v",
    ]

    base_command = "vcs -R \\"

    with open(output_file, "w") as f:
        for name in names:
            file_params = " ".join([f"-v {file}" for file in lib_files])
            command = f"(time {base_command} {file_params} /mnt/mydata/{name}/{name}_tb.v /mnt/mydata/{name}/{name}.v) 2>&1 | tee /mnt/mydata/outputs/{name}_output.log"
            f.write(command + "\n")

    print(f"Done")


# 输入的name列表
names = [
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

generate_script(names, "generated_scripts.sh")
