# PIC3

安装注意事项：
1.由于作者在测试代码时是在上级文件夹测试的，当前文件夹命名为IC3，所以main.py里filepath = "./IC3/test.aig"。如果用户在当前文件夹测试，此处可以选择把/IC3删掉或者打开filepath = args[0]这一句然后通过输入路径来测试
2.Class.py里动态库的路径也需要做出相应的修改，160行 lib_path = os.path.abspath("./IC3/libminisat_wrapper.so") 中根据运行路劲进行调整
3.如果需要重新编译动态库，minisat_c_wrapper.cpp文件最下面有编译命令g++ -shared -fPIC -o ./IC3/libminisat_wrapper.so ./IC3/minisat_c_wrapper.cpp  ./IC3/minisat/minisat/simp/SimpSolver.cc ./IC3/minisat/minisat/utils/System.cc ./IC3/minisat/minisat/core/Solver.cc  -I ./IC3/minisat -lstdc++，同样，根据实际路径进行调整
