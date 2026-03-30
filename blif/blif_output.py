from collections import OrderedDict, defaultdict, deque
from blif_input import parse_blif_core

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

# def build_not_equiv_classes(neg_pairs):
#     """
#     构建非门等价类，每对(a, b)满足a = ~b或b = ~a，归为同一等价类。
#     返回: {代表元: [所有等价信号名]}, 以及信号->代表元的映射。
#     """
#     parent = {}
#     def find(x):
#         while parent.get(x, x) != x:
#             parent[x] = parent.get(parent[x], parent[x])
#             x = parent[x]
#         return x
#     def union(x, y):
#         px, py = find(x), find(y)
#         if px != py:
#             parent[py] = px
#     for a, b in neg_pairs.items():
#         # a = ~b 或 b = ~a
#         union(a, b)
#     # 收集等价类
#     SigPair = OrderedDict()
#     for x in set(list(neg_pairs.keys()) + list(neg_pairs.values())):
#         px = find(x)
#         SigPair[px].append(x)
#     # 信号到代表元
#     sig2rep = {x: find(x) for x in set(list(neg_pairs.keys()) + list(neg_pairs.values()))}
#     return SigPair, sig2rep

def build_not_equiv_classes(neg_pairs, eq_pairs):
    """
    构建非门等价类，每对(a, b)满足a = ~b或b = ~a，归为同一等价类。
    返回: 
        SigPair: OrderedDict{信号名: {可替换信号名: 符号(1/-1)}} （1=等价，-1=相反）
        sig2rep: dict{信号名: 代表元} （信号→代表元映射）
        sig2sign: dict{信号名: 符号(1/-1)} （信号相对代表元的符号）
    """
    parent = {}          # 并查集父节点映射：key=信号，value=父节点
    sig2sign = {}        # 信号相对父节点的符号：key=信号，value=1/-1（初始为1）

    def find(x):
        """查找代表元，同时更新符号（路径压缩时传递符号）"""
        if x not in parent:
            parent[x] = x
            sig2sign[x] = 1  # 初始：自身是代表元，符号为1
        
        # 路径压缩 + 符号传递
        if parent[x] != x:
            orig_parent = parent[x]
            root = find(parent[x])  # 递归找根节点
            # 更新父节点（路径压缩）
            parent[x] = root
            # 更新符号：x相对根节点的符号 = x相对原父节点的符号 * 原父节点相对根节点的符号
            sig2sign[x] *= sig2sign[orig_parent]
        return parent[x]

    def union(x, y, sign):
        """合并x和y（x = ~y），维护符号关系"""
        px = find(x)  # x的代表元
        py = find(y)  # y的代表元
        if px != py:
            # 合并：将py的父节点设为px，同时记录y相对px的符号（y = ~x → y的符号 = -1 * x的符号）
            parent[py] = px
            if sign == 1:
                # x的符号是sig2sign[x]（相对px），y = ~x → y相对px的符号 = -sig2sign[x]
                sig2sign[py] = -sig2sign[x]
            else:
                # x的符号是sig2sign[x]，y = x → y相对px的符号 = sig2sign[x]
                sig2sign[py] = sig2sign[x]

    # 初始化并合并所有非门对
    for a, b in neg_pairs.items():
        # a = ~b → 合并a和b，维护符号关系
        union(a, b, 1)

    for a, b in eq_pairs.items():
        # a = b → 合并a和b，维护符号关系
        union(a, b, 0)
    
    # 第一步：先按代表元收集等价类（所有信号+符号）
    root2sigs = OrderedDict()  # 代表元: {信号: 符号}
    all_signals = set(list(neg_pairs.keys()) + list(neg_pairs.values()) + list(eq_pairs.keys()) + list(eq_pairs.values()))
    for x in all_signals:
        px = find(x)  # 确保路径压缩和符号更新完成
        if px not in root2sigs:
            root2sigs[px] = OrderedDict()
        root2sigs[px][x] = sig2sign[x]

    # 第二步：构建SigPair（每个信号都作为键，对应其等价类的所有可替换信号+符号）
    SigPair = OrderedDict()
    for sig in all_signals:
        # 找到当前信号的代表元，获取整个等价类的信号+符号
        root = find(sig)
        class_sigs = root2sigs[root]
        
        # 计算当前信号相对等价类中每个信号的符号
        sig2other = OrderedDict()
        sig_self_sign = sig2sign[sig]  # 当前信号相对代表元的符号
        for other_sig, other_sign in class_sigs.items():
            if other_sig != sig:
                # 符号规则：other_sig 相对 sig 的符号 = other_sign / sig_self_sign（即 other_sig = sign * sig）
                sign = other_sign / sig_self_sign  # 1/-1（因为都是±1，等价于相乘）
                sig2other[other_sig] = int(sign)  # 转为整数
        
        SigPair[sig] = sig2other

    # 信号到代表元的映射
    sig2rep = {x: find(x) for x in all_signals}

    return SigPair, sig2rep, sig2sign

