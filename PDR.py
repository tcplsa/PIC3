from Aiger import *
from Class import *
from functools import cmp_to_key
import random
import sys

frames = []
states = []
use_heuristic = 0
bad = 0
obligation_queue = []
core = []
map_to_prime = []
init_state = []
nexts = []
num_inputs = 0
num_latches = 0
num_constraints = 0
num_ands = 0
option_ctg_tries = 1
nkobl = 0
earliest_strengthened_frame = 0
top_frame_cannot_reach_bad = True
unprimed_first_dimacs = 2
primed_first_dimacs = 0
variables = []
ands = []
unknown = False
constraints_prime = []
constraints = []
lift = None
init = None
satelite = None
satelite2 = None
'''problem'''




def depth():
    return len(frames) - 2



    
def prime_var(var: int) -> int:
    if not hasattr(prime_var, "map_to_prime"):
        prime_var.map_to_prime = {} 
    if not hasattr(prime_var, "map_to_unprime"):
        prime_var.map_to_unprime = {} 

    assert var >= 1, f"变量{var}必须≥1"
    
    if var > 1:
        upper_bound = 1 + num_inputs + num_latches
        if var <= upper_bound:
            return primed_first_dimacs + var - 2
        else:
            if var not in prime_var.map_to_prime:
                unprimed_var = var
                while len(variables) <= unprimed_var:
                    variables.append(Variable(len(variables), f"unknown_{len(variables)}"))
                new_name = f"{variables[unprimed_var].name}'"
                primed_var = len(variables)
                prime_var.map_to_prime[unprimed_var] = primed_var
                prime_var.map_to_unprime[primed_var] = unprimed_var
                variables.append(Variable(primed_var, new_name)) 
            
            return prime_var.map_to_prime[var]
    else:
        return var

def prime_lit(lit):
    if lit >= 0:
        return prime_var(lit)
    else:
        return -prime_var(-lit)

def show_state(s):
    # 初始化字符列表，长度为输入数+锁存器数+2，默认值'x'
    a = ['x'] * (num_inputs + num_latches + 2)

    # 处理输入（inputs）：根据符号设置 '0' 或 '1'
    for i in s.inputs:
        abs_i = abs(i)
        a[abs_i] = '0' if i < 0 else '1'
    
    # 处理锁存器（latches）：根据符号设置 '0' 或 '1'
    for l in s.latches:
        abs_l = abs(l)
        a[abs_l] = '0' if l < 0 else '1'
    
    # 构建并打印输出字符串
    output = '['
    # 添加输入部分（索引 1+1 到 1+num_inputs）
    for i in range(1, num_inputs + 1):
        output += a[1 + i]
    # 添加分隔符
    output += '|'
    # 添加锁存器部分（索引 1+num_inputs+1 到 1+num_inputs+num_latches）
    for l in range(1, num_latches + 1):
        output += a[1 + num_inputs + l]
    output += ']'
    
    print(output)



def encode_lift(lift):
    global satelite2
    satelite2 = encode_translation(lift,satelite2)

