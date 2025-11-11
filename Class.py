import subprocess
import os
import tempfile
from typing import List, Dict, Set, Optional
import ctypes


state_count = 0
# class CNFFormula:
#     """CNF公式类，用于存储子句并与minisat交互"""
    
#     def __init__(self):
#         self.clauses = []  # 存储子句的列表，每个子句是一个整数列表
#         self.var_count = 0  # 变量数量
        
#     def add_clause(self, clause):

#         """
#         向CNF公式添加一个子句
        
#         参数:
#             clause: 整数列表，每个整数表示一个文字(变量或其否定)
#                     正数表示变量本身，负数表示变量的否定
#         """
#         if not isinstance(clause, list):
#             raise ValueError("子句必须是一个整数列表")
        
#         if clause == [None]:
#             return
        
        
#         # 检查子句中的变量是否有效并更新变量计数
#         for lit in clause:
#             if not isinstance(lit, int) or lit == 0:
#                 print(lit)
#                 raise ValueError("子句中的文字必须是非零整数")
            
#             var = abs(lit)
#             if var > self.var_count:
#                 self.var_count = var
                
#         self.clauses.append(clause)
    
#     def save_to_cnf(self, filename):
#         """
#         将CNF公式保存为DIMACS CNF格式文件
        
#         参数:
#             filename: 保存的文件名
#         """
#         with open(filename, 'w') as f:
#             # 写入问题描述行：p cnf 变量数 子句数
#             f.write(f"p cnf {self.var_count} {len(self.clauses)}\n")
            
#             # 写入每个子句，每个子句以0结尾
#             for clause in self.clauses:
#                 clause_str = ' '.join(map(str, clause)) + ' 0\n'
#                 f.write(clause_str)
    
#     def solve(self,):

#         base_dir = os.path.dirname(os.path.abspath(__file__))
#         minisat_path = os.path.join(base_dir, "bin", "minisat")

#         with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as cnf_file, \
#              tempfile.NamedTemporaryFile(mode='r', suffix='.txt', delete=False) as result_file:
            
#             cnf_filename = cnf_file.name
#             result_filename = result_file.name
#             result_filename = "result_file.txt"
        
#         try:

#             self.save_to_cnf(cnf_filename)
            
#             # 调用minisat求解器
#             result = subprocess.run(
#                 [minisat_path, cnf_filename, result_filename],
#                 capture_output=True,
#                 text=True
#             )
            
#             # 检查是否运行成功
#             # minisat返回码：0=正常，10=SAT，20=UNSAT
#             if result.returncode not in [0, 10, 20]:
#                 raise RuntimeError(f"Minisat运行失败: {result.stderr}")
            
#             # 读取并解析结果
#             # with open(result_filename, 'r') as f:
#             #     first_line = f.readline().strip()
#             #     if first_line == 'SAT':
#             #         return 'SAT'
#             #     elif first_line == 'UNSAT':
#             #         return 'UNSAT'
#             #     else:
#             #         raise ValueError(f"无法解析Minisat结果: {first_line}")
                
                
#             with open(result_filename, 'r') as f:
#                 lines = [line.strip() for line in f.readlines() if line.strip()]

#             if not lines:
#                 return 'ERROR', None  # 输出文件为空

#             first_line = lines[0].upper()
#             if first_line == 'SAT':
#                 # 解析变量赋值（第二行，格式如"1 -2 3 0"）
#                 model = {}
#                 if len(lines) >= 2:
#                     assignment_line = lines[1]
#                     for lit_str in assignment_line.split():
#                         try:
#                             lit = int(lit_str)
#                         except ValueError:
#                             continue  # 跳过非整数内容
#                         if lit == 0:
#                             break  # 赋值以0结尾
#                         var = abs(lit)
#                         model[var] = 1 if lit > 0 else -1  # 1=真，-1=假
#                 return 'SAT', model

#             elif first_line == 'UNSAT':
#                 return 'UNSAT', None

#             else:
#                 return 'ERROR', None
                    
#         finally:
#             pass
#             # 清理临时文件
#             if os.path.exists(cnf_filename):
#                 os.remove(cnf_filename)
#             # if os.path.exists(result_filename):
#             #     os.remove(result_filename)

class Variable:
    def __init__(self, dimacs_index, name = "", type = "", type_index = 0, prime = 0):
        self.dimacs_var = dimacs_index
        self.name = name
        if type in ['i', 'o', 'l', 'a']:
            # 更新type属性为合法类型
            self.name = type 
            s = f"{type}{str(type_index)}"  
            if prime == 1:
                s += "'"  
            self.name = s 