def kahn_layering(inputs, outputs, ands, xors, sig2rep):
    """
    Kahn算法分层，inputs为起点，返回每个信号的层级dict。
    """
    # 构建有向图
    graph = defaultdict(list)
    indegree = defaultdict(int)
    for o, i1, i2, _ in ands + xors:
        of = sig2rep.get(o, o)
        i1f = sig2rep.get(i1, i1)
        i2f = sig2rep.get(i2, i2)
        graph[i1f].append(of)
        graph[i2f].append(of)
        indegree[of] += 2
        indegree.setdefault(i1f, 0)
        indegree.setdefault(i2f, 0)
    for inp in inputs:
        indegree.setdefault(sig2rep.get(inp, inp), 0)
    for out in outputs:
        indegree.setdefault(sig2rep.get(out, out), 0)
    # Kahn拓扑排序分层
    layer = {}
    queue = deque()
    for node in indegree:
        if indegree[node] == 0:
            queue.append(node)
            layer[node] = 0
    while queue:
        u = queue.popleft()
        for v in graph[u]:
            indegree[v] -= 1
            if indegree[v] == 0:
                queue.append(v)
                layer[v] = layer[u] + 1
    return layer

def assign_vars_by_layer(layer_dict,sig2rep):
    """
    按层级分配变量编号，层级小的编号小，同层内部可按名字排序。
    返回: {信号名: 变量编号}
    """
    # print("分层结果：", layer_dict)
    sorted_items = sorted(layer_dict.items(), key=lambda x: (x[1], str(x[0])))
    # print("分层排序后：", sorted_items)
    name2var = OrderedDict()
    for idx, (name, l) in enumerate(sorted_items, 1):
        if l < 1e10:
            name2var[name] = idx
        else:
            try:
                name2var[name] = name2var[sig2rep.get(name, name)]*-1
            except KeyError:
                print(f"Warning: 信号{name}未分配编号，且其代表元{sig2rep.get(name, name)}也未分配编号")
                sys.exit(1)
    return name2var

