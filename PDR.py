from Aiger import *
from Class import *
from functools import cmp_to_key
import random

frames = []
states = []
use_heuristic = 0
obligation_queue = []
core = [] #有问题
option_ctg_tries = 1
earliest_strengthened_frame = 0
top_frame_cannot_reach_bad = True
unprimed_first_dimacs = 2
variables = []
'''problem'''
primed_first_dimacs = 100


def depth():
    return len(frames) - 1


def prime_var(lit):
    pass

def prime_lit(lit):
    if lit >= 0:
        return prime_var(lit)
    else:
        return -prime_var(-lit)


def extract_state_from_sat(sat, s, succ, index):
    pass

def get_pre_of_bad(s,aig):
    s.clear()
    Fk = depth()
    frames[Fk].solver.assume(bad_prime)
    res = frames[Fk].solver.solve()
    res = 0
    SAT = 1
    if res == SAT:  
        bad_state = State()  #
        for i in range(0, aig["I"]):
            pipt = frames[Fk].solver.val(primed_first_dimacs + i)
            if pipt > 0:
                bad_state.inputs.append(pipt - (primed_first_dimacs - unprimed_first_dimacs))
            elif pipt < 0:
                bad_state.inputs.append(pipt + (primed_first_dimacs - unprimed_first_dimacs))
        

        for i in range(0, aig["L"]):
            l_val = frames[Fk].solver.val(primed_first_dimacs + aig["I"] + i)
            if l_val > 0:
                bad_state.latches.append(l_val - (primed_first_dimacs - unprimed_first_dimacs))
            elif l_val < 0:
                bad_state.latches.append(l_val + (primed_first_dimacs - unprimed_first_dimacs))
        
        extract_state_from_sat(frames[Fk].solver, s, None, Fk)  
        s.next = bad_state  
        return True
    else:  
        return False
    
def encode_init_condition(s,aig):
    s.add(-1)
    s.add(0)
    for l in aig["latches"]:
        if l['current'] % 2 == 0:
            s.add((l['current'] / 2))
            s.add(0)
        else:
            s.add(((l['current'] + 1) / 2))
            s.add(0)

    if len(aig["constraints"]) >= 0:
        for l in aig["constraints"]:
            s.add((l))
            s.add(0)

        lit_set = []
        for l in aig["constraints"]:
            lit_set.insert((abs(l)));

        for a in reversed(aig["ands"]):
            if a[0] in lit_set:
                continue
            lit_set.append((abs(a[1])));
            lit_set.append((abs(a[2])));

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
        

def is_init(latches):
    '''to be finish'''
    return False
    

def encode_translation(s):
    pass
    
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

def is_inductive(solver, latches, gen_core, reverse_assumption = 0):
    solver.clear_act()
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
            assumptions.append(i)
        assumptions.sort(key=cmp_to_key(lit_cmp))
    
    solver.assume(act)
    for i in assumptions:
        solver.assume(i)
    status = solver.solve()
    print(status)
    res = (status == 20)
    if res > 0 and gen_core > 0:
        core.clear()
        for i in latches:
            if solver.failed(prime_lit(i)):
                core.append(i)
            if is_init(core):
                core = latches
    solver.set_clear_act()
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
            required.insert(l)
        
def CTG_down():
    pass



def add_cube(cube, k ,to_all, ispropagate, prtimes):
    if ispropagate == False:
        earliest_strengthened_frame =min(earliest_strengthened_frame,k)
    cube.sort(key = lambda x:abs(x))
    if cube in frames[k].cubes:
        return
    frames[k].cubes.append(cube)
    if to_all == True:
        for i in range(1, k):
            for l in cube:
                frames[i].solver.add((-l))
            frames[i].solver.add(0)
    for l in cube:
        frames[k].solver.add((-l))
    frames[k].solver.add(0)


