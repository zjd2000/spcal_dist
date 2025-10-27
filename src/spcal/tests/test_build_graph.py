# XXX: 20251026: need update
from unittest.mock import MagicMock, patch

import pytest
from networkx import DiGraph

from spcal.netlist_graph import NetlistGraph


class TestNetlistGraphBuildGraph:
    # XXX 20250622: need update
    @pytest.fixture
    def mock_netlist_dict(self):
        return {
            "cell1": MagicMock(
                cell_type="type1",
                input_wires={"in1": {"wire": "wire1"}, "in2": {"wire": "wire2"}},
                output_wires={"out1": {"wire": "wire3"}},
            ),
            "cell2": MagicMock(
                cell_type="type2",
                input_wires={"in1": {"wire": "wire3"}, "in2": {"wire": "wire4"}},
                output_wires={"out1": {"wire": "wire5"}},
            ),
            "cell3": MagicMock(
                cell_type="type3",
                input_wires={"in1": {"wire": "wire5"}},
                output_wires={"out1": {"wire": "wire1"}},  # 形成循环
            ),
        }

    @pytest.fixture
    def netlist_graph(self, mock_netlist_dict):
        with patch("spcal.NetlistGraph.load_functions", return_value={}):
            graph = NetlistGraph("lib_dir", {}, [])
            graph._NetlistGraph__netlist_dict = mock_netlist_dict
            return graph

    def test_build_graph_edges(self, netlist_graph):
        netlist_graph.build_graph()
        graph = netlist_graph._NetlistGraph__graph

        # 验证节点
        assert set(graph.nodes) == {"cell1", "cell2", "cell3"}

        # 验证边
        assert set(graph.edges) == {
            ("cell1", "cell2"),
            ("cell2", "cell3"),
            ("cell3", "cell1"),
        }
        assert graph["cell1"]["cell2"]["wire"] == "wire3"
        assert graph["cell2"]["cell3"]["wire"] == "wire5"
        assert graph["cell3"]["cell1"]["wire"] == "wire1"

    def test_build_graph_node_attributes(self, netlist_graph):
        netlist_graph.build_graph()
        graph = netlist_graph._NetlistGraph__graph

        # 验证节点属性
        assert graph.nodes["cell1"]["type"] == "type1"
        assert graph.nodes["cell1"]["input_wires"] == {
            "in1": {"wire": "wire1"},
            "in2": {"wire": "wire2"},
        }

    def test_build_graph_cycles(self, netlist_graph):
        netlist_graph.build_graph()
        cycles = netlist_graph._NetlistGraph__cycles

        # 验证循环
        assert len(cycles) == 1
        assert set(cycles[0]) == {"cell1", "cell2", "cell3"}

        # 验证循环边的标记
        graph = netlist_graph._NetlistGraph__graph
        assert graph["cell3"]["cell1"]["cycle_edge"] is True

    def test_build_graph_no_cycles(self, netlist_graph):
        # 修改 mock 数据移除循环
        netlist_graph._NetlistGraph__netlist_dict["cell3"].output_wires = {
            "out1": {"wire": "wire6"}
        }

        netlist_graph.build_graph()
        cycles = netlist_graph._NetlistGraph__cycles

        # 验证无循环
        assert len(cycles) == 0

    def test_build_graph_isolated_nodes(self, netlist_graph):
        # 添加孤立节点
        netlist_graph._NetlistGraph__netlist_dict["cell4"] = MagicMock(
            cell_type="type4", input_wires={}, output_wires={}
        )

        netlist_graph.build_graph()
        graph = netlist_graph._NetlistGraph__graph

        # 验证孤立节点存在但无边
        assert "cell4" in graph.nodes
        assert list(graph.edges("cell4")) == []