class SATSolver:
    
    def __init__(self):
        # MiniSat C++ 封装后端
        self.clauses = []
        self.current_clause = []
        self.assumptions = []
        self.max_variable = 0
        self.simplified_cnf = []
        try:
            # 使用绝对路径加载（避免相对路径陷阱）
            lib_path = os.path.abspath("./IC3/libminisat_wrapper.so")
            self.lib = ctypes.CDLL(lib_path)
            self._setup_lib_functions()
            self.solver = self.lib.minisat_create()
            self.backend = "minisat"
        except Exception as e:
            # 打印详细错误（如文件不存在、符号缺失等）
            print(f"初始化错误：{str(e)}")
            # 可选：如果加载失败，终止程序（避免后续错误）
            raise  # 抛出异常，停止执行
        
        # 通用常量
        self.SAT = 1
        self.UNSAT = 0
        self.UNKNOWN = -1
        
        # 状态变量
        self.solve_result = self.UNKNOWN
        self.var_values = {}
        self.failed_assumptions = []
        self.clear_flag = False
    
    def _setup_lib_functions(self):
        """设置 C++ 库函数原型"""
        self.lib.minisat_create.restype = ctypes.c_void_p
        self.lib.minisat_destroy.argtypes = [ctypes.c_void_p]
        self.lib.minisat_add_clause.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        self.lib.minisat_add_clause.restype = ctypes.c_bool
        self.lib.minisat_solve.argtypes = [ctypes.c_void_p, ctypes.c_bool]
        self.lib.minisat_solve.restype = ctypes.c_int
        self.lib.minisat_set_assumptions.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        self.lib.minisat_model_value.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.minisat_model_value.restype = ctypes.c_int
        self.lib.minisat_max_var.argtypes = [ctypes.c_void_p]
        self.lib.minisat_max_var.restype = ctypes.c_int
        self.lib.minisat_clear_assumptions.argtypes = [ctypes.c_void_p]
        self.lib.minisat_get_failed_assumptions.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        self.lib.minisat_get_failed_assumptions.restype = ctypes.POINTER(ctypes.c_int)
        self.lib.minisat_var_enlarge_to.argtypes = [ctypes.c_void_p, ctypes.c_int]
        self.lib.minisat_var_enlarge_to.restype = None
        self.lib.minisat_simplify.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        self.lib.minisat_simplify.restype = ctypes.POINTER(ctypes.c_int)
        self.lib.minisat_free_simplified_cnf.argtypes = [ctypes.POINTER(ctypes.c_int)]
        self.lib.minisat_free_simplified_cnf.restype = None
        self.lib.minisat_perform_simplify.argtypes = [ctypes.c_void_p]
        self.lib.minisat_perform_simplify.restype = None
        self.lib.minisat_get_raw_cnf.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)]
        self.lib.minisat_get_raw_cnf.restype = ctypes.POINTER(ctypes.c_int)
    # def _setup_python_backend(self):
    #     """设置纯 Python 后端"""
    #     self.clauses = []
    #     self.current_clause = []
    #     self.assumptions = []
    #     self.max_variable = 0
    
    def __del__(self):
        """析构函数"""
        if hasattr(self, 'solver') and self.solver and self.backend == "minisat":
            self.lib.minisat_destroy(self.solver)
    
    def simplify(self) -> List[int]:

        if self.backend != "minisat":
            print("Warning: simplify only supported for minisat backend")
            return []
        
        # 调用 C++ 后端的简化函数
        out_size = ctypes.c_int()
        simplified_ptr = self.lib.minisat_simplify(self.solver, ctypes.byref(out_size))
        
        # 将结果转换为 Python 列表
        self.simplified_cnf = []
        if out_size.value > 0:
            self.simplified_cnf = [simplified_ptr[i] for i in range(out_size.value)]
            
            # 释放 C++ 端分配的内存
            self.lib.minisat_free_simplified_cnf(simplified_ptr)
        
        return self.simplified_cnf
    
    def perform_simplify(self) -> None:
        """
        仅执行简化，不获取简化后的 CNF（性能更好）
        适用于只需要简化效果而不需要获取具体 CNF 的场景
        """
        if self.backend == "minisat":
            self.lib.minisat_perform_simplify(self.solver)
    
    def get_simplified_cnf(self) -> List[int]:
        """获取上次简化后的 CNF"""
        return self.simplified_cnf.copy()
    
    def show_simplified_cnf(self) -> None:
        """显示简化后的 CNF"""
        if not self.simplified_cnf:
            print("No simplified CNF available. Call simplify() first.")
            return
        
        print("Simplified CNF:")
        clause = []
        for lit in self.simplified_cnf:
            if lit == 0:
                if clause:
                    print("  " + " ".join(str(l) for l in clause))
                    clause = []
            else:
                clause.append(lit)
        
        # 打印最后一个子句（如果有）
        if clause:
            print("  " + " ".join(str(l) for l in clause))
    
    
    def var_enlarge_to(self, v: int) -> None:
        """
        扩展变量到至少 v 个（确保变量索引 1 到 v 都存在）
        参数 v: 目标变量数量（DIMACS 格式，从 1 开始）
        """
        if self.backend == "minisat":
            # 调用 C++ 后端的变量扩展函数
            self.lib.minisat_var_enlarge_to(self.solver, v)
            # self.lib.minisat_var_enlarge_to(self.solver, 1000)
        
        # 更新 Python 端的最大变量记录
        if v > self.max_variable:
            self.max_variable = v
            
    def add(self, dimacs_lit: int) -> bool:
        """
        添加文字到当前子句，0 表示子句结束
        返回是否成功添加
        """
        if dimacs_lit == 0:
            # print("add_cls: ", end="")

            # # 遍历clause中的每个文字编码
            # for code in self.current_clause:
            #     # 解析变量索引（0-based）和符号
            #     var_0based = code // 2  # 提取变量（0-based）
            #     sign = code % 2         # 提取符号（1表示负文字，0表示正文字）
                
            #     # 转换为1-based变量编号
            #     var_1based = var_0based + 1
                
            #     # 计算DIMACS格式的文字（带符号）
            #     lit = -var_1based if sign else var_1based
                
            #     # 打印当前文字（不换行，用空格分隔）
            #     print(lit, end=" ")

            # # 打印换行，结束当前子句输出
            # print()
            return self._minisat_add_current_clause()
        else:
            self.current_clause.append(dimacs_lit)
            var = abs(dimacs_lit)
            if var > self.max_variable:
                self.max_variable = var
            return True
    
    def _minisat_add_current_clause(self) -> bool:
        """MiniSat 后端：添加当前子句"""
        self.clauses.append(self.current_clause.copy())
        if not self.current_clause:
            return False
            
        arr = (ctypes.c_int * len(self.current_clause))()
        for i, lit in enumerate(self.current_clause): 
            arr[i] = lit
            
        result = self.lib.minisat_add_clause(self.solver, arr, len(self.current_clause))
        self.current_clause.clear()
        return result
    
    # def _python_add_current_clause(self) -> bool:
    #     """Python 后端：添加当前子句"""
    #     if self.current_clause:
    #         self.clauses.append(self.current_clause.copy())
    #         self.current_clause.clear()
    #         return True
    #     return False
    
    def assume(self, assumption_lit: int) -> None:
        """添加假设文字"""
        self.assumptions.append(assumption_lit)
    
    def solve(self, simplify: bool = True) -> int:
        return self._minisat_solve(simplify)
    
    def _minisat_solve(self, simplify: bool = True) -> int:
        """MiniSat 后端求解"""
        # 设置假设
        if self.assumptions:
            self.lib.minisat_clear_assumptions(self.solver)
            arr = (ctypes.c_int * len(self.assumptions))()
            for i, lit in enumerate(self.assumptions): 
                arr[i] = lit
            self.lib.minisat_set_assumptions(self.solver, arr, len(self.assumptions))
        else:
            self.lib.minisat_clear_assumptions(self.solver)
        self.assumptions.clear()
        # 求解
        result = self.lib.minisat_solve(self.solver, ctypes.c_bool(simplify))
        
        if result == 10:  # SAT
            self.solve_result = self.SAT
            self._minisat_get_model()
            self.failed_assumptions.clear()
        elif result == 20:  # UNSAT
            self.solve_result = self.UNSAT
            self.var_values.clear()
            self._minisat_get_failed_assumptions()
        else:
            print("wrong")
            self.solve_result = self.UNKNOWN
            self.var_values.clear()
            self.failed_assumptions.clear()
        
        return self.solve_result
    
    def _minisat_get_model(self):
        """MiniSat 后端获取模型"""
        self.var_values = {}
        max_var = self.lib.minisat_max_var(self.solver)
        for var in range(1, max_var + 1):
            value = self.lib.minisat_model_value(self.solver, var - 1)
            if value != 0: 
                self.var_values[var] = (value == 1)
    
    def _minisat_get_failed_assumptions(self):
        """MiniSat 后端获取失败假设"""
        out_size = ctypes.c_int()
        failed_ptr = self.lib.minisat_get_failed_assumptions(self.solver, ctypes.byref(out_size))
        
        self.failed_assumptions = []
        if out_size.value > 0:
            self.failed_assumptions = {failed_ptr[i] for i in range(out_size.value)}
    
    # def _python_solve(self) -> int:
    #     """Python 后端求解（简化实现）"""
    #     # 这里应该实现一个真正的 Python SAT 求解器
    #     # 目前返回 UNKNOWN 表示需要 C++ 后端
    #     print("Warning: Python backend not fully implemented. Using MiniSat C++ backend is recommended.")
    #     self.solve_result = self.UNKNOWN
    #     self.var_values.clear()
    #     self.failed_assumptions.clear()
    #     return self.solve_result
    
    def val(self, lit: int) -> int:
        """
        获取文字的值
        返回: 1(真), -1(假), 0(未知)
        """
        if self.solve_result != self.SAT:
            return 0
        
        var = abs(lit)
        if var not in self.var_values:
            return 0
        
        var_value = self.var_values[var]
        if lit > 0:
            return lit if var_value else -lit
        else:
            return -lit if var_value else lit
    
    def failed(self, lit: int) -> int:
        """
        检查假设是否失败
        返回: 1(失败), 0(未失败)
        """
        if self.solve_result != self.UNSAT:
            return 0
        return 1 if lit in self.failed_assumptions else 0
    
    def max_var(self) -> int:
        """返回最大变量索引"""
        if self.backend == "minisat":
            return self.lib.minisat_max_var(self.solver)
        else:
            return self.max_variable
    
    def act(self) -> None:
        """清除假设和临时状态"""
        self.assumptions.clear()
        self.current_clause.clear()
        self.solve_result = self.UNKNOWN
        self.var_values.clear()
        self.failed_assumptions.clear()
        
        if self.backend == "minisat":
            self.lib.minisat_clear_assumptions(self.solver)
           
    def clear_act(self) -> None:

        # 条件性添加约束（与 C++ 版本行为一致）
        if self.clear_flag:
            max_var = self.max_var()
            if max_var > 0:
                # 添加 [-max_var] 单文字子句
                self.add(-max_var)
                self.add(0)  # 结束子句
            self.clear_flag = False       
            
    def set_clear_act(self) -> None:
        clear_flag = True
    
    def add_clause(self, clause: List[int]) -> bool:
        """直接添加完整子句（备选接口）"""
        for lit in clause:
            if not self.add(lit):
                return False
        return self.add(0)  # 结束子句
    
    # 可选的高级功能
    def freeze_var(self, var: int) -> None:
        """冻结变量（仅 MiniSat 后端支持）"""
        if self.backend == "minisat" and hasattr(self.lib, 'minisat_freeze_var'):
            self.lib.minisat_freeze_var(self.solver, var - 1)
    
    def unfreeze_var(self, var: int) -> None:
        """解冻变量（仅 MiniSat 后端支持）"""
        if self.backend == "minisat" and hasattr(self.lib, 'minisat_unfreeze_var'):
            self.lib.minisat_unfreeze_var(self.solver, var - 1)
    
    
    def get_raw_cnf(self) -> List[int]:
        """
        获取原始 CNF 子句（不执行简化）
        返回格式与 simplify() 相同，但不执行实际的简化操作
        """
        if self.backend != "minisat":
            return []
        
        out_size = ctypes.c_int()
        raw_cnf_ptr = self.lib.minisat_get_raw_cnf(self.solver, ctypes.byref(out_size))
        
        raw_cnf = []
        if out_size.value > 0:
            raw_cnf = [raw_cnf_ptr[i] for i in range(out_size.value)]
            
            # 释放 C++ 端分配的内存
            self.lib.minisat_free_simplified_cnf(raw_cnf_ptr)
        
        return raw_cnf
    
    def show_raw_cnf(self) -> None:
        """以可读格式显示原始 CNF"""
        raw_cnf = self.get_raw_cnf()
        if not raw_cnf:
            print("No raw CNF available.")
            return
        
        print("Raw CNF (without simplification):")
        clause = []
        clause_num = 1
        for lit in raw_cnf:
            if lit == 0:
                if clause:
                    # 跳过变量数量信息行 (nVars, -nVars, 0)
                    if len(clause) == 3 and clause[0] > 0 and clause[1] == -clause[0] and clause[2] == 0:
                        print(f"  Variables: {clause[0]}")
                    else:
                        print(f"  Clause {clause_num}: {' '.join(str(l) for l in clause)}")
                        clause_num += 1
                    clause = []
            else:
                clause.append(lit)
        
        # 打印最后一个子句（如果有）
        if clause:
            print(f"  Clause {clause_num}: {' '.join(str(l) for l in clause)}")
    
    def get_clauses(self) -> List[List[int]]:
        """
        获取原始 CNF 子句列表
        返回: 子句列表，每个子句是一个文字列表
        """
        raw_cnf = self.get_raw_cnf()
        clauses = []
        current_clause = []
        
        for lit in raw_cnf:
            if lit == 0:
                if current_clause:
                    # 跳过变量数量信息行 (nVars, -nVars, 0)
                    if len(current_clause) != 3 or not (current_clause[0] > 0 and current_clause[1] == -current_clause[0] and current_clause[2] == 0):
                        clauses.append(current_clause.copy())
                    current_clause.clear()
            else:
                current_clause.append(lit)
        
        # 添加最后一个子句（如果有）
        if current_clause:
            clauses.append(current_clause)
        
        return clauses
    
    def show_info(self, show_cnf: bool = False) -> None:
        """显示求解器信息"""
        print(f"SAT Solver Info:")
        print(f"  Backend: {self.backend}")
        print(f"  Max variable: {self.max_var()}")
        status_map = {self.SAT: 'SAT', self.UNSAT: 'UNSAT', self.UNKNOWN: 'Unknown'}
        print(f"  Solve result: {status_map[self.solve_result]}")
        for assume in self.assumptions:
            print("assume:",assume)
        # for i, clause in enumerate(self.clauses):
        #     print(f"clause {i}:", clause)
        raw_clauses = self.get_clauses()
        for i, clause in enumerate(raw_clauses):
            print(f"clause {i}:", clause)
        
        if show_cnf:
            raw_clauses = self.get_clauses()
            for i, clause in enumerate(raw_clauses):
                print(f"raw clause {i}:", clause)
        if self.solve_result == self.SAT:
            print(f"  Model size: {len(self.var_values)}")
        elif self.solve_result == self.UNSAT:
            print(f"  Failed assumptions: ", self.failed_assumptions)
        print(self.var_values)