def extract_state_from_sat(sat, s, succ, index):
    # print("extract_state_from_sat")

    global lift
    s.clear()
    if lift == None:
        lift = SATSolver()
        encode_lift(lift)
    # print("clear_flag",lift.clear_flag)
    lift.clear_act()
    # print("lift")
    # lift.show_info()
    assumptions = []
    latches = []
    distance = primed_first_dimacs - ( num_inputs + num_latches + 2 )
    for i in range (0, num_inputs):
        ipt = sat.val(unprimed_first_dimacs + i)
        pipt = sat.val(primed_first_dimacs + i)
        if ipt != 0:
            s.inputs.append(ipt)
            assumptions.append(ipt)
        if pipt > 0:
            pipt = pipt - distance
            assumptions.append(pipt)
        elif pipt < 0:
            pipt = -(-pipt - distance)
            assumptions.append(pipt)
    
    sz = len(assumptions)
    
    for i in range(0, num_latches):
        l = sat.val(unprimed_first_dimacs + num_inputs + i)
        if l != 0:
            latches.append(l)
            assumptions.append(l)
    
    act_var = lift.max_var() + 1
    # print("act_var", act_var)
    
    lift.add(-act_var)

    
    for l in constraints:
        lift.add(-l)
    for l in constraints_prime:
        lift.add(-l)
            
    if succ == None:
        lift.add(-bad_prime)
    else:
        for l in succ.latches: 
            lift.add(prime_lit(-l))
    lift.add(0)
    # print("lift add")
    
    
    assumptions.sort(key=cmp_to_key(lit_cmp))
    for i in range(0, len(assumptions)):
        if assumptions[i] >= num_inputs + num_latches + 2:
            assumptions[i] = assumptions[i] + distance
        elif assumptions[i] <= - (num_inputs + num_latches + 2):
            assumptions[i] = assumptions[i] - distance
            
    lift.assume(act_var)
    for l in assumptions:
        lift.assume(l)
    res = lift.solve(False)
    # lift.show_info()
    assert res == 0, f"不应为SAT"
    # print("lift:")
    for l in assumptions:
        if lift.failed(l):
            pass
            # print(variables[abs(l)].name)
    
    for l in latches:
        if lift.failed(l):
            s.latches.append(l)
    '''
    corelen = 0
    last_index = 0
    for i in range(0, len(assumptions)):
        l = assumptions[i]
        if abs(l) >= num_inputs + 2 and abs(l) <= num_inputs + num_latches + 1:
            corelen += 1
        if lift.failed(l):
            last_index = corelen
    '''
    s.next = succ
    lift.set_clear_act()
    # print("end extract_state_from_sat")
    return

def get_pre_of_bad(s):
    print("get pre of bad")
    global bad_prime
    s.clear()
    Fk = depth()
    # print("Fk=",Fk)
    # res = frames[Fk].solver.solve()
    # print("res before:",res)
    frames[Fk].solver.assume(bad_prime)
    
    res = frames[Fk].solver.solve(False)
    
    # frames[Fk].solver.show_info()
    
    # for c in frames[Fk].solver.clauses:
    #     print(c)
 
    # res = 0
    # print("res:",res)
    SAT = 1
    if res == SAT:  
        # sys.exit()
        bad_state = State()  

        for i in range(0, num_inputs):
            pipt = frames[Fk].solver.val(primed_first_dimacs + i)
            # print(pipt)
            if pipt > 0:
                bad_state.inputs.append(pipt - (primed_first_dimacs - unprimed_first_dimacs))
                # print("pipt add = ",pipt - (primed_first_dimacs - unprimed_first_dimacs))
            elif pipt < 0:
                bad_state.inputs.append(pipt + (primed_first_dimacs - unprimed_first_dimacs))
                # print("pipt add = ",pipt + (primed_first_dimacs - unprimed_first_dimacs))
        

        for i in range(0, num_latches):
            l_val = frames[Fk].solver.val(primed_first_dimacs + num_inputs + i)
            # print(l_val)
            if l_val > 0:
                bad_state.latches.append(l_val - (primed_first_dimacs - unprimed_first_dimacs))
                # print("l add = ",l_val - (primed_first_dimacs - unprimed_first_dimacs))
            elif l_val < 0:
                bad_state.latches.append(l_val + (primed_first_dimacs - unprimed_first_dimacs))
                # print("l add = ",l_val + (primed_first_dimacs - unprimed_first_dimacs))
        extract_state_from_sat(frames[Fk].solver, s, None, Fk)  
        s.next = bad_state
        # print(s.next.latches) 
        # show_state(s) 
        # print("end get pre of bad")
        return True
    else:  
        # print("end get pre of bad")
        return False
    
