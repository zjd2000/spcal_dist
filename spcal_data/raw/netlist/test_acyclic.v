module test_0623(clk, N1, N2, N3, N6, N7, N22, N23);
    input N1, N2, N3, N6, N7, clk;
    output N22, N23;
    wire N1, N2, N3, N6, N7;
    wire N22, N23;
    wire N10, N11,N11_QN, N16, N19;
    nand NAND2_1 (N10, N1, N3);
    nand NAND2_2 (N11, N22, N6);
    nand NAND2_3 (N16, N2, N11_QN);
    nand NAND2_4 (N19, N11_QN, N7);
    nand NAND2_5 (N22, N10, N16);
    nand NAND2_6 (N23, N16, N19);
    DFFASRHQNx1_ASAP7_75t_R register_dff ( .D(N11), .CLK(clk), .SETN(1'b1), .RESETN(1'b1), .QN(N11_QN) );

endmodule