def rec_block_cube():
    now_state = []
    ct = 0
    while len(obligation_queue) != 0:

        '''测试代码'''
        if ct == 0: 
            break
        '''测试代码'''

        obl = obligation_queue[0]
        sat = frames[obl.frame_k].solver
        if is_inductive(sat, obl.state.latches, True)  == True:
            del obligation_queue[0]
            tmp_core = core
            generalize(tmp_core, obl.frame_k)
            for k in range(obl.frame_k + 1, depth() + 1):
                if is_inductive(frames[k].solver, tmp_core, False) == False:
                    break
            la = obl.state.latches
            for ci in frames[k].cubes:
                lemma = ci
                if len(la) < len(lemma):
                    break
            add_cube(tmp_core, k, True, False, k - obl.frame_k + (len(tmp_core) < len(core)))
            if k <= depth() and True:  #应为pushpo，未解决
                obligation_queue.append(Obligation(obl.state, k, obl.depth, 1))
        else:
            pass
            '''
            to be finished
            '''
    return True



def propagate():
    start_k = 1
    if top_frame_cannot_reach_bad == True:
        start_k = depth()
    for i in range(start_k, depth() + 1):
        ckeep = 0
        cprop = 0
        idx = 0  
        while idx < len(frames[i].cubes):
            ci = frames[i].cubes[idx] 

            if is_inductive(frames[i].solver, ci, True):

                cprop += 1
                if len(core) < len(ci):
                    add_cube(core, i+1, True, True, 1)
                else:
                    add_cube(core, i+1, False, True, 0)
                frames[i].cubes.pop(idx)         
            else:
                ckeep += 1
                idx += 1  
        if len(frames[i].cubes) == 0:
            '''
            if len(frames[i].cubes) == 0:
                # 初始化变量
                invariant = None
                new_and_gate = None
                first_cube = True  # Python中用True/False表示布尔值
                badcube = Cube()   # 假设Cube类已定义
                badcube.clear()    # 清空cube
                badcube.append(bad)
                frames[i+1].cubes.add(badcube)  # 假设用set存储cubes，使用add方法
                
                # 处理约束条件
                for l in constraints:
                    badcube.clear()
                    badcube.append(-l)
                    frames[i+1].cubes.add(badcube)
                
                # 输出帧统计信息
                if output_stats_for_frames:
                    show_frames()
                
                # 处理证书输出
                if output_certificate:
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
            '''
            return True
    return False

def initialize(aig):  #把aig转化为cnf
    return convert_ands_to_clauses(aig["ands"])


def new_frame():     #创建新的帧
    frame =  Frame()
    frames.append(frame)
    
def translate_to_dimacs(aig):
    variables.append(Variable(0,"NULL"))
    variables.append(Variable(1,"False"))
    
    for i in range(1,aig["I"] + 1):
        variables.append(Variable(1 + i,'i',i-1, 0))

    for i in range(1,aig["L"] + 1):
        variables.append(Variable(1 + aig["I"] + i,'l',i-1, 0))
    
    for i in range(1, aig["A"] + 1):
        variables.append(Variable(1 + aig["I"] + aig["L"] + i,'a',i-1, 0))
    
    bad = aig["bad"][0]
    global bad_prime 
    bad_prime = prime_lit(bad)
    '''
    constraint
    '''

    
def pdr_main(aig):
    clauses = initialize(aig)
    translate_to_dimacs(aig)
    new_frame() #初始帧
    encode_init_condition(frames[len(frames)-1].solver,aig)
    top_frame_cannot_reach_bad = True
    earliest_strengthened_frame = depth()
    result = 10
    ct = 0
    cnt = 0
    while True:
        cnt += 1
        if cnt > 1000000:  #强制退出协议
            break
        
        s = State()   #全状态
        flag = get_pre_of_bad(s,aig)
        if flag == True:   #如果存在义务
            obligation_queue.clear() #清空义务列表
            obligation_queue.append(Obligation(s, depth()-1, 1)) #加入新义务
            top_frame_cannot_reach_bad = False #现在会到达bad
            if rec_block_cube() == False:  #无法处理义务说明不安全
                result = 10
                break
            else:
                for p in states:
                    del p
        else:   #没有义务就看看能不能结束
            if propagate() == True:  #能结束就退出
                result =20
                break
            new_frame()  #不能结束就进下一层
            top_frame_cannot_reach_bad = True
            earliest_strengthened_frame = depth()
    return result