def encode_init_condition(s,aig):
    
    s.add(-1)
    s.add(0)
    for l in aig["latches"]:
        if l['default'] != 0:
            s.add(int((l['current'] / 2)+1))
            # print(int((l['current'] / 2)+1))
            s.add(0)
        else:
            s.add(int(-((l['current']) / 2)-1))
            # print(int(-((l['current']) / 2)-1))
            s.add(0)

    if len(aig["constraints"]) >= 0:
        for l in aig["constraints"]:
            s.add((l))
            s.add(0)

        lit_set = set()
        for l in aig["constraints"]:
            lit_set.add(abs(l))

        for a in reversed(aig["ands"]):
            if a[0] not in lit_set:
                continue
            lit_set.add(abs(a[1]))
            lit_set.add(abs(a[2]))

            s.add((-a[0]))
            s.add((a[1]))
            s.add(0)
            
            s.add((-a[0]))
            s.add((a[2]))
            s.add(0)
            
            s.add((a[0]))
            s.add((-a[1]))
            s.add((-a[2]))
            s.add(0)
    # print("add_cls finish load init")

def is_init(latches,aig):
    global init
    if init == None:
        init = SATSolver()
        encode_init_condition(init,aig)
    for l in latches:
        init.assume(l)
    res = init.solve()
    assert res != -1
    return res == 1
    

def encode_translation(s,satelite,cons = True):
    satelite_unsat = False
    if satelite == None:
        satelite = SATSolver()
        satelite.var_enlarge_to(len(variables)-1)
        for i in range(1, num_inputs + num_latches + 1):
            satelite.freeze_var(1 + i)
            satelite.freeze_var(prime_var(1 + i))
        satelite.freeze_var(abs(bad))
        satelite.freeze_var(abs(bad_prime))
        
        for i in range(0, num_constraints):
            satelite.freeze_var(abs(constraints[i]))
            satelite.freeze_var(prime_var(abs(constraints[i])))
        
        prime_lit_set = set()
        prime_lit_set.add(abs(bad))
        for l in constraints:
            prime_lit_set.add(abs(l))
        lit_set = prime_lit_set.copy()
        for l in nexts:
            lit_set.add(abs(l))
            
        satelite.add(-1)
        satelite.add(0)
        #print(-bad)
        satelite.add(-bad)
        satelite.add(0)
        
        if cons == True:
            for l in constraints:
                if l == bad:
                    satelite_unsat = True
                satelite.add((l))
                satelite.add(0)
        for i in range(0, num_latches):
            l = 1 + num_inputs + i + 1
            pl = prime_lit(l)
            next = nexts[i]
            #print(-pl," ",next)
            satelite.add(-pl)
            satelite.add(next)
            satelite.add(0)
            #print(-next," ",pl)
            satelite.add(-next)
            satelite.add(pl)
            satelite.add(0)
        #print(lit_set)
        for a in reversed(ands):

            assert a[0] > 0, f"And门输出a[0]必须为正数，实际为{a[0]}"
        
            if a[0] in lit_set:
                lit_set.add(abs(a[1]))
                lit_set.add(abs(a[2]))
                
                #print(-a[0]," ",a[1])
                satelite.add(-a[0])
                satelite.add(a[1])
                satelite.add(0)  
                #print(-a[0]," ",a[2])
                satelite.add(-a[0])
                satelite.add(a[2])
                satelite.add(0) 
                #print(a[0]," ",-a[1]," ",-a[2])
                satelite.add(a[0])
                satelite.add(-a[1])
                satelite.add(-a[2])
                satelite.add(0)  
                if a[0] in prime_lit_set:
                    po = prime_lit(a[0])
                    pi1 = prime_lit(a[1])
                    pi2 = prime_lit(a[2])
                    
                    prime_lit_set.add(abs(a[1]))
                    prime_lit_set.add(abs(a[2]))
                    
                    #print(-po," ",pi1)
                    satelite.add(-po)
                    satelite.add(pi1)
                    satelite.add(0)  
                    
                    #print(-po," ",pi2)
                    satelite.add(-po)
                    satelite.add(pi2)
                    satelite.add(0) 
                    
                    #print(po," ",-pi1," ",-pi2)
                    satelite.add(po)
                    satelite.add(-pi1)
                    satelite.add(-pi2)
                    satelite.add(0) 
        # satelite.show_info()
        satelite.simplify()

    for l in satelite.simplified_cnf:
        s.add(l)
    if satelite_unsat == True:
        s.add(1)
        s.add(0)
    # print("add_cls finish load transition")
    return satelite
    
    
