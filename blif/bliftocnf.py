# blif2cnf.py
#!/usr/bin/env python3
"""
BLIF -> CNF converter (适配新版BLIF解析模块 + 时序下一状态处理)
核心特性：
1. 预处理连续变量分配 + 取反信号正负编码 + 辅助变量分离
2. 修复OFF-set/XOR编码错误
3. 新增时序电路下一状态变量处理：
   - 区分现态（current）和次态（next）变量
   - 生成锁存器次态→现态的转移约束
   - 支持初始状态约束编码
"""
import sys
import argparse
from collections import OrderedDict

# 导入新版BLIF解析模块
from IC3.blif.readblif import parse_blif_with_continuous_vars

# ===================== 时序变量工具函数 =====================
def get_next_var_name(var_name):
    """生成下一状态变量名（后缀标注）"""
    return f"{var_name}_next"

def get_next_var_id(base_var_id, signal_var_count):
    """
    生成下一状态变量编号：
    次态变量编号 = 现态变量编号 + 信号变量总数
    保证现态/次态变量空间完全分离
    """
    return base_var_id + signal_var_count

class CNF:
    def __init__(self):
        self.clauses = []
        self.signal_var_count = 0  # 现态信号变量总数
        self.aux_var_count = 0     # 辅助变量计数
        self.next_var_offset = 0   # 次态变量偏移量（= signal_var_count）
    
    def new_aux_var(self):
        """生成新的辅助变量（从 2*signal_var_count + 1 开始）"""
        self.aux_var_count += 1
        return self.next_var_offset + self.aux_var_count
    
    @property
    def var_count(self):
        """总变量数 = 现态 + 次态 + 辅助变量"""
        return self.next_var_offset * 2 + self.aux_var_count
    
    def set_next_var_offset(self, offset):
        """设置次态变量偏移量（在解析完现态变量后调用）"""
        self.next_var_offset = offset
    
    def add_clause(self, lits):
        """添加CNF子句（去重+过滤空值）"""
        unique_lits = list(dict.fromkeys([lit for lit in lits if lit != 0]))
        if unique_lits:
            self.clauses.append(unique_lits)
    
    def extend(self, other):
        """合并另一个CNF对象"""
        self.clauses.extend(other.clauses)
        self.signal_var_count = max(self.signal_var_count, other.signal_var_count)
        self.aux_var_count = max(self.aux_var_count, other.aux_var_count)
        self.next_var_offset = max(self.next_var_offset, other.next_var_offset)

# ===================== 核心编码函数 =====================
def get_literal(sig_name, name2var, neg_pairs, is_next=False, next_offset=0):
    """
    获取信号对应的CNF文字（支持现态/次态 + 取反对）
    :param sig_name: 信号名
    :param name2var: 现态变量映射
    :param neg_pairs: 取反对映射
    :param is_next: 是否为下一状态变量
    :param next_offset: 次态变量偏移量
    :return: 文字（变量编号×符号）
    """
    # 优先处理取反信号
    if sig_name in neg_pairs:
        src_var, sign = neg_pairs[sig_name]
        # 次态变量偏移
        if is_next:
            src_var = get_next_var_id(src_var, next_offset)
        return src_var * sign
    # 普通信号
    elif sig_name in name2var:
        var_id = name2var[sig_name]
        # 次态变量偏移
        if is_next:
            var_id = get_next_var_id(var_id, next_offset)
        return var_id
    else:
        raise ValueError(f"无效信号：{sig_name}（未分配变量）")

def pattern_to_literals(pattern, input_names, name2var, neg_pairs, is_next=False, next_offset=0):
    """
    将真值表pattern转换为CNF文字列表（支持次态变量）
    """
    if len(pattern) != len(input_names):
        pattern = pattern.ljust(len(input_names), '-')[:len(input_names)]
    
    lits = []
    for ch, nm in zip(pattern, input_names):
        if ch not in '01':
            continue
        
        # 获取信号文字（支持次态）
        base_lit = get_literal(nm, name2var, neg_pairs, is_next, next_offset)
        # 根据pattern的0/1调整符号
        if ch == '0':
            lits.append(-base_lit)
        else:
            lits.append(base_lit)
    
    return lits

