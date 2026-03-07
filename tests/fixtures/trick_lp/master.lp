\ Trick "A Consultant's Guide to Solving Large Problems" DW example
\ Master file: global objective + two coupling constraints
Minimize
 obj: - 7 x1 - 5 x2 - 3 x3

Subject To
 Con1: x1 + 2 x2 + x3 <= 10
 Con2: x1 <= 3

End