def lit_cmp(a: int, b: int) -> int:
    abs_a = abs(a)
    abs_b = abs(b)
    if abs_a < abs_b:
        return -1  # a排在b前
    elif abs_a > abs_b:
        return 1   # b排在a前
    else:
        # 绝对值相等时，按数值本身从小到大排
        return -1 if a < b else 1 if a > b else 0

def is_inductive(aig,solver, latches, gen_core, reverse_assumption = False):
    # print("start is_inductive")
    global core
    solver.clear_act()
    # solver.set_clear_act()
    assumptions = []
    act = solver.max_var() + 1
    solver.add((-act))
    for i in latches:
        solver.add((-i))
    solver.add(0)
    if use_heuristic == 1:
        pass
    else:
        for i in latches:
            assumptions.append(prime_lit(i))
        assumptions.sort(key=cmp_to_key(lit_cmp))
    
    solver.assume(act)
    for i in assumptions:
        solver.assume(i)
    status = solver.solve(False)
    # solver.show_info()
    
    res = (status == 0)
    if res == True and gen_core == True:
        core.clear()
        for i in latches:
            if solver.failed(prime_lit(i)):
                core.append(i)
            if is_init(core,aig):
                core = latches.copy()
                break
    solver.set_clear_act()
    # print("core: ",core)
    # print("end is_inductive")

    return res



def generalize(cube, k, depth):
    mic_failed = 0
    required = []
    cube.sort(key = lambda x:abs(x))
    random.shuffle(cube)
    tmp_cube = cube
    for l in tmp_cube:
        cand = []
        if l not in cube:
           mic_failed = 0
           continue
        for i in cube:
            if i != l:
                cand.append(i)
        
        if CTG_down(cand, k, depth, required):
            mic_failed = 0
            cube = cand
        else:
            mic_failed += 1
            if mic_failed > option_ctg_tries:
                break
            required.append(l)

def CTG_down(cube, k, depth, required):
    return False



def add_cube(cube, k ,to_all, ispropagate, prtimes):
    global earliest_strengthened_frame
    if ispropagate == False:
        earliest_strengthened_frame =min(earliest_strengthened_frame,k)
    cube.sort(key = lambda x:abs(x))
    cube_tuple = tuple(cube)
    if cube_tuple in frames[k].cubes:
        return
    frames[k].cubes.add(cube_tuple)
    # print("Added cube(sz",len(cube),") to frame", k, ":")
    # for c in cube:
    #     print("-" if c < 0 else "", variables[abs(c)].name, end=' ')
    # print()
    if to_all == True:
        for i in range(1, k):
            for l in cube:
                frames[i].solver.add((-l))
            frames[i].solver.add(0)
    for l in cube:
        frames[k].solver.add((-l))
    frames[k].solver.add(0)
    for i in range(1, k + 1):
        pass
        # print("Frame", i, "now has", len(frames[i].cubes), "cubes.")


