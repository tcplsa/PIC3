from collections import OrderedDict

class BLIFParserResult:
    """BLIF解析结果封装类"""
    def __init__(self):
        self.inputs = []                # 顶层输入信号编号列表
        self.outputs = []               # 顶层输出信号编号列表
        self.names_blocks = []          # 原始有效.names块列表
        self.ands = []                  # AND门（变量编号）
        self.xors = []                  # XOR门（变量编号）
        self.latches = []               # 锁存器信息（input编号, output编号, 初始值）→ output必为正
        self.name2var = OrderedDict()   # 信号名→变量编号映射
        self.var_count = 0              # 有效变量总数
        self.neg_pairs = {}             # 取反对映射：取反信号→(源变量编号, 符号)
        self.eq_pairs = {}              # 缓冲器等价映射：输出→输入
        self.constraints = []
        
def _parse_blif_core(path):
    """核心BLIF解析：提取结构、识别取反对和缓冲器"""
    inputs = []
    outputs = []
    names_blocks = []
    latches = []
    used_signals = set()
    neg_pairs = {}
    eq_pairs = {}

    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = [l.rstrip('\n') for l in f]
    except FileNotFoundError:
        raise FileNotFoundError(f"BLIF文件不存在：{path}")
    except Exception as e:
        raise RuntimeError(f"读取BLIF失败：{e}")

    i = 0
    line_count = len(lines)
    while i < line_count:
        line = lines[i].strip()
        i += 1

        if not line or line.startswith('#'):
            continue

        # 处理顶层输入
        if line.startswith('.inputs'):
            input_signals = line.split()[1:]
            input_signals = [s for s in input_signals if s not in ['rst_n', 'clk']]
            inputs.extend(input_signals)
            used_signals.update(input_signals)
            continue

        # 处理顶层输出
        if line.startswith('.outputs'):
            output_signals = line.split()[1:]
            outputs.extend(output_signals)
            used_signals.update(output_signals)
            continue

        # 处理.names块
        if line.startswith('.names'):
            parts = line.split()
            nm_inputs = parts[1:-1] if len(parts) > 1 else []
            nm_output = parts[-1] if len(parts) >= 1 else ''

            # 解析真值表
            rows = []
            while i < line_count:
                next_line = lines[i].strip()
                i += 1
                if not next_line or next_line.startswith('#'):
                    continue
                if next_line.startswith('.'):
                    i -= 1
                    break
                toks = next_line.split()
                if len(toks) < 1:
                    continue
                rows.append((toks[0], toks[1] if len(toks) >= 2 else '1'))

            if not rows:
                continue

            # 识别单输入门：反相器/缓冲器
            if len(nm_inputs) == 1 and len(rows) == 1:
                src_sig = nm_inputs[0]
                if rows[0] == ('0', '1'):
                    neg_pairs[nm_output] = src_sig
                    used_signals.add(src_sig)
                elif rows[0] == ('1', '1'):
                    eq_pairs[nm_output] = src_sig
                    used_signals.add(src_sig)
                continue

            # 普通.names块
            used_signals.update(nm_inputs)
            used_signals.add(nm_output)
            names_blocks.append((nm_inputs, nm_output, rows))
            continue

        # 处理锁存器
        if line.startswith('.latch'):
            parts = line.split()
            if len(parts) >= 3:
                input_sig = parts[1]
                output_sig = parts[2]
                init_val = 1 if (len(parts) >= 5 and parts[4] == '1') else 0
                used_signals.add(input_sig)
                used_signals.add(output_sig)
                latches.append({'type':'latch', 'input':input_sig, 'output':output_sig, 'init':init_val})
            continue

        # 处理DFF子电路
        if line.startswith('.subckt'):
            parts = line.split()
            if len(parts) < 2 or parts[1] not in ['$dff', '$_SDFF_PN0_', '$_SDFF_PP0_', '$_DFF_P_', '$_SDFF_NP0_']:
                continue
            params = {}
            for param in parts[2:]:
                if '=' in param:
                    k, v = param.split('=', 1)
                    params[k] = v
            if 'D' not in params or 'Q' not in params:
                continue
            d_sig, q_sig = params['D'], params['Q']
            clk_sig = params.get('C', 'clk')
            rst_sig = params.get('R', None)
            used_signals.add(d_sig)
            used_signals.add(q_sig)
            used_signals.add(clk_sig)
            if rst_sig:
                used_signals.add(rst_sig)
            latches.append({
                'type':'dff', 'input':d_sig, 'output':q_sig, 
                'clk':clk_sig, 'rst':rst_sig, 'init':0
            })
            continue

        if line.startswith('.end'):
            break

    return inputs, outputs, names_blocks, latches, used_signals, neg_pairs, eq_pairs