# class SATSolver:
#     def __init__(self):
#         # 存储CNF子句：每个子句是一个文字列表（不含结束符0）
#         self.clauses = []
#         # 当前正在构建的子句（临时存储，等待0结束）
#         self.current_clause = []
#         # 存储假设文字（带假设求解时使用）
#         self.assumptions = []
#         # 最大变量索引
#         self.max_variable = 0
#         # 求解结果：1=SAT，0=UNSAT，-1=未求解
#         self.solve_result = -1
#         # 变量赋值（仅当solve_result=1时有效）：key=变量索引，value=1（真）/-1（假）
#         self.var_values = {}
#         # 失败的假设文字（仅当solve_result=0时有效）
#         self.failed_assumptions = set()

#     def add(self, dimacs_lit: int) -> None:
#         """添加DIMACS格式文字到CNF，0表示子句结束"""
#         if dimacs_lit == 0:
#             # 子句结束，添加到 clauses（忽略空句）
#             if self.current_clause:
#                 self.clauses.append(self.current_clause.copy())
#                 self.current_clause.clear()
#         else:
#             # 累加文字到当前子句，并更新最大变量
#             i_dimacs_lit = int(dimacs_lit)
#             self.current_clause.append(i_dimacs_lit)
#             var = abs(i_dimacs_lit)
#             if var > self.max_variable:
#                 self.max_variable = var