def rec_block_cube(aig):
    global nkobl
    global unknown
    print("rec_block_cube")
    states = []
    ct = 0
    cnt = 0
    while len(obligation_queue) != 0:
        print("obligation_queue size:", len(obligation_queue))
        obligation_queue.sort()
        cnt += 1
        # '''测试代码'''
        # if ct == 0: 
        #     break
        # '''测试代码'''
        obl = obligation_queue[0]
        sat = frames[obl.frame_k].solver
        # print("fk:", obl.frame_k)
        # sat.show_info()
        # exit()
        if is_inductive(aig, sat, obl.state.latches, True)  == True:
            # print("successfully block cube")
            del obligation_queue[0]
            tmp_core = core
            generalize(tmp_core, obl.frame_k, 1)
            # print("tmp_core: ",tmp_core)
            # generalize(tmp_core, obl.frame_k, 1)
            key = 0
            k = obl.frame_k + 1
            for k in range(obl.frame_k + 1, depth() + 1):
                key == 2
                if is_inductive(aig, frames[k].solver, tmp_core, False) == False:
                    key = 1
                    break
            if key == 2:
                k += 1
            if k > depth() + 1:
                k = depth() + 1
            pushpo = False
            la = obl.state.latches
            for ci in frames[k].cubes:
                lemma = ci
                if len(la) < len(lemma):
                    break
                all_included = True
                for elem in lemma:
                    # 检查 la 中是否存在与 elem 绝对值相同的元素
                    if not any(abs(la_elem) == abs(elem) for la_elem in la):
                        all_included = False
                        break
                if all_included:
                    pushpo = True  # 对应 pushpo = 1
                    nkobl += 1
                    break  # 找到匹配后跳出循环
            add_cube(tmp_core, k, True, False, k - obl.frame_k + (1 if (len(tmp_core) < len(core)) else 0))
            if k <= depth() and pushpo:  
                # print("k:",k,"  depth:",depth())
                obligation_queue.append(Obligation(obl.state, k, obl.depth))
        else:
            print("block cube failed")
            if cnt > 2147483640:
                unknown = True
                return False
            if obl.state.failed_depth and obl.state.failed_depth <= obl.depth + obl.frame_k:
                obligation_queue.sort()
                # 移除队列首个元素
                if obligation_queue:
                    obligation_queue.pop(0)  # 假设是列表，pop(0) 移除首个元素
                # 传递失败深度给下一个状态
                if obl.state.next is not None:
                    obl.state.next.failed_depth = obl.state.failed_depth
                continue  # 继续处理下一个义务

            # 第二个条件判断：检查失败次数和深度
            if obl.state.failed >= 5 and (obl.depth + obl.frame_k) > depth():
                obligation_queue.sort()
                # 移除队列首个元素
                if obligation_queue:
                    obligation_queue.pop(0)
                # 更新当前状态的失败深度
                obl.state.failed_depth = obl.depth + obl.frame_k
                # 传递失败深度给下一个状态
                if obl.state.next is not None:
                    obl.state.next.failed_depth = obl.state.failed_depth
                continue  # 继续处理下一个义务

            # 生成新状态并处理
            s = State()  # 创建新 State 实例

            if obl.frame_k == 0:
                # 处理 frame_k 为 0 的情况：提取输入和锁存器值
                s.clear()  # 清空状态的输入和锁存器
                # 提取输入值
                for i in range(num_inputs):
                    ipt = sat.val(unprimed_first_dimacs + i)
                    if ipt != 0:
                        s.inputs.append(ipt)
                # 提取锁存器值
                for i in range(num_latches):
                    l = sat.val(unprimed_first_dimacs + num_inputs + i)
                    if l != 0:
                        s.latches.append(l)
                # 设置反例相关信息
                s.next = obl.state
                cex_state_idx = s
                find_cex = True
                # print("end rec_block_cube")
                return False   # 返回求解结果

            else:
                # 处理 frame_k 不为 0 的情况：从 SAT 求解器提取状态
                extract_state_from_sat(sat, s, obl.state, obl.frame_k)
                # 向义务队列插入新义务
                new_obligation = Obligation(s, obl.frame_k - 1, obl.depth + 1)
                obligation_queue.append(new_obligation)  # 假设用 append 插入队列
                obligation_queue.sort()
    # print("end rec_block_cube")
    return True