def _identify_gate_type(nm_inputs, rows):
    """识别2输入门类型：AND/XOR/OR及其反相"""
    if len(nm_inputs) != 2:
        return 'unknown', False
    
    full_table = {'00':'0', '01':'0', '10':'0', '11':'0'}
    for pattern, value in rows:
        if pattern in full_table:
            full_table[pattern] = value
    
    v00, v01, v10, v11 = full_table['00'], full_table['01'], full_table['10'], full_table['11']

    if v00 == '0' and v01 == '0' and v10 == '0' and v11 == '1':
        return 'and', False
    elif v00 == '1' and v01 == '1' and v10 == '1' and v11 == '0':
        return 'and', True
    elif v00 == '0' and v01 == '1' and v10 == '1' and v11 == '0':
        return 'xor', False
    elif v00 == '1' and v01 == '0' and v10 == '0' and v11 == '1':
        return 'xor', True
    elif v00 == '0' and v01 == '1' and v10 == '1' and v11 == '1':
        return 'or', False
    elif v00 == '1' and v01 == '0' and v10 == '0' and v11 == '0':
        return 'or', True
    else:
        return 'unknown', False

def _split_names_to_ands_xors(names_blocks):
    """将.names块拆解为AND/XOR门"""
    ands, xors = [], []
    for nm_inputs, nm_output, rows in names_blocks:
        gate_type, invert_output = _identify_gate_type(nm_inputs, rows)
        if len(nm_inputs) == 2:
            if gate_type == 'and':
                ands.append((nm_output, nm_inputs[0], nm_inputs[1], invert_output))
            elif gate_type == 'xor':
                xors.append((nm_output, nm_inputs[0], nm_inputs[1], invert_output))
            elif gate_type == 'or':
                ands.append((nm_output, f"~{nm_inputs[0]}", f"~{nm_inputs[1]}", not invert_output))
    return ands, xors

def _resolve_equivalence(sig_name, eq_pairs):
    """递归解析缓冲器等价映射"""
    while sig_name in eq_pairs:
        sig_name = eq_pairs[sig_name]
    return sig_name

def _map_signal_to_var(sig_name, name2var, neg_pairs, eq_pairs, force_positive=False):
    """信号名转变量编号（处理取反和等价）
    :param force_positive: 是否强制返回正编号（仅用于锁存器output）
    """
    invert = False
    if sig_name.startswith('~'):
        invert = True
        sig_name = sig_name[1:]
    
    sig_name = _resolve_equivalence(sig_name, eq_pairs)

    # ========== 核心修复：正确处理neg_pairs的元组值 ==========
    if sig_name in neg_pairs:
        # neg_pairs[sig_name] 是 (源变量编号, 符号) 元组，直接取源变量编号
        src_var, _ = neg_pairs[sig_name]
        var = -src_var if invert else src_var
    elif sig_name in name2var:
        var = name2var[sig_name]
        var = -var if invert else var
    else:
        raise KeyError(f"信号{sig_name}未分配编号")
    
    # 强制返回正编号（锁存器output专用）
    if force_positive:
        return abs(var)
    return var

def _map_gate_signals_to_vars(inputs, outputs, latches, ands_list, xors_list, name2var, neg_pairs, eq_pairs):
    """映射所有信号到变量编号（保证锁存器output为正）"""
    inputs_var = [_map_signal_to_var(s, name2var, neg_pairs, eq_pairs) for s in inputs]
    outputs_var = [_map_signal_to_var(s, name2var, neg_pairs, eq_pairs) for s in outputs]
    
    latches_var = []
    for latch in latches:
        # 锁存器input：正常映射（可正可负）
        in_var = _map_signal_to_var(latch['input'], name2var, neg_pairs, eq_pairs)
        # 锁存器output：强制映射为正编号
        out_var = _map_signal_to_var(latch['output'], name2var, neg_pairs, eq_pairs, force_positive=True)
        latches_var.append((in_var, out_var, latch['init']))
    
    ands_var = []
    for out_sig, in1_sig, in2_sig, invert_out in ands_list:
        out_var = _map_signal_to_var(out_sig, name2var, neg_pairs, eq_pairs)
        in1_var = _map_signal_to_var(in1_sig, name2var, neg_pairs, eq_pairs)
        in2_var = _map_signal_to_var(in2_sig, name2var, neg_pairs, eq_pairs)
        ands_var.append((-out_var if invert_out else out_var, in1_var, in2_var, invert_out))
    
    xors_var = []
    for out_sig, in1_sig, in2_sig, invert_out in xors_list:
        out_var = _map_signal_to_var(out_sig, name2var, neg_pairs, eq_pairs)
        in1_var = _map_signal_to_var(in1_sig, name2var, neg_pairs, eq_pairs)
        in2_var = _map_signal_to_var(in2_sig, name2var, neg_pairs, eq_pairs)
        xors_var.append((-out_var if invert_out else out_var, in1_var, in2_var, invert_out))
    
    return inputs_var, outputs_var, latches_var, ands_var, xors_var

def _assign_continuous_vars(inputs, outputs, latches, used_signals, neg_pairs, eq_pairs):
    """分配连续变量编号（优先级：锁存器输出→输入→取反源→输出→中间信号，保证锁存器输出先分配正编号）"""
    name2var = OrderedDict()
    var_count = 1
    neg_map = {}

    def new_var():
        nonlocal var_count
        curr = var_count
        var_count += 1
        return curr

    # 解析所有信号的等价映射
    used_signals_resolved = set(_resolve_equivalence(s, eq_pairs) for s in used_signals)

    # ========== 核心调整：优先分配锁存器输出（保证正编号） ==========
    # 提取所有锁存器输出信号（去重+解析等价）
    latch_outputs = set()
    for latch in latches:
        sig_res = _resolve_equivalence(latch['output'], eq_pairs)
        latch_outputs.add(sig_res)
    # 优先为锁存器输出分配正编号
    for sig in sorted(latch_outputs):
        if sig in used_signals_resolved and sig not in name2var:
            name2var[sig] = new_var()

    # 分配输入信号
    for sig in inputs:
        sig_res = _resolve_equivalence(sig, eq_pairs)
        if sig_res in used_signals_resolved and sig_res not in name2var:
            name2var[sig_res] = new_var()

    # 分配取反源信号
    neg_src = sorted(set(_resolve_equivalence(s, eq_pairs) for s in neg_pairs.values()))
    for sig in neg_src:
        if sig in used_signals_resolved and sig not in name2var:
            name2var[sig] = new_var()

    # 分配输出信号
    for sig in outputs:
        sig_res = _resolve_equivalence(sig, eq_pairs)
        if sig_res in used_signals_resolved and sig_res not in name2var:
            name2var[sig_res] = new_var()

    # 分配剩余信号
    assigned = set(name2var.keys())
    neg_sigs = set(_resolve_equivalence(s, eq_pairs) for s in neg_pairs.keys())
    remaining = sorted([s for s in used_signals_resolved if s not in assigned and s not in neg_sigs])
    for sig in remaining:
        name2var[sig] = new_var()

    # 构建取反对映射（仅存储正编号的源变量）
    for neg_sig, src_sig in neg_pairs.items():
        src_res = _resolve_equivalence(src_sig, eq_pairs)
        if src_res in name2var:
            neg_map[neg_sig] = (name2var[src_res], -1)  # 源变量始终为正，符号单独存储
        if neg_sig in name2var:
            del name2var[neg_sig]

    return name2var, var_count, neg_map

def parse_blif_with_continuous_vars(blif_path):
    """BLIF解析主函数"""
    # 解析核心结构
    inputs, outputs, names_blocks, latches, used_signals, neg_pairs, eq_pairs = _parse_blif_core(blif_path)
    
    # 拆解门电路
    ands_list, xors_list = _split_names_to_ands_xors(names_blocks)
    
    # 分配变量编号（优先锁存器输出）
    name2var, var_count, neg_map = _assign_continuous_vars(
        inputs, outputs, latches, used_signals, neg_pairs, eq_pairs
    )
    
    # 映射变量编号（强制锁存器output为正）
    inputs_var, outputs_var, latches_var, ands_var, xors_var = _map_gate_signals_to_vars(
        inputs, outputs, latches, ands_list, xors_list, name2var, neg_map, eq_pairs
    )
    
    # 封装结果（二次校验锁存器output为正）
    result = BLIFParserResult()
    # 变量编号全部加1
    result.inputs = [v + 1 for v in inputs_var]
    result.outputs = [v + 1 for v in outputs_var]
    result.names_blocks = names_blocks
    result.ands = [(o + 1, i1 + 1, i2 + 1, inv) for (o, i1, i2, inv) in ands_var]
    result.xors = [(o + 1, i1 + 1, i2 + 1, inv) for (o, i1, i2, inv) in xors_var]
    # 强制校验：锁存器output必须为正
    for latch in latches_var:
        in_var, out_var, init = latch
        assert out_var > 0, f"锁存器output编号必须为正，当前为{out_var}"
        result.latches.append((out_var + 1, in_var + 1, init))
    # name2var编号加1
    result.name2var = type(name2var)((k, v + 1) for k, v in name2var.items())
    result.var_count = len(name2var)
    # neg_pairs编号加1
    result.neg_pairs = {k: (v[0] + 1, v[1]) for k, v in neg_map.items()}
    result.eq_pairs = eq_pairs

    return result

if __name__ == '__main__':
    import sys
    blif_path = '/home/lyj238/wdl/IC3/pipeLinedAdder_final.blif'
    # blif_path = '/home/lyj238/wdl/IC3/test.blif'
    try:
        parser_result = parse_blif_with_continuous_vars(blif_path)
        print("=== BLIF解析结果 ===")
        print(f"输入信号编号: {parser_result.inputs}")
        print(f"输出信号编号: {parser_result.outputs}")
        print(f"总变量数: {parser_result.var_count}")
        print(f"AND门数: {len(parser_result.ands)} | XOR门数: {len(parser_result.xors)}")
        print(f"AND门信息（o, i1, i2）: {parser_result.ands}")
        print(f"XOR门信息（o, i1, i2）: {parser_result.xors}")
        print(f"锁存器信息（input, output, init）: {parser_result.latches}")
        # 校验锁存器output均为正
        for latch in parser_result.latches:
            assert latch[1] > 0, f"锁存器output {latch[1]} 非正！"
        print("✅ 所有锁存器output编号均为正")
    except Exception as e:
        print(f"解析失败: {e}")
        sys.exit(1)



