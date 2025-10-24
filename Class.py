import subprocess
import os
import tempfile

state_count = 0
class CNFFormula:
    """CNF公式类，用于存储子句并与minisat交互"""
    
    def __init__(self):
        self.clauses = []  # 存储子句的列表，每个子句是一个整数列表
        self.var_count = 0  # 变量数量
        
    def add_clause(self, clause):
        """
        向CNF公式添加一个子句
        
        参数:
            clause: 整数列表，每个整数表示一个文字(变量或其否定)
                    正数表示变量本身，负数表示变量的否定
        """
        if not isinstance(clause, list):
            raise ValueError("子句必须是一个整数列表")
        
        # 检查子句中的变量是否有效并更新变量计数
        for lit in clause:
            if not isinstance(lit, int) or lit == 0:
                raise ValueError("子句中的文字必须是非零整数")
            
            var = abs(lit)
            if var > self.var_count:
                self.var_count = var
                
        self.clauses.append(clause)
    
    def save_to_cnf(self, filename):
        """
        将CNF公式保存为DIMACS CNF格式文件
        
        参数:
            filename: 保存的文件名
        """
        with open(filename, 'w') as f:
            # 写入问题描述行：p cnf 变量数 子句数
            f.write(f"p cnf {self.var_count} {len(self.clauses)}\n")
            
            # 写入每个子句，每个子句以0结尾
            for clause in self.clauses:
                clause_str = ' '.join(map(str, clause)) + ' 0\n'
                f.write(clause_str)
    
    def solve(self,):

        base_dir = os.path.dirname(os.path.abspath(__file__))
        minisat_path = os.path.join(base_dir, "bin", "minisat")

        with tempfile.NamedTemporaryFile(mode='w', suffix='.cnf', delete=False) as cnf_file, \
             tempfile.NamedTemporaryFile(mode='r', suffix='.txt', delete=False) as result_file:
            
            cnf_filename = cnf_file.name
            result_filename = result_file.name
        
        try:

            self.save_to_cnf(cnf_filename)
            
            # 调用minisat求解器
            result = subprocess.run(
                [minisat_path, cnf_filename, result_filename],
                capture_output=True,
                text=True
            )
            
            # 检查是否运行成功
            # minisat返回码：0=正常，10=SAT，20=UNSAT
            if result.returncode not in [0, 10, 20]:
                raise RuntimeError(f"Minisat运行失败: {result.stderr}")
            
            # 读取并解析结果
            with open(result_filename, 'r') as f:
                first_line = f.readline().strip()
                if first_line == 'SAT':
                    return 'SAT'
                elif first_line == 'UNSAT':
                    return 'UNSAT'
                else:
                    raise ValueError(f"无法解析Minisat结果: {first_line}")
                    
        finally:
            # 清理临时文件
            if os.path.exists(cnf_filename):
                os.remove(cnf_filename)
            if os.path.exists(result_filename):
                os.remove(result_filename)

class Variable:
    dimacs_var = 0
    name = ""
    def __init__(self, dimacs_index, name = "", type = "", type_index = "", prime = 0):
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
        # 存储CNF子句：每个子句是一个文字列表（不含结束符0）
        self.clauses = []
        # 当前正在构建的子句（临时存储，等待0结束）
        self.current_clause = []
        # 存储假设文字（带假设求解时使用）
        self.assumptions = []
        # 最大变量索引
        self.max_variable = 0
        # 求解结果：1=SAT，0=UNSAT，-1=未求解
        self.solve_result = -1
        # 变量赋值（仅当solve_result=1时有效）：key=变量索引，value=1（真）/-1（假）
        self.var_values = {}
        # 失败的假设文字（仅当solve_result=0时有效）
        self.failed_assumptions = set()

    def add(self, dimacs_lit: int) -> None:
        """添加DIMACS格式文字到CNF，0表示子句结束"""
        if dimacs_lit == 0:
            # 子句结束，添加到 clauses（忽略空句）
            if self.current_clause:
                self.clauses.append(self.current_clause.copy())
                self.current_clause.clear()
        else:
            # 累加文字到当前子句，并更新最大变量
            self.current_clause.append(dimacs_lit)
            var = abs(dimacs_lit)
            if var > self.max_variable:
                self.max_variable = var

    def assume(self, assumption_lit: int) -> None:
        """添加假设文字（本次求解临时有效）"""
        self.assumptions.append(assumption_lit)

    def solve(self) -> int:
        """模拟SAT求解，返回1（SAT）、0（UNSAT）"""
        # 实际场景中需调用真实求解逻辑，这里简化模拟：
        # 1. 检查是否有明显矛盾（示例：包含空子句或假设冲突）
        # 2. 这里默认返回SAT（1），可根据需求修改
        self.solve_result = 1  # 模拟可满足
        # 模拟赋值：所有变量设为真（简化处理）
        '''self.var_values = {i: 1 for i in range(1, self.max_variable + 1)}'''
        # 清空失败假设（若之前有）
        self.failed_assumptions.clear()
        return self.solve_result

    def failed(self, lit: int) -> int:
        """检查假设文字是否为失败文字（仅UNSAT时有效）"""
        if self.solve_result != 0:
            return 0  # 非UNSAT状态，无失败文字
        # 简化逻辑：假设lit在假设列表中则为失败文字
        return 1 if lit in self.assumptions else 0

    def val(self, lit: int) -> int:
        """返回文字的赋值结果（仅SAT时有效）"""
        if self.solve_result != 1:
            return 0  # 非SAT状态，无有效赋值
        var = abs(lit)
        sign = 1 if lit > 0 else -1
        # 变量值乘以符号（1=真，-1=假）
        return self.var_values.get(var, 1) * sign

    def max_var(self) -> int:
        """返回最大变量索引"""
        return self.max_variable

    def set_clear_act(self) -> None:
        """设置清除活动变量标记（空实现，可扩展）"""
        pass

    def clear_act(self) -> None:
        """清除活动变量和假设（重置临时状态）"""
        self.assumptions.clear()
        self.current_clause.clear()
        self.solve_result = -1
        self.var_values.clear()
        self.failed_assumptions.clear()

    def show_info(self) -> None:
        """显示求解器信息"""
        print(f"SAT Solver Info:")
        print(f"  Clauses: {len(self.clauses)}")
        print(f"  Max variable: {self.max_var()}")
        print(f"  Last solve result: {'SAT' if self.solve_result == 1 else 'UNSAT' if self.solve_result == 0 else 'Unsolved'}")
        if self.solve_result == 1:
            print(f"  Assumptions: {self.assumptions}")


class Frame:
    cubes = []
    solver = SATSolver()

class State:
    latches = []
    inputs = []
    index = 0
    failed = 0
    failed_depth = 0


    def __init__(self,latches = [],inputs = []):
        global state_count 
        state_count += 1
        self.index = state_count
        self.latches = latches
        self.inputs = inputs
        
    def clear(self):
        pass
        
class Obligation:
    state = None
    frame_k = 0
    depth = 0
    def __init__(self, s, k, d):
        state = s
        frame_k = k
        depth = d
    
    def __lt__(self,other):
        if self.frame_k < other.frame_k:
            return True
        if self.frame_k > other.frame_k:
            return False
        if self.depth < other.depth:
            return True
        if self.depth >= other.depth:
            return False