def propagate(aig):
    global bad
    start_k = 1
    if top_frame_cannot_reach_bad == True:
        start_k = depth()
    print("Propagate from frame", start_k)
    for i in range(start_k, depth() + 1):
        ckeep = 0
        cprop = 0
        idx = 0  
        cubes_list = list(frames[i].cubes)
        while idx < len(frames[i].cubes):
            ci = cubes_list[idx] 
            # print("Checking cube at index", idx, ":", ci)
            if is_inductive(aig, frames[i].solver, ci, True):
                # print("true")
                cprop += 1
                if len(core) < len(ci):
                    add_cube(core, i+1, True, True, 1)
                else:
                    add_cube(core, i+1, False, True, 0)
                cubes_list.pop(idx) 
                frames[i].cubes = set(cubes_list)       
            else:
                ckeep += 1
                idx += 1  
        
        if len(frames[i].cubes) == 0:
            if len(frames[i].cubes) == 0:
                # 初始化变量
                invariant = None
                new_and_gate = None
                first_cube = True  # Python中用True/False表示布尔值
                badcube = []  # 假设Cube类已定义
                badcube.clear()    # 清空cube
                badcube.append(bad)
                badcube_tuple = tuple(badcube)
                frames[i+1].cubes.add(badcube_tuple)
                # frames[i+1].cubes.add(badcube)  # 假设用set存储cubes，使用add方法
                
                # 处理约束条件
                for l in constraints:
                    badcube.clear()
                    badcube.append(-l)
                    frames[i+1].cubes.add(tuple(badcube))
                
                
                # 处理证书输出
                if False:
                    # 合并后续帧的cubes
                    for d in range(i+2, depth() + 2):  # Python range是左闭右开，所以+2
                        for c in frames[d].cubes:
                            frames[i+1].cubes.add(c)
                    
                    # 处理每个cube构建AND门
                    for c in frames[i+1].cubes:
                        cc = c.copy()  # 复制cube
                        if len(cc) == 0:
                            cc.append(-1)
                        
                        # 排序并反转，假设Lit_CMP()对应lambda表达式
                        cc.sort(key=lambda x: abs(x))  # 按绝对值排序
                        cc.reverse()  # 反转列表
                        
                        first_bit = True
                        for l in cc:
                            if first_bit:
                                new_and_gate = l
                                first_bit = False
                                continue
                            
                            # 计算新的AND门索引
                            o = 1 + num_inputs + num_latches + num_ands + 1
                            # 根据绝对值大小决定参数顺序
                            if abs(new_and_gate) > abs(l):
                                ands.append(And(o, new_and_gate, l))
                            else:
                                ands.append(And(o, l, new_and_gate))
                            
                            new_and_gate = o
                            num_ands += 1
                        
                        # 处理第一个cube和后续cube的逻辑
                        if first_cube:
                            invariant = -new_and_gate
                            first_cube = False
                            continue
                        
                        # 创建新的AND门
                        o = 1 + num_inputs + num_latches + num_ands + 1
                        if abs(new_and_gate) > abs(invariant):
                            ands.append(And(o, -new_and_gate, invariant))
                        else:
                            ands.append(And(o, invariant, -new_and_gate))
                        
                        invariant = o
                        num_ands += 1
                    
                    # 最终处理 
                    bad = -invariant
            return True
    return False

def initialize(aig):  #把aig转化为cnf
    return convert_ands_to_clauses(aig["ands"])

def aiger_to_dimacs(lit):
    res = lit >> 1
    if lit & 1 == 1:
        return -res-1
    else:
        return res+1

def new_frame():     #创建新的帧
    last = len(frames)
    frame =  Frame()
    frames.append(frame)
    global satelite
    satelite = encode_translation(frames[last].solver,satelite)
    for l in constraints_prime:
        frames[last].solver.add(l)
        frames[last].solver.add(0)
    
