/////////////////////////////////////////////////////////////
// Created by: Synopsys DC Expert(TM) in wire load mode
// Version   : O-2018.06-SP1
// Date      : Tue Nov  5 11:38:49 2024
/////////////////////////////////////////////////////////////


module add_6_cla ( a, b, c_in, clk, rst_n, sum, c_out );
  input [5:0] a;
  input [5:0] b;
  output [5:0] sum;
  input c_in, clk, rst_n;
  output c_out;
  wire   N6, n48, n49, n50, n55, n56, n57, n58, n59, n60, n61, n62, n63, n64,
         n65, n66, n67, n68, n69, n70, n71, n72, n73, n74, n75, n76, n77, n78,
         n79, n80, n81, n82, n83, n84, n85, n86, n87, n88, n89, n90, n91, n92,
         n93, n94, n95, n96, n97, n98, n99, n100, n101, n102, n103, n104, n105,
         n106, n107, n108, n109, n110, n111, n112, n113, n114, n115, n116,
         n117, n118, n119, n120, n121, n122, n123, n124, n125, n126, n127,
         n128, n129, n130, n131, n132, n133, n134, n135;

  INVx1_ASAP7_75t_R U36 ( .A(rst_n), .Y(N6) );
  \**FFGEN**  c_out_reg ( .next_state(n131), .clocked_on(clk), .force_00(n132), 
        .force_01(N6), .force_10(n132), .force_11(n132), .Q(c_out) );
  \**FFGEN**  sum_reg_5_ ( .next_state(n133), .clocked_on(clk), .force_00(n132), .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[5]) );
  \**FFGEN**  sum_reg_4_ ( .next_state(n134), .clocked_on(clk), .force_00(n132), .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[4]) );
  \**FFGEN**  sum_reg_3_ ( .next_state(n135), .clocked_on(clk), .force_00(n132), .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[3]) );
  \**FFGEN**  sum_reg_2_ ( .next_state(n50), .clocked_on(clk), .force_00(n132), 
        .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[2]) );
  \**FFGEN**  sum_reg_1_ ( .next_state(n49), .clocked_on(clk), .force_00(n132), 
        .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[1]) );
  \**FFGEN**  sum_reg_0_ ( .next_state(n48), .clocked_on(clk), .force_00(n132), 
        .force_01(N6), .force_10(n132), .force_11(n132), .Q(sum[0]) );
  INVx1_ASAP7_75t_R U58 ( .A(n88), .Y(n90) );
  INVx6_ASAP7_75t_R U59 ( .A(c_in), .Y(n75) );
  INVx6_ASAP7_75t_R U60 ( .A(c_in), .Y(n99) );
  OR2x2_ASAP7_75t_R U61 ( .A(n65), .B(n77), .Y(n104) );
  INVx2_ASAP7_75t_R U62 ( .A(n70), .Y(n72) );
  BUFx3_ASAP7_75t_R U63 ( .A(n92), .Y(n70) );
  CKINVDCx10_ASAP7_75t_R U64 ( .A(a[2]), .Y(n98) );
  INVx1_ASAP7_75t_R U65 ( .A(n130), .Y(n68) );
  AND2x2_ASAP7_75t_R U66 ( .A(n67), .B(n107), .Y(n108) );
  NAND3xp33_ASAP7_75t_R U67 ( .A(n108), .B(n104), .C(n85), .Y(n109) );
  INVx2_ASAP7_75t_R U68 ( .A(n64), .Y(n65) );
  INVx2_ASAP7_75t_R U69 ( .A(n81), .Y(n56) );
  INVx6_ASAP7_75t_R U70 ( .A(n77), .Y(n55) );
  AND2x6_ASAP7_75t_R U71 ( .A(b[1]), .B(a[1]), .Y(n77) );
  AND2x4_ASAP7_75t_R U72 ( .A(n55), .B(n64), .Y(n81) );
  NAND2x1p5_ASAP7_75t_R U73 ( .A(n55), .B(n128), .Y(n97) );
  OR2x6_ASAP7_75t_R U74 ( .A(n64), .B(n63), .Y(n128) );
  BUFx6f_ASAP7_75t_R U75 ( .A(n74), .Y(n67) );
  AND2x2_ASAP7_75t_R U76 ( .A(n66), .B(n55), .Y(n62) );
  INVx2_ASAP7_75t_R U77 ( .A(n67), .Y(n103) );
  INVx1_ASAP7_75t_R U78 ( .A(n106), .Y(n69) );
  OR3x1_ASAP7_75t_R U79 ( .A(n67), .B(n82), .C(n78), .Y(n106) );
  AND3x1_ASAP7_75t_R U80 ( .A(n59), .B(n60), .C(n58), .Y(n57) );
  NAND3xp33_ASAP7_75t_R U81 ( .A(n82), .B(n107), .C(n67), .Y(n58) );
  OR2x2_ASAP7_75t_R U82 ( .A(n80), .B(n103), .Y(n59) );
  OR2x2_ASAP7_75t_R U83 ( .A(n67), .B(n107), .Y(n60) );
  AND2x2_ASAP7_75t_R U84 ( .A(n127), .B(n62), .Y(n61) );
  AND2x2_ASAP7_75t_R U85 ( .A(n80), .B(n91), .Y(n127) );
  AND2x4_ASAP7_75t_R U86 ( .A(n75), .B(n96), .Y(n63) );
  NAND2x2_ASAP7_75t_R U87 ( .A(b[2]), .B(a[2]), .Y(n91) );
  BUFx6f_ASAP7_75t_R U88 ( .A(n73), .Y(n64) );
  OR2x2_ASAP7_75t_R U89 ( .A(n95), .B(n94), .Y(n73) );
  BUFx6f_ASAP7_75t_R U90 ( .A(n79), .Y(n66) );
  NAND2x2_ASAP7_75t_R U91 ( .A(b[4]), .B(a[4]), .Y(n79) );
  NAND2x2_ASAP7_75t_R U92 ( .A(b[0]), .B(a[0]), .Y(n96) );
  NAND2x2_ASAP7_75t_R U93 ( .A(b[3]), .B(a[3]), .Y(n80) );
  OR2x2_ASAP7_75t_R U94 ( .A(n126), .B(n90), .Y(n130) );
  NOR2x1_ASAP7_75t_R U95 ( .A(n71), .B(n83), .Y(n126) );
  MAJx2_ASAP7_75t_R U96 ( .A(b[0]), .B(a[0]), .C(c_in), .Y(n92) );
  BUFx3_ASAP7_75t_R U97 ( .A(n121), .Y(n71) );
  XOR2x2_ASAP7_75t_R U98 ( .A(n84), .B(n102), .Y(n135) );
  XOR2x2_ASAP7_75t_R U99 ( .A(n119), .B(n120), .Y(n133) );
  NAND2xp5_ASAP7_75t_R U100 ( .A(n69), .B(n105), .Y(n110) );
  NAND2xp5_ASAP7_75t_R U101 ( .A(n85), .B(n104), .Y(n105) );
  XNOR2x2_ASAP7_75t_R U102 ( .A(b[4]), .B(a[4]), .Y(n74) );
  NAND2xp5_ASAP7_75t_R U103 ( .A(n61), .B(n128), .Y(n118) );
  XOR2x2_ASAP7_75t_R U104 ( .A(n93), .B(n72), .Y(n49) );
  NAND2xp5_ASAP7_75t_R U105 ( .A(n66), .B(n71), .Y(n117) );
  INVx8_ASAP7_75t_R U106 ( .A(c_in), .Y(n76) );
  AND2x4_ASAP7_75t_R U107 ( .A(b[3]), .B(a[3]), .Y(n78) );
  INVx6_ASAP7_75t_R U108 ( .A(a[2]), .Y(n114) );
  NOR2x2_ASAP7_75t_R U109 ( .A(b[3]), .B(a[3]), .Y(n111) );
  NAND2x1p5_ASAP7_75t_R U110 ( .A(b[5]), .B(a[5]), .Y(n124) );
  NOR2x2_ASAP7_75t_R U111 ( .A(b[4]), .B(a[4]), .Y(n112) );
  NOR2xp67_ASAP7_75t_R U112 ( .A(n112), .B(n111), .Y(n116) );
  AND2x4_ASAP7_75t_R U113 ( .A(b[2]), .B(a[2]), .Y(n82) );
  OR2x6_ASAP7_75t_R U114 ( .A(b[3]), .B(a[3]), .Y(n107) );
  AND2x4_ASAP7_75t_R U115 ( .A(n86), .B(n87), .Y(n83) );
  CKINVDCx16_ASAP7_75t_R U116 ( .A(b[5]), .Y(n86) );
  CKINVDCx16_ASAP7_75t_R U117 ( .A(a[5]), .Y(n87) );
  XNOR2x2_ASAP7_75t_R U118 ( .A(b[5]), .B(a[5]), .Y(n120) );
  XOR2x2_ASAP7_75t_R U119 ( .A(b[3]), .B(a[3]), .Y(n102) );
  XNOR2x2_ASAP7_75t_R U120 ( .A(b[1]), .B(a[1]), .Y(n93) );
  TIELOx1_ASAP7_75t_R U121 ( .L(n132) );
  NAND2xp5_ASAP7_75t_R U122 ( .A(n91), .B(n89), .Y(n84) );
  AND2x2_ASAP7_75t_R U123 ( .A(n100), .B(n101), .Y(n85) );
  NAND2x1p5_ASAP7_75t_R U124 ( .A(n86), .B(n87), .Y(n122) );
  AND2x2_ASAP7_75t_R U125 ( .A(n125), .B(n124), .Y(n88) );
  NAND2xp5_ASAP7_75t_R U126 ( .A(n56), .B(n85), .Y(n89) );
  NOR2xp33_ASAP7_75t_R U127 ( .A(n68), .B(n129), .Y(n131) );
  NOR2x2_ASAP7_75t_R U128 ( .A(a[0]), .B(b[0]), .Y(n94) );
  NOR2x2_ASAP7_75t_R U129 ( .A(a[1]), .B(b[1]), .Y(n95) );
  FAx1_ASAP7_75t_R U130 ( .A(b[0]), .B(a[0]), .CI(n76), .SN(n48) );
  FAx1_ASAP7_75t_R U131 ( .A(b[2]), .B(n98), .CI(n97), .SN(n50) );
  OR2x2_ASAP7_75t_R U132 ( .A(b[2]), .B(a[2]), .Y(n101) );
  NAND3xp33_ASAP7_75t_R U133 ( .A(n99), .B(n55), .C(n96), .Y(n100) );
  NAND3xp33_ASAP7_75t_R U134 ( .A(n109), .B(n110), .C(n57), .Y(n134) );
  INVx2_ASAP7_75t_R U135 ( .A(b[2]), .Y(n113) );
  NAND3xp33_ASAP7_75t_R U136 ( .A(n114), .B(n113), .C(n80), .Y(n115) );
  NAND2xp5_ASAP7_75t_R U137 ( .A(n116), .B(n115), .Y(n121) );
  NAND2xp5_ASAP7_75t_R U138 ( .A(n117), .B(n118), .Y(n119) );
  INVx2_ASAP7_75t_R U139 ( .A(n66), .Y(n123) );
  NAND2xp5_ASAP7_75t_R U140 ( .A(n123), .B(n122), .Y(n125) );
  AND4x1_ASAP7_75t_R U141 ( .A(n55), .B(n88), .C(n127), .D(n128), .Y(n129) );
endmodule

