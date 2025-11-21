def aag_to_cnf(aag_file, cnf_file):
    """
    Convert AAG (ASCII AIGER) to CNF (DIMACS format),
    ignoring latches (store them separately).
    """

    with open(aag_file, "r") as f:
        lines = [l.strip() for l in f if l.strip()]

    header = lines[0].split()
    assert header[0] == "aag"

    M, I, L, O, A = map(int, header[1:])

    idx = 1
    inputs = [int(lines[idx+i]) for i in range(I)]
    idx += I
    latches = [list(map(int, lines[idx+i].split())) for i in range(L)]
    idx += L
    outputs = [int(lines[idx+i]) for i in range(O)]
    idx += O
    ands = [list(map(int, lines[idx+i].split())) for i in range(A)]

    clauses = []

    def lit2var(lit):
        """AIGER literal -> (var, sign)"""
        return lit // 2, lit % 2

    def lit2dimacs(lit):
        """AIGER literal -> CNF variable"""
        var, sign = lit2var(lit)
        return -(var+1) if sign else (var+1)

    
    for lhs, rhs0, rhs1 in ands:
        z = lit2dimacs(lhs)
        x = lit2dimacs(rhs0)
        y = lit2dimacs(rhs1)

        clauses.append([-x, -y, z])  # (¬x ∨ ¬y ∨ z)
        clauses.append([x, -z])      # (x ∨ ¬z)
        clauses.append([y, -z])      # (y ∨ ¬z)

    
    num_vars = M
    num_clauses = len(clauses)

    with open(cnf_file, "w") as f:
        f.write(f"p cnf {num_vars} {num_clauses}\n")
        for c in clauses:
            f.write(" ".join(map(str, c)) + " 0\n")

    
    latch_info = [
        {"current": cur, "next": nxt}
        for cur, nxt in latches
    ]

    print(f"Converted {aag_file} -> {cnf_file}, "
          f"{num_vars} vars, {num_clauses} clauses, "
          f"{len(latches)} latches stored separately")

    return latch_info

def read_varint(f):
    """读取 LEB128 编码的整数 (用于 AND gate delta)"""
    x, shift = 0, 0
    while True:
        b = f.read(1)
        if not b:
            raise EOFError("Unexpected EOF in varint")
        b = b[0]
        x |= (b & 0x7F) << shift
        if not (b & 0x80):
            break
        shift += 7
    return x


def read_aag(filename):
    with open(filename, "r", encoding="utf-8") as f:
        # 读取头部信息并解析
        header = f.readline().strip()
        header_fields = header.split()
        if len(header_fields) < 6:
            raise ValueError(f"头部字段不足，至少需6个，实际{len(header_fields)}个")
        if header_fields[0] != "aag":
            raise ValueError(f"头部标识错误，应为'aag'，实际'{header_fields[0]}'")
        M, I, L, O, A = map(int, header_fields[1:6])
        extended_fields = list(map(int, header_fields[6:10]))
        B, C, J, F = (extended_fields + [0]*4)[:4]
        # 读取输入部分（I个条目，每个条目占1行）
        inputs = []
        for _ in range(I):
            input_val = int(f.readline().strip())
            inputs.append(input_val)

        # 读取锁存器部分（L个条目，每个条目占1行，每行2个整数）
        latches = []
        for i in range(L):  # 用i跟踪索引，方便计算默认current（如果需要）
            # 读取一行，去除空白并分割为参数列表
            line = f.readline().strip()
            if not line:  # 处理空行（如果有）
                raise ValueError("latches行不能为空")
            parts = line.split()  # 按空格分割，支持多空格/tab分隔
            parts = [int(p) for p in parts]  # 转换为整数
            
            # 根据参数数量处理
            if len(parts) == 3:
                # 情况1：3个参数 → current, next, default
                cur, nxt, default_val = parts
                latches.append({"current": cur, "next": nxt, "default": default_val})
            elif len(parts) == 2:
                cur = 2 * (I + i + 1)
                
                nxt, default_val = parts
                latches.append({"current": cur, "next": nxt, "default": default_val})
            elif len(parts) == 1:
                # 情况2：1个参数 → 仅next，current需要手动计算（参考你之前的逻辑）
                nxt = parts[0]
                # 假设current的计算方式为：2*(I + i + 1)（根据你的业务逻辑调整）
                cur = 2 * (I + i + 1)
                latches.append({"current": cur, "next": nxt, "default": 0})
            else:
                # 异常情况：参数数量不对（既不是1也不是2）
                raise ValueError(f"latches行格式错误：'{line}'，需1到2个参数")

        # 读取输出部分（O个条目，每个条目占1行）
        output = []
        for _ in range(O):
            output_val = int(f.readline().strip())
            output.append(output_val)

        bad = []
        for _ in range(B):
            lit = int(f.readline().strip())
            bad.append(lit)
        
        constraints = []
        for _ in range(C):
            lit = int(f.readline().strip())
            constraints.append(lit)
        
        # 读取AND门部分（A个条目，每个条目占1行，每行3个整数）
        ands = []
        for _ in range(A):
            # 每行三个整数，分别代表lhs, rhs0, rhs1
            parts = list(map(int, f.readline().strip().split()))
            assert len(parts) == 3, f"AND门行格式错误，应包含3个数，实际有{len(parts)}个"
            lhs, rhs0, rhs1 = parts
            ands.append((lhs, rhs0, rhs1))

        if len(bad) == 0:
            bad = output.copy()
        
        # 返回解析后的字典结构
        return {
            "M": M, "I": I, "L": L, "O": O, "A": A, "B": B, "C": C,
            "inputs": inputs,
            "latches": latches,
            "output": output,
            "ands": ands,
            "constraints": constraints,
            "bad": bad
        }
    
    