#     def assume(self, assumption_lit: int) -> None:
#         """添加假设文字（本次求解临时有效）"""
#         self.assumptions.append(assumption_lit)

#     def solve(self) -> int:
#         cnf = CNFFormula()
        
#         for clause in self.clauses:
#             cnf.add_clause(clause)
        

#         for lit in self.assumptions:
#             cnf.add_clause([lit])
        

#         try:
#             status,model = cnf.solve()
#             print(status)
#         except Exception as e:
#             print(f"求解失败: {e}")
#             self.solve_result = -1
#             return -1
        

#         if status == 'SAT':
#             self.solve_result = 1
#             self.var_values = model if model else {}  
#             self.failed_assumptions.clear()
#         elif status == 'UNSAT':
#             self.solve_result = 0
#             self.failed_assumptions = self._find_failed_assumptions(cnf)
#             print(self.failed_assumptions)
#             self.var_values.clear()
#         else:
#             self.solve_result = -1
#             self.var_values.clear()
#             self.failed_assumptions.clear()
        
#         return self.solve_result

#     def _find_failed_assumptions(self, base_cnf: CNFFormula) -> Set[int]:
#         """验证每个假设是否为失败文字（移除后公式变SAT）"""
#         failed = set()
#         if not self.assumptions:
#             return failed
        
