/////////////////////////////////////////////////////////////
// Created by: Synopsys DC Expert(TM) in wire load mode
// Version   : O-2018.06-SP1
// Date      : Fri Feb  7 23:11:29 2025
/////////////////////////////////////////////////////////////


module c17 ( N1, N2, N3, N6, N7, N22, N23 );
  input N1, N2, N3, N6, N7;
  output N22, N23;
  wire   n2;

  NAND2x1p5_ASAP7_75t_R U4 ( .A(N6), .B(N3), .Y(n2) );
  OA21x2_ASAP7_75t_R U5 ( .A1(N2), .A2(N7), .B(n2), .Y(N23) );
  AO22x1_ASAP7_75t_R U6 ( .A1(N1), .A2(N3), .B1(n2), .B2(N2), .Y(N22) );
endmodule