def encode_special_gates(nm_inputs, nm_output, rows, name2var, neg_pairs, cnf, is_next=False):
    """
    编码特殊逻辑门（支持次态变量）
    """
    if len(nm_inputs) != 2:
        return False
    
    # 获取输入输出文字（支持次态）
    a_lit = get_literal(nm_inputs[0], name2var, neg_pairs, is_next, cnf.next_var_offset)
    b_lit = get_literal(nm_inputs[1], name2var, neg_pairs, is_next, cnf.next_var_offset)
    out_lit = get_literal(nm_output, name2var, neg_pairs, is_next, cnf.next_var_offset)
    
    on_patterns = [p for p, v in rows if v == '1']

    # XOR门
    if set(on_patterns) == {'01', '10'}:
        cnf.add_clause([a_lit, b_lit, -out_lit])
        cnf.add_clause([-a_lit, -b_lit, -out_lit])
        cnf.add_clause([a_lit, -b_lit, out_lit])
        cnf.add_clause([-a_lit, b_lit, out_lit])
        return True
    
    # AND门
    elif on_patterns == ['11']:
        cnf.add_clause([-out_lit, a_lit])
        cnf.add_clause([-out_lit, b_lit])
        cnf.add_clause([out_lit, -a_lit, -b_lit])
        return True
    
    # OR门
    elif set(on_patterns) == {'01', '10', '11'}:
        cnf.add_clause([-a_lit, out_lit])
        cnf.add_clause([-b_lit, out_lit])
        cnf.add_clause([-out_lit, a_lit, b_lit])
        return True
    
    # NAND门
    elif set(on_patterns) == {'00', '01', '10'}:
        cnf.add_clause([out_lit, a_lit])
        cnf.add_clause([out_lit, b_lit])
        cnf.add_clause([-out_lit, -a_lit, -b_lit])
        return True
    
    return False

def names_to_cnf_improved(nm_inputs, nm_output, rows, name2var, neg_pairs, cnf, is_next=False):
    """
    生成.names块对应的CNF子句（支持次态变量）
    """
    # 获取输出文字（支持次态）
    out_lit = get_literal(nm_output, name2var, neg_pairs, is_next, cnf.next_var_offset)
    
    # 尝试编码特殊门
    if encode_special_gates(nm_inputs, nm_output, rows, name2var, neg_pairs, cnf, is_next):
        return
    
    on_patterns = [p for p, v in rows if v == '1']
    off_patterns = [p for p, v in rows if v == '0']
    
    # 恒假
    if not on_patterns:
        cnf.add_clause([-out_lit])
        return
    
    # 恒真
    if not off_patterns:
        cnf.add_clause([out_lit])
        return
    
    # 通用情况：辅助变量编码
    aux_vars = []
    for pattern in on_patterns:
        lits = pattern_to_literals(pattern, nm_inputs, name2var, neg_pairs, is_next, cnf.next_var_offset)
        if not lits:
            cnf.add_clause([out_lit])
            return
        
        aux = cnf.new_aux_var()
        aux_vars.append(aux)
        
        # aux → 输入条件
        for lit in lits:
            cnf.add_clause([-aux, lit])
        # 输入条件 → aux
        cnf.add_clause([-lit for lit in lits] + [aux])
        # aux → 输出
        cnf.add_clause([-aux, out_lit])
    
    # 输出 → aux的OR
    if aux_vars:
        cnf.add_clause([-out_lit] + aux_vars)
    
    # OFF行编码
    for pattern in off_patterns:
        lits = pattern_to_literals(pattern, nm_inputs, name2var, neg_pairs, is_next, cnf.next_var_offset)
        if lits:
            cnf.add_clause([-lit for lit in lits] + [-out_lit])

def encode_latch_next_state(latches, name2var, neg_pairs, cnf):
    """
    编码锁存器的下一状态转移约束：
    核心逻辑：latch_output_next = latch_input (现态)
    """
    next_clauses = []
    
    for latch in latches:
        # 获取锁存器输出（现态）和输入（次态驱动）
        latch_out = latch['output']
        latch_in = latch['input']
        
        # 现态变量ID
        curr_out_lit = get_literal(latch_out, name2var, neg_pairs, False, cnf.next_var_offset)
        # 次态变量ID（输出的次态 = 输入的现态）
        next_out_lit = get_literal(latch_out, name2var, neg_pairs, True, cnf.next_var_offset)
        in_lit = get_literal(latch_in, name2var, neg_pairs, False, cnf.next_var_offset)
        
        # 生成转移约束：next_out ↔ in (等价于 (¬next_out ∨ in) ∧ (next_out ∨ ¬in))
        cnf.add_clause([-next_out_lit, in_lit])
        cnf.add_clause([next_out_lit, -in_lit])
        
        # 记录转移关系（用于输出映射）
        next_clauses.append((latch_out, curr_out_lit, next_out_lit, in_lit))
    
    return next_clauses