#         # 复制基础CNF（不含任何假设）
#         from copy import deepcopy
#         cnf_copy = deepcopy(base_cnf)
        
#         for lit in self.assumptions:
#             # 构建“移除当前假设lit”的CNF：添加其他所有假设
#             temp_cnf = deepcopy(cnf_copy)
#             for other_lit in self.assumptions:
#                 if other_lit != lit:
#                     temp_cnf.add_clause([other_lit])  # 添加其他假设
            
#             # 求解：若SAT，则lit是失败假设（因为移除它后可满足）
#             status, _ = temp_cnf.solve()
#             if status == 'SAT':
#                 failed.add(lit)
        
#         return failed

#     def failed(self, lit: int) -> int:
#         """检查假设文字是否为失败文字（仅UNSAT时有效）"""
#         if self.solve_result != 0:
#             return 0  # 非UNSAT状态，无失败文字
#         # 简化逻辑：假设lit在假设列表中则为失败文字
#         return 1 if lit in self.assumptions else 0

#     def val(self, lit: int) -> int:
#         """返回文字的赋值结果（仅SAT时有效）"""
#         if self.solve_result != 1:
#             return 0  # 非SAT状态，无有效赋值
#         var = abs(lit)
#         sign = 1 if lit > 0 else -1
#         # 变量值乘以符号（1=真，-1=假）
#         return self.var_values.get(var, 1) * sign

