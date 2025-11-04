from Class import *
# 示例用法
if __name__ == "__main__":
    # 示例1：创建一个不可满足的CNF公式（3鸽2巢问题）
    print("示例1：3鸽2巢问题")
    pigeonhole_cnf = SATSolver()
    
    # 变量含义: 1=p(1,1), 2=p(1,2), 3=p(2,1), 4=p(2,2), 5=p(3,1), 6=p(3,2)
    pigeonhole_cnf.add_clause([1, 2])    # 鸽1必须进至少1个洞
    pigeonhole_cnf.add_clause([3, 4])    # 鸽2必须进至少1个洞
    pigeonhole_cnf.add_clause([5, 6])    # 鸽3必须进至少1个洞
    pigeonhole_cnf.add_clause([-1, -3])  # 洞1最多放1只鸽子（鸽1和鸽2不能同时进洞1）
    pigeonhole_cnf.add_clause([-1, -5])  # 洞1最多放1只鸽子（鸽1和鸽3不能同时进洞1）
    pigeonhole_cnf.add_clause([-3, -5])  # 洞1最多放1只鸽子（鸽2和鸽3不能同时进洞1）
    pigeonhole_cnf.add_clause([-2, -4])  # 洞2最多放1只鸽子（鸽1和鸽2不能同时进洞2）
    # pigeonhole_cnf.add_clause([-2, -6])  # 洞2最多放1只鸽子（鸽1和鸽3不能同时进洞2）
    # pigeonhole_cnf.add_clause([-4, -6])  # 洞2最多放1只鸽子（鸽2和鸽3不能同时进洞2）
    pigeonhole_cnf.assume(1)
    pigeonhole_cnf.assume(2)
    pigeonhole_cnf.assume(3)
    result = pigeonhole_cnf.solve()
    print(f"求解结果: {result}")  # 应输出UNSAT
    print(pigeonhole_cnf.failed(3))
    pigeonhole_cnf.show_info()
    # 示例2：创建一个可满足的CNF公式
    print("\n示例2：简单的可满足问题")
    simple_cnf = SATSolver()
    simple_cnf.show_info()
    # simple_cnf.clear_act()
    simple_cnf.add_clause([1, 2])       # x1 ∨ x2
    simple_cnf.add_clause([-1, 3])      # ¬x1 ∨ x3
    simple_cnf.add_clause([-2, -3])     # ¬x2 ∨ ¬x3
    
    result = simple_cnf.solve()
    print(f"求解结果: {result}")  # 应输出SAT
    print(simple_cnf.val(3))