def encode_initial_state(latches, name2var, neg_pairs, cnf):
    """
    编码初始状态约束：latch_output = init_value
    """
    init_clauses = []
    
    for latch in latches:
        latch_out = latch['output']
        init_val = latch.get('init', 0)
        
        # 初始状态约束（仅作用于现态变量）
        lit = get_literal(latch_out, name2var, neg_pairs, False, cnf.next_var_offset)
        if init_val == 1:
            cnf.add_clause([lit])  # 初始值为1
        else:
            cnf.add_clause([-lit]) # 初始值为0
        
        init_clauses.append((latch_out, lit, init_val))
    
    return init_clauses

# ===================== 主构建函数 =====================
def build_cnf_complete(blif_result, encode_init_state=True):
    """
    构建完整的时序CNF：
    1. 组合逻辑（现态）
    2. 组合逻辑（次态驱动）
    3. 锁存器次态转移约束
    4. 初始状态约束（可选）
    """
    cnf = CNF()
    # 设置现态信号变量总数
    cnf.signal_var_count = blif_result.var_count
    # 设置次态变量偏移量（次态 = 现态 + signal_var_count）
    cnf.set_next_var_offset(blif_result.var_count)
    
    name2var = blif_result.name2var
    neg_pairs = blif_result.neg_pairs
    
    # 1. 编码现态组合逻辑
    for nm_inputs, nm_output, rows in blif_result.names_blocks:
        names_to_cnf_improved(nm_inputs, nm_output, rows, name2var, neg_pairs, cnf, is_next=False)
    
    # 2. 编码锁存器下一状态转移约束
    next_state_clauses = encode_latch_next_state(blif_result.latches, name2var, neg_pairs, cnf)
    
    # 3. 编码初始状态约束（可选）
    init_state_clauses = []
    if encode_init_state and blif_result.latches:
        init_state_clauses = encode_initial_state(blif_result.latches, name2var, neg_pairs, cnf)
    
    return cnf, name2var, next_state_clauses, init_state_clauses