#     def max_var(self) -> int:
#         """返回最大变量索引"""
#         return self.max_variable

#     def set_clear_act(self) -> None:
#         """设置清除活动变量标记（空实现，可扩展）"""
#         pass

#     def clear_act(self) -> None:
#         """清除活动变量和假设（重置临时状态）"""
#         self.assumptions.clear()
#         self.current_clause.clear()
#         self.solve_result = -1
#         self.var_values.clear()
#         self.failed_assumptions.clear()

#     def show_info(self) -> None:
#         """显示求解器信息"""
#         print(f"SAT Solver Info:")
#         print(f"  Clauses: {len(self.clauses)}")
#         print(f"  Max variable: {self.max_var()}")
#         print(f"  Last solve result: {'SAT' if self.solve_result == 1 else 'UNSAT' if self.solve_result == 0 else 'Unsolved'}")
#         if self.solve_result == 1:
#             print(f"  Assumptions: {self.assumptions}")


class CubeCMP:
    """Cube 的比较器（用于 set 排序，对应 C++ 的 Cube_CMP）"""
    def __call__(self, a, b):
        # 按文字列表排序（示例逻辑，可根据实际需求修改）
        return tuple(a.literals) < tuple(b.literals)



class Frame:

    def __init__(self):
        self.cubes = set()  
        self.solver = SATSolver()

class State:
    # 移除类属性的 latches 和 inputs（类属性会被所有实例共享，此处不需要）
    index = 0
    failed = 0
    failed_depth = 0
    next = None

    def __init__(self, latches=None, inputs=None):
        global state_count 
        state_count += 1
        self.index = state_count
        # 每个实例创建独立的列表（避免共享）
        self.latches = latches.copy() if latches is not None else []
        self.inputs = inputs.copy() if inputs is not None else []
        
    def clear(self):
        self.latches.clear()  # 现在只清空当前实例的列表
        self.inputs.clear()
        self.next = None
        
class Obligation:
    # 类属性可以省略（除非需要所有实例共享默认值，这里不需要）
    def __init__(self, s, k, d):
        self.state = s       # 绑定到实例：self.xxx
        self.frame_k = k     # 绑定到实例
        self.depth = d       # 绑定到实例
    
    def __lt__(self, other):
        # 现在可以正确访问实例属性
        if self.frame_k < other.frame_k:
            return True
        if self.frame_k > other.frame_k:
            return False
        # 帧号相同时，比较深度
        return self.depth < other.depth  # 简化逻辑