def read_aig(filename):
    def read_varint(f):
        x, shift = 0, 0
        while True:
            b = f.read(1)
            if not b:
                raise EOFError("Unexpected EOF in varint")
            b = b[0]
            x |= (b & 0x7F) << shift
            if not (b & 0x80):
                break
            shift += 7
        return x

    with open(filename, "rb") as f:
        header = f.readline().decode().strip()
        header_fields = header.split()
        if len(header_fields) < 6:
            raise ValueError(f"头部字段不足，至少需6个，实际{len(header_fields)}个")
        if header_fields[0] != "aig":
            raise ValueError(f"头部标识错误，应为'aig'，实际'{header_fields[0]}'")
        M, I, L, O, A = map(int, header_fields[1:6])
        extended_fields = list(map(int, header_fields[6:10]))
        B, C, J, F = (extended_fields + [0]*4)[:4]
        # typ, M, I, L, O, A = header.split()
        # assert typ == "aig"
        # M, I, L, O, A = map(int, [M, I, L, O, A])

        
        inputs = []
        for _ in range(I):
            input_val = int(f.readline().decode.strip())
            inputs.append(input_val)

        
        latches = []
        for i in range(L):
            line = f.readline().decode().strip()
            parts = line.split()
            parts = [int(p) for p in parts]
            
            cur = 2 * (I + i + 1)
            
            if len(parts) == 1:
                nxt = parts[0]
                latches.append({"current": cur, "next": nxt, "default": 0})
            elif len(parts) == 2:
                nxt, default_val = parts
                latches.append({"current": cur, "next": nxt, "default": default_val})
            else:
                raise ValueError(f"latches行格式错误：{line}（需1或2个参数）")

        output = []
        for _ in range(O):
            output_val = int(f.readline().decode().strip())
            output.append(output_val)

        bad = []
        for _ in range(B):
            lit = int(f.readline().decode().strip())
            bad.append(lit)
        
        constraints = []
        for _ in range(C):
            lit = int(f.readline().decode().strip())
            constraints.append(lit)
        
        ands = []
        lhs = 2 * (I + L + 1)
        for _ in range(A):
            d0 = read_varint(f)
            d1 = read_varint(f)
            rhs0 = lhs - d0
            rhs1 = rhs0 - d1
            ands.append((lhs, rhs0, rhs1))
            lhs += 2
        '''to be finished'''
        if len(bad) == 0:
            bad = output.copy()
        
        return {
            "M": M, "I": I, "L": L, "O": O, "A": A, "B": B, "C": C,
            "inputs": [2*(i+1) for i in range(I)],
            "latches": latches,
            "output": output,
            "ands": ands,
            "constraints": constraints,
            "bad": bad  
        }


def convert_ands_to_clauses(ands):
    """
    将AND门列表转换为等价的或子句(CNF)，存储为数据结构
    
    参数:
        ands: 从read_aig获取的AND门列表，每个元素为(lhs, rhs0, rhs1)
    
    返回:
        list: 或子句的列表，每个子句是整数列表。
              例如: [[-3, 1], [-3, 2], [3, -1, -2]]
              其中负数表示变量的否定
    """
    clauses = []  # 用于存储或子句的数据结构
    
    for lhs, rhs0, rhs1 in ands:
        # 逻辑等价转换: lhs = rhs0 ∧ rhs1
        # 转换为三个或子句
        clause1 = [-lhs, rhs0]       # ¬lhs ∨ rhs0
        clause2 = [-lhs, rhs1]       # ¬lhs ∨ rhs1
        clause3 = [lhs, -rhs0, -rhs1]  # lhs ∨ ¬rhs0 ∨ ¬rhs1
        
        clauses.extend([clause1, clause2, clause3])
    
    return clauses

# latches = aag_to_cnf("test.agg","test.cnf")
# print("Latches info:")
# for latch in latches:
#     print(latch)

# aig = read_aig("test.aig")

# print("Header:", aig["M"], aig["I"], aig["L"], aig["O"], aig["A"])
# print("Bad:", aig["bad"])
# print("Latches:", aig["latches"])
# for ands in aig["ands"]:
#     print("AND gate:", ands)