# ===================== 输出函数 =====================
def write_latch_info(latches, name2var, neg_pairs, next_state_clauses, path):
    """
    写入锁存器信息（包含现态/次态变量映射）
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# latch_output (curr) | latch_output (next) | latch_input | init_value\n")
        # 构建锁存器映射表
        latch_map = {clause[0]: clause for clause in next_state_clauses}
        for latch in latches:
            latch_out = latch['output']
            init_val = latch.get('init', 0)
            if latch_out in latch_map:
                _, curr_lit, next_lit, in_lit = latch_map[latch_out]
                f.write(f"{curr_lit} {next_lit} {in_lit} {init_val}\n")

def write_next_var_map(name2var, next_offset, path):
    """
    写入次态变量映射文件
    """
    with open(path, 'w', encoding='utf-8') as f:
        f.write("# Variable ID → Signal Name (current/next)\n")
        # 现态变量
        f.write("## Current State Variables ##\n")
        for sig, var in sorted(name2var.items(), key=lambda x: x[1]):
            f.write(f"{var} {sig}\n")
        # 次态变量
        f.write("\n## Next State Variables ##\n")
        for sig, var in sorted(name2var.items(), key=lambda x: x[1]):
            next_var = get_next_var_id(var, next_offset)
            f.write(f"{next_var} {get_next_var_name(sig)}\n")
        # 辅助变量
        f.write("\n## Aux Variables ##\n")
        f.write("# Aux variables are numbered from 2*next_offset + 1\n")

# ===================== 主函数 =====================
def main():
    parser = argparse.ArgumentParser(description='Convert BLIF to DIMACS CNF (with next state support)')
    parser.add_argument('blif', help='Input BLIF file path')
    parser.add_argument('-o', '--output', help='Output CNF file path (default: <blif>.cnf)')
    parser.add_argument('-l', '--latches', help='Output latch info file path')
    parser.add_argument('-n', '--next-map', help='Output next state variable map file path')
    parser.add_argument('--no-init', action='store_true', help='Disable initial state constraint encoding')
    parser.add_argument('-v', '--verbose', action='store_true', help='Print verbose information')
    
    args = parser.parse_args()
    
    # 1. 解析BLIF
    try:
        blif_result = parse_blif_with_continuous_vars(args.blif)
    except Exception as e:
        print(f"Error parsing BLIF file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 2. 打印Verbose信息
    if args.verbose:
        print(f"=== BLIF Parsing Result ===")
        print(f"Input file: {args.blif}")
        print(f"Top-level inputs: {blif_result.inputs}")
        print(f"Top-level outputs: {blif_result.outputs}")
        print(f"Valid names blocks: {len(blif_result.names_blocks)}")
        print(f"Latches/DFFs: {len(blif_result.latches)}")
        print(f"Current state variables: {blif_result.var_count}")
        print(f"Next state variables offset: {blif_result.var_count}")
        print(f"Negation pairs: {len(blif_result.neg_pairs)}")
    
    # 3. 构建时序CNF
    try:
        encode_init = not args.no_init
        cnf, name2var, next_state_clauses, init_state_clauses = build_cnf_complete(blif_result, encode_init)
    except Exception as e:
        print(f"Error building CNF: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 4. 输出CNF文件
    cnf_file = args.output or (args.blif[:-5] if args.blif.endswith('.blif') else args.blif) + '.cnf'
    try:
        with open(cnf_file, 'w', encoding='utf-8') as f:
            # 写入时序相关注释
            f.write(f"c Converted from BLIF: {args.blif}\n")
            f.write(f"c Current state vars: {cnf.signal_var_count}\n")
            f.write(f"c Next state vars: {cnf.next_var_offset}\n")
            f.write(f"c Aux vars: {cnf.aux_var_count}\n")
            f.write(f"c Next state clauses: {len(next_state_clauses)}\n")
            f.write(f"c Initial state clauses: {len(init_state_clauses)}\n")
            f.write(f"p cnf {cnf.var_count} {len(cnf.clauses)}\n")
            # 写入子句
            for clause in cnf.clauses:
                f.write(' '.join(str(lit) for lit in clause) + ' 0\n')
        print(f"Successfully wrote CNF to: {cnf_file}")
        print(f"  Total variables: {cnf.var_count} (curr: {cnf.signal_var_count}, next: {cnf.next_var_offset}, aux: {cnf.aux_var_count})")
        print(f"  Total clauses: {len(cnf.clauses)} (next state: {len(next_state_clauses)}, init: {len(init_state_clauses)})")
    except Exception as e:
        print(f"Error writing CNF file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 5. 输出变量映射文件
    map_file = cnf_file + '.map'
    try:
        write_next_var_map(name2var, cnf.next_var_offset, map_file)
        print(f"Successfully wrote variable map (with next state) to: {map_file}")
    except Exception as e:
        print(f"Error writing variable map: {e}", file=sys.stderr)
        sys.exit(1)
    
    # 6. 输出锁存器信息（包含次态）
    if blif_result.latches and args.latches:
        try:
            write_latch_info(blif_result.latches, name2var, neg_pairs, next_state_clauses, args.latches)
            print(f"Successfully wrote latch info (with next state) to: {args.latches}")
        except Exception as e:
            print(f"Error writing latch info: {e}", file=sys.stderr)
            sys.exit(1)
    
    # 7. 单独输出次态变量映射（可选）
    if args.next_map:
        try:
            with open(args.next_map, 'w', encoding='utf-8') as f:
                f.write("# Next State Variable Mapping\n")
                f.write("# NextVarID = CurrVarID + {cnf.next_var_offset}\n")
                for sig, var in sorted(name2var.items(), key=lambda x: x[1]):
                    next_var = get_next_var_id(var, cnf.next_var_offset)
                    f.write(f"{var} → {next_var} ({get_next_var_name(sig)})\n")
            print(f"Successfully wrote next state map to: {args.next_map}")
        except Exception as e:
            print(f"Error writing next state map: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()