# spcal 使用说明

## 1 下载代码

您可以通过压缩包 `spcal_dist.zip` 下获取代码。

请确保同时获得了spcal_data 压缩包，用于存放spcal运行时所需的lib文件。放在项目根目录下面

## 2 安装环境

### 2.1 安装 uv

uv 是一个 Python 包管理器，用于安装和管理 Python 项目的依赖项。它可以帮助您快速、方便地安装和更新项目所需的所有依赖项。

linux(WLS2) 下安装 uv 可以通过以下命令：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

其他平台的安装参考 [uv 安装文档](https://docs.astral.sh/uv/getting-started/installation/)

### 2.2 安装 spcal

首先，您需要联系管理员拿到一个最新的spcal wheel包，比如 `spcal-0.9.1-py3-none-any.whl`

然后，执行

```bash
uv add spcal-0.9.1-py3-none-any.whl
```

### 2.3 安装依赖项

您可以通过以下命令安装项目所需的所有依赖项：

```bash
uv sync
```

### 3 运行 spcal

您可以通过以下命令运行 spcal：

```bash
uv run main.py
```

默认是运行demo中的示例代码。您可以根据需要修改main.py中的代码。

### 4 参数说明

参数形如：    
```python
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
```
其中：
- cell_name： 待计算的cell名称，可以是多个cell，比如 ["bl16_U2", "bl16_U3"]
- data_dir： spcal_data 压缩包解压后的目录
- netlist： 待计算的cell的netlist文件路径
- config： 待计算的cell的配置文件路径
- bdd_backend： BDD后端，可选值为 "autoref" 和 "pybdd"
- visual： 是否可视化结果，可选值为 "True" 和 "False"
- output_dir： 输出目录，用于存放计算结果
- bdd_dump_path： BDD dump 文件路径，用于存放BDD可视化结果
- bdd_dump_format： BDD dump 文件格式，可选值为 "dag" 和 "expr"
- overwrite： 是否覆盖输出目录下的文件，可选值为 "True" 和 "False"

### 5 更新spcal

先卸载旧版本的spcal：
```bash
uv remove spcal
```

然后，安装新版本的spcal：
```bash
uv add spcal-0.9.1-py3-none-any.whl
```