def translate_to_dimacs(aig):
    global bad_prime 
    global bad
    global primed_first_dimacs
    variables.append(Variable(0,"NULL"))
    variables.append(Variable(1,"False"))
    
    for i in range(1, num_inputs + 1):
        variables.append(Variable(1 + i, None, 'i', i-1, 0))

    for i in range(1, num_latches + 1):
        variables.append(Variable(1 + num_inputs + i, None, 'l', i-1, 0))
    
    for i in range(1, num_ands + 1):
        o = 1 + num_inputs + num_latches + i
        i1 = aiger_to_dimacs(aig["ands"][i-1][1])
        i2 = aiger_to_dimacs(aig["ands"][i-1][2])
        variables.append(Variable(1 + num_inputs + num_latches + i, None, 'a', i-1, 0))
        ands.append([o,i1,i2])
    
    
    for i in range(1, num_latches + 1):
        l = 1 + num_inputs + i
        assert (l-1)*2 == aig["latches"][i-1]["current"], f"不匹配"
        al = aig["latches"][i-1]
        nexts.append(aiger_to_dimacs(al["next"]))
        if al["default"] == 0:
            init_state.append(-l)
        elif al["default"] == 1:
            init_state.append(l)
        
    for i in range(0, num_constraints):
        cst = aig["constraints"][i]
        constraints.append(aiger_to_dimacs(cst))
    
    primed_first_dimacs = len(variables)
    assert primed_first_dimacs == 1 + num_inputs + num_latches + num_ands + 1, f"primed_first_dimacs长度不匹配"
    
    for i in range(0, num_inputs):
        variables.append(Variable(primed_first_dimacs + i, None, 'i', i, 1))
        
    for i in range(0, num_latches):
        variables.append(Variable(primed_first_dimacs + num_inputs + i, None, 'l', i, 1))
    
    for i in range(0, num_constraints):
        pl = prime_lit(constraints[i])
        constraints_prime.append(pl)
    
    bad = aiger_to_dimacs(aig["bad"][0])
    bad_prime = prime_lit(bad)
    '''
    constraint
    '''
    # for var in variables:
    #     print(var.name)


    
def pdr_main(aig):
    global num_inputs
    global num_latches
    global num_constraints
    global num_ands
    global earliest_strengthened_frame
    global top_frame_cannot_reach_bad
    global unknown
    num_inputs = aig["I"]
    num_latches = aig["L"]
    num_ands = aig["A"]
    num_constraints = aig["C"]
    clauses = initialize(aig)
    translate_to_dimacs(aig)
    new_frame() #初始帧
    
    encode_init_condition(frames[0].solver,aig)
    new_frame()
    # for c in frames[1].solver.clauses:
    #     print("c: ",c)
    new_frame()
    
    assert depth() == 1, f"深度应该为1"
    top_frame_cannot_reach_bad = True
    earliest_strengthened_frame = depth()
    result = 10
    ct = 0
    cnt = 0
    while True:
        cnt += 1
        if cnt > 10000:  #强制退出协议
            unknown = True
            break
        
        s = State()   #全状态
        flag = get_pre_of_bad(s)
        # print("latches:",s.latches)
        if flag == True:   #如果存在义务
            # print("flag")
            obligation_queue.clear() #清空义务列表
            # print("s的编号是： ",s.index)
            obligation_queue.append(Obligation(s, depth()-1, 1)) #加入新义务
            top_frame_cannot_reach_bad = False #现在会到达bad
            if rec_block_cube(aig) == False:  #无法处理义务说明不安全
                result = 10
                break
            else:
                for p in states:
                    del p
        else:   #没有义务就看看能不能结束
            assert len(obligation_queue) == 0, f"存在未完成的义务"
            if propagate(aig) == True:  #能结束就退出
                result =20
                break
            new_frame()  #不能结束就进下一层
            top_frame_cannot_reach_bad = True
            earliest_strengthened_frame = depth()
    if unknown == True:
        result = 0
    return result