def parse_blif_with_layered_vars(blif_path):
    """
    使用分层分配变量编号的BLIF解析主函数
    """
    inputs, outputs, names_blocks, latches, used_signals, neg_pairs, eq_pairs = parse_blif_core(blif_path)

    # 提取门电路
    ands_list, xors_list = _split_names_to_ands_xors(names_blocks)
    
    # 构建非门等价类
    not_pairs = {}
    for k, v in neg_pairs.items():
        not_pairs[k] = v
        not_pairs[v] = k
    equal_pairs = {}
    for k, v in eq_pairs.items():
        equal_pairs[k] = v
        equal_pairs[v] = k
    # print("neg_pairs:", not_pairs)
    # print("eq_pairs:", equal_pairs)
    SigPair, sig2rep, sig2sign = build_not_equiv_classes(not_pairs, equal_pairs)
    # print("SigPair 输出：")
    # for sig, replace_map in SigPair.items():
    #     print(f"{sig}: {dict(replace_map)}")
    
    # 获取所有涉及的信号（包括输入、输出、中间信号）
    all_signals = set(inputs + outputs)
    for o, i1, i2, _ in ands_list + xors_list:
        all_signals.update([o, i1, i2])
    for latch in latches:
        all_signals.update([latch['input'], latch['output']])
    # print("所有变量：",all_signals)
    # Kahn分层
    layer = kahn_layering(inputs, outputs, ands_list, xors_list, sig2rep)
    # 确保所有信号都有层级信息（处理未出现在门中的信号）
    for signal in all_signals:
        if signal not in layer:
            layer[signal] = 1e10  # 默认为第0层（输入层或孤立信号）
        layer["$aiger1$0b"] = 0
    # 按层级分配变量编号
    name2var = assign_vars_by_layer(layer, sig2rep)
    
    # 映射所有信号到变量编号

    def map_signal_to_var(sig_name, force_positive=False, force_update_var=None):
        """
        信号名转变量编号（处理取反）。
        force_update_var: 若指定，则将该信号及其等价/相反信号的编号全部同步为此值（正整数），并返回对应编号（考虑取反）。
        """
        original_sig = sig_name
        # 解析等价映射
        resolved_sig = _resolve_equivalence(sig_name, eq_pairs)
        # print(f"映射信号: 原始={original_sig} 解析后={resolved_sig}" )
        # force_positive为True时，自动同步所有等价/相反信号编号为正数
        if force_positive:
            # 以当前编号的绝对值为正编号进行同步
            if resolved_sig in name2var:
                update_var_number(resolved_sig, abs(name2var[resolved_sig]), name2var, SigPair, sig2rep, sig2sign)
            else:
                raise KeyError(f"信号{resolved_sig}未分配编号")
        if force_update_var is not None:
            # 直接同步所有等价/相反信号的编号
            update_var_number(resolved_sig, force_update_var, name2var, SigPair, sig2rep, sig2sign)
        if resolved_sig in name2var:
            var = name2var[resolved_sig]
        else:
            raise KeyError(f"信号{resolved_sig}未分配编号")
        return var

    def update_var_number(target_sig, new_var, name2var, SigPair, sig2rep, sig2sign):
        """
        直接修改name2var中target_sig的编号，并同步所有等价/相反信号的编号。
        target_sig: 目标信号名（不带~）
        new_var: 新的编号（正整数）
        name2var: {信号名: 变量编号}
        SigPair: {信号名: {等价/相反信号: 符号}}
        sig2rep: {信号名: 代表元}
        sig2sign: {信号名: 符号(1/-1)}
        """
        # 先更新自身
        name2var[target_sig] = new_var
        # 找到target_sig的等价类（所有等价/相反信号）
        if target_sig not in SigPair:
            return

        # 更新等价/相反信号
        for other_sig, sign in SigPair[target_sig].items():
            name2var[other_sig] = new_var * sign
        # 还要保证代表元的编号也同步
        rep = sig2rep[target_sig]
        if rep != target_sig:
            # 代表元编号 = new_var * (sig2sign[rep] / sig2sign[target_sig])
            sign = sig2sign[rep] // sig2sign[target_sig]
            name2var[rep] = new_var * sign
        # 反向：如果有信号的等价类包含target_sig，也要同步（防止SigPair只单向）
        for sig, others in SigPair.items():
            if sig == target_sig:
                continue
            if target_sig in others:
                sign = others[target_sig]
                name2var[sig] = new_var * sign
    
    # 映射输入、输出、锁存器
    # print("latches:",latches)
    inputs_var = [map_signal_to_var(s, force_positive=True) for s in inputs]
    outputs_var = [map_signal_to_var(s) for s in outputs]
    latches_var = []
    for latch in latches:
        out_var = map_signal_to_var(latch['output'], force_positive=True)
    # 映射门电路
    ands_var = []
    for out_sig, in1_sig, in2_sig, invert_out in ands_list:
        out_var = map_signal_to_var(out_sig, force_positive=True)

    xors_var = []
    for out_sig, in1_sig, in2_sig, invert_out in xors_list:
        out_var = map_signal_to_var(out_sig, force_positive=True)

    
    for latch in latches:
        # print(f"映射锁存器: input={latch['input']} output={latch['output']} init={latch['init']}")
        in_var = map_signal_to_var(latch['input'])
        out_var = map_signal_to_var(latch['output'], force_positive=True)
        latches_var.append((in_var, out_var, latch['init']))
    latches_var.sort(key=lambda x: x[1])  # 按第二个元素（out_var）升序
    # 映射门电路
    ands_var = []
    for out_sig, in1_sig, in2_sig, invert_out in ands_list:
        out_var = map_signal_to_var(out_sig, force_positive=True)
        in1_var = map_signal_to_var(in1_sig)
        in2_var = map_signal_to_var(in2_sig)
        # print(f"映射AND门: {out_sig}({out_var}) = {in1_sig}({in1_var}) AND {in2_sig}({in2_var}), invert_out={invert_out}")
        ands_var.append((abs(out_var) if invert_out else out_var, in1_var, in2_var, invert_out))
    ands_var.sort(key=lambda x: x[0])
    xors_var = []
    for out_sig, in1_sig, in2_sig, invert_out in xors_list:
        out_var = map_signal_to_var(out_sig, force_positive=True)
        in1_var = map_signal_to_var(in1_sig)
        in2_var = map_signal_to_var(in2_sig)
        xors_var.append((abs(out_var) if invert_out else out_var, in1_var, in2_var, invert_out))
    xors_var.sort(key=lambda x: x[0])  # 按第一个元素（out_var）升序
    
    # 构建结果对象
    result = BLIFParserResult()
    result.inputs = [(v // abs(v) if v != 0 else 1) * (abs(v) + 1) for v in inputs_var]
    result.outputs = [(v // abs(v) if v != 0 else 1) * (abs(v) + 1) for v in outputs_var]
    result.names_blocks = names_blocks  # 保持原始.names块不变
    result.ands = [((o // abs(o) if o != 0 else 1) * (abs(o) + 1), i1 // abs(i1) * (abs(i1) + 1), i2 // abs(i2) * (abs(i2) + 1), inv) for (o, i1, i2, inv) in ands_var]
    result.xors = [((o // abs(o) if o != 0 else 1) * (abs(o) + 1), i1 // abs(i1) * (abs(i1) + 1), i2 // abs(i2) * (abs(i2) + 1), inv) for (o, i1, i2, inv) in xors_var]
    result.latches = []
    for latch in latches_var:
        in_var, out_var, init = latch
        assert out_var > 0, f"锁存器output编号必须为正，当前为{out_var}"
        result.latches.append(((in_var // abs(in_var) if in_var != 0 else 1) * (abs(in_var) + 1), (out_var // abs(out_var) if out_var != 0 else 1) * (abs(out_var) + 1), init))
    result.name2var = name2var
    result.var_count = len(name2var)
    result.neg_pairs = neg_pairs
    result.eq_pairs = eq_pairs
    
    return result

def parse_blif_with_continuous_vars(blif_path):
    """原版BLIF解析主函数：使用连续分配变量编号"""
    
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
        used_signals_resolved = set(_resolve_equivalence(s, eq_pairs) for s in used_signals)
        latch_outputs = set()
        for latch in latches:
            sig_res = _resolve_equivalence(latch['output'], eq_pairs)
            latch_outputs.add(sig_res)
        for sig in sorted(latch_outputs):
            if sig in used_signals_resolved and sig not in name2var:
                name2var[sig] = new_var()
        for sig in inputs:
            sig_res = _resolve_equivalence(sig, eq_pairs)
            if sig_res in used_signals_resolved and sig_res not in name2var:
                name2var[sig_res] = new_var()
        neg_src = sorted(set(_resolve_equivalence(s, eq_pairs) for s in neg_pairs.values()))
        for sig in neg_src:
            if sig in used_signals_resolved and sig not in name2var:
                name2var[sig] = new_var()
        for sig in outputs:
            sig_res = _resolve_equivalence(sig, eq_pairs)
            if sig_res in used_signals_resolved and sig_res not in name2var:
                name2var[sig_res] = new_var()
        assigned = set(name2var.keys())
        neg_sigs = set(_resolve_equivalence(s, eq_pairs) for s in neg_pairs.keys())
        remaining = sorted([s for s in used_signals_resolved if s not in assigned and s not in neg_sigs])
        for sig in remaining:
            name2var[sig] = new_var()
        for neg_sig, src_sig in neg_pairs.items():
            src_res = _resolve_equivalence(src_sig, eq_pairs)
            if src_res in name2var:
                neg_map[neg_sig] = (name2var[src_res], -1)
            if neg_sig in name2var:
                del name2var[neg_sig]
        return name2var, var_count, neg_map

    def _map_signal_to_var(sig_name, name2var, neg_pairs, eq_pairs, force_positive=False):
        """信号名转变量编号（处理取反和等价）"""
        invert = False
        if sig_name.startswith('~'):
            invert = True
            sig_name = sig_name[1:]
        sig_name = _resolve_equivalence(sig_name, eq_pairs)
        if sig_name in neg_pairs:
            src_var, _ = neg_pairs[sig_name]
            var = -src_var if invert else src_var
        elif sig_name in name2var:
            var = name2var[sig_name]
            var = -var if invert else var
        else:
            raise KeyError(f"信号{sig_name}未分配编号")
        if force_positive:
            return abs(var)
        return var

    def _map_gate_signals_to_vars(inputs, outputs, latches, ands_list, xors_list, name2var, neg_pairs, eq_pairs):
        """映射所有信号到变量编号（保证锁存器output为正），并按output从小到大排序"""
        # 1. 输入/输出信号映射（无output维度，保持原顺序）
        inputs_var = [_map_signal_to_var(s, name2var, neg_pairs, eq_pairs) for s in inputs]
        outputs_var = [_map_signal_to_var(s, name2var, neg_pairs, eq_pairs) for s in outputs]

        # 2. 锁存器信号映射 + 按output变量升序排序（latches_var元素：(in_var, out_var, init)）
        latches_var = []
        for latch in latches:
            in_var = _map_signal_to_var(latch['input'], name2var, neg_pairs, eq_pairs)
            out_var = _map_signal_to_var(latch['output'], name2var, neg_pairs, eq_pairs, force_positive=True)
            latches_var.append((in_var, out_var, latch['init']))
        latches_var.sort(key=lambda x: x[1])  # 按第二个元素（out_var）升序

        # 3. 与门信号映射 + 按output变量升序排序（ands_var元素：(out_var, in1_var, in2_var, invert_out)）
        ands_var = []
        for out_sig, in1_sig, in2_sig, invert_out in ands_list:
            out_var = _map_signal_to_var(out_sig, name2var, neg_pairs, eq_pairs)
            in1_var = _map_signal_to_var(in1_sig, name2var, neg_pairs, eq_pairs)
            in2_var = _map_signal_to_var(in2_sig, name2var, neg_pairs, eq_pairs)
            ands_var.append((abs(out_var) if invert_out else out_var, in1_var, in2_var, invert_out))
        ands_var.sort(key=lambda x: x[0])  # 按第一个元素（out_var）升序
        print("映射后的AND门信息（o, i1, i2, invert_out）: ", ands_var)

        # 4. 异或门信号映射 + 按output变量升序排序（xors_var元素：(out_var, in1_var, in2_var, invert_out)）
        xors_var = []
        for out_sig, in1_sig, in2_sig, invert_out in xors_list:
            out_var = _map_signal_to_var(out_sig, name2var, neg_pairs, eq_pairs)
            in1_var = _map_signal_to_var(in1_sig, name2var, neg_pairs, eq_pairs)
            in2_var = _map_signal_to_var(in2_sig, name2var, neg_pairs, eq_pairs)
            xors_var.append((abs(out_var) if invert_out else out_var, in1_var, in2_var, invert_out))
        xors_var.sort(key=lambda x: x[0])  # 按第一个元素（out_var）升序

        return inputs_var, outputs_var, latches_var, ands_var, xors_var

    inputs, outputs, names_blocks, latches, used_signals, neg_pairs, eq_pairs = parse_blif_core(blif_path)
    ands_list, xors_list = _split_names_to_ands_xors(names_blocks)
    name2var, var_count, neg_map = _assign_continuous_vars(inputs, outputs, latches, used_signals, neg_pairs, eq_pairs)
    inputs_var, outputs_var, latches_var, ands_var, xors_var = _map_gate_signals_to_vars(inputs, outputs, latches, ands_list, xors_list, name2var, neg_map, eq_pairs)
    result = BLIFParserResult()
    result.inputs = [(v // abs(v) if v != 0 else 1) * (abs(v) + 1) for v in inputs_var]
    result.outputs = [(v // abs(v) if v != 0 else 1) * (abs(v) + 1) for v in outputs_var]
    result.names_blocks = names_blocks
    result.ands = [((o // abs(o) if o != 0 else 1) * (abs(o) + 1), i1 // abs(i1) * (abs(i1) + 1), i2 // abs(i2) * (abs(i2) + 1), inv) for (o, i1, i2, inv) in ands_var]
    result.xors = [((o // abs(o) if o != 0 else 1) * (abs(o) + 1), i1 // abs(i1) * (abs(i1) + 1), i2 // abs(i2) * (abs(i2) + 1), inv) for (o, i1, i2, inv) in xors_var]
    for latch in latches_var:
        in_var, out_var, init = latch
        assert out_var > 0, f"锁存器output编号必须为正，当前为{out_var}"
        result.latches.append((in_var, out_var, init))
    result.name2var = name2var
    result.var_count = len(name2var)
    result.neg_pairs = {k: (v[0], v[1]) for k, v in neg_map.items()}
    result.eq_pairs = eq_pairs
    return result

if __name__ == '__main__':
    import sys
    # blif_path = '/home/lyj238/wdl/IC3/pipeLinedAdder_final.blif'
    blif_path = '/home/lyj238/wdl/IC3/test2.blif'
    try:
        print("=== 按层次分配变量编号的解析结果 ===")
        parser_result = parse_blif_with_layered_vars(blif_path)
        print(f"输入信号编号: {parser_result.inputs}")
        print(f"输出信号编号: {parser_result.outputs}")
        print(f"总变量数: {parser_result.var_count}")
        print(f"AND门数: {len(parser_result.ands)} | XOR门数: {len(parser_result.xors)}")
        print(f"AND门信息（o, i1, i2）: {parser_result.ands}")
        print(f"XOR门信息（o, i1, i2）: {parser_result.xors}")
        print(f"锁存器信息（input, output, init）: {parser_result.latches}")
        for latch in parser_result.latches:
            assert latch[1] > 0, f"锁存器output {latch[1]} 非正！"
        print("✅ 所有锁存器output编号均为正")
        print(f"变量映射（信号名 -> 编号）: {list(parser_result.name2var.items())}")
        
        # print("\n=== 连续变量编号解析结果（对比）===")
        # parser_result2 = parse_blif_with_continuous_vars(blif_path)
        # print(f"总变量数: {parser_result2.var_count}")
        # print(f"变量映射前10项: {list(parser_result2.name2var.items())[:10]}")
        
    except Exception as e:
        print(f"解析失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)