# spcal

## Overview

The spcal system is a comprehensive Python-based toolchain for calculating signal probabilities (SP) and analyzing CMOS circuits in electronic design automation (EDA) workflows. This system processes various netlist formats, standard cell libraries, and switching activity data to perform static probability analysis and CMOS circuit characterization.

This document provides a high-level overview of the spcal architecture, core components, and primary capabilities. For detailed usage instructions, see Getting Started. For in-depth technical documentation of specific analysis methods, see Core Analysis Features. For data format specifications and processing workflows, see Data Processing Pipeline.

## Quick Start

To get started with spcal, follow these steps:

1. Clone the spcal repository:

You may use Access Token to clone the repository as long as this project is private.

```bash
git clone https://{ACCESS_TOKEN}@github.com/bytedance/spcal.git
cd spcal
```

2. Install the required dependencies using uv:

If you have any issues, please refer to the uv documentation.

https://github.com/astral-sh/uv

```bash
# On Linux.
curl -LsSf https://astral.sh/uv/install.sh | sh
```

```bash
# On macOS.
brew install uv
```

```bash
# On Windows.
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

3. Install uv virtual environment:

```bash
uv sync
```

4. Run spcal:

```bash
uv run src/spcal/main.py
```

5. use spcal\_data

Do not commit your plaintext token in .gitmodule as spcal\_data is a privaet repo.

Use instructions above instead.

```bash
git config submodule.spcal_data.url https://<token>@github.com/sunyaqi123/spcal_data.git
```

### High-Level System Components

![image](https://github.com/user-attachments/assets/66424518-d0ee-40e3-a800-c1186458cdfd)

### Core Data Flow and Processing Pipeline
The system processes electronic design data through a structured pipeline that transforms raw netlist and library files into probability analysis results and visualizations.

![image](https://github.com/user-attachments/assets/972018fb-ccb9-4a64-9ffc-8fed1f766197)

## Core Components

### Command Line Interface

The system provides two primary entry points defined in the uv configuration:

## Core Components

### Command Line Interface

The system provides two primary entry points defined in the uv configuration:

| Command | Entry Point               | Purpose                                       |
|---------|---------------------------|-----------------------------------------------|
| `sp`    | `spcal.main:sp_main`      | Static probability analysis of specified cells |
| `cmos`  | `spcal.main:cmos_main`    | CMOS circuit analysis and BTI computation      |


## Key Dependencies and Technologies

The spcal system leverages several specialized libraries for electronic design analysis:

| Library      | Version   | Purpose                                                                 |
|--------------|-----------|-------------------------------------------------------------------------|
| `networkx`   | `^3.4.2`  | Graph-based netlist representation and analysis                         |
| `dd`         | `^0.6.0`  | Binary Decision Diagram (BDD) operations for exact probability calculation |
| `scipy`      | `^1.15.1` | Scientific computing and numerical analysis                             |
| `matplotlib` | `^3.9.2`  | Static plotting and visualization                                       |
| `plotly`     | `^5.24.1` | Interactive visualizations and dashboards                               |
| `schemdraw`  | `^0.19`   | Circuit diagram generation                                              |
| `graphviz`   | `^0.20.3` | Graph visualization and layout                                          |
| `typer`      |	^0.13.0	| Command-line interface framework  |
| `pyyaml`	| ^6.0.2	| Configuration file parsing |

### Analysis Capabilities

The spcal system provides two main analysis modes:

  1. Static Probability (SP) Analysis: Computes signal transition probabilities using graph-based propagation algorithms with support for both exact BDD-based and approximate Monte Carlo estimation methods

  2. CMOS Circuit Analysis: Performs transistor-level analysis including Bias Temperature Instability (BTI) computation and power/performance characterization

For detailed information about these analysis capabilities, see Static Probability (SP) Analysis and CMOS Circuit Analysis.

## Key Features

### Multi-Format Data Support

- Netlist Formats: CDL (Circuit Description Language), LIB (Liberty format), Verilog
- Activity Data: SAIF (Switching Activity Interchange Format) files
- Configuration: YAML-based configuration system with library specifications

### Advanced Probability Estimation

- Exact Methods: Binary Decision Diagram (BDD) based computation for precise results
- Approximate Methods: Monte Carlo simulation for complex circuits with performance optimization
- Graph Algorithms: NetworkX-based topological analysis and signal propagation

### Comprehensive Visualization

- Static Plots: matplotlib-based charts and graphs for analysis results
- Interactive Dashboards: plotly-based interactive visualizations with zoom and filtering
- Circuit Diagrams: schemdraw integration for generating circuit schematics
- Graph Layouts: graphviz-powered network topology visualization

### Standard Cell Library Integration

- ASAP7 Support: Built-in support for ASAP7 standard cell libraries
- JSON Representation: Efficient library storage and access in JSON format
- Configurable Libraries: Extensible library system for additional standard cell sets

README is Written by DeepWiKi
https://deepwiki.com/sunyaqi123/spcal
Developed with ❤️ by SYQ
