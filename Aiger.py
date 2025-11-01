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
        typ, M, I, L, O, A = header.split()
        assert typ == "aag", f"不是有效的AAG文件，头部标识应为'aag'，实际为'{typ}'"
        M, I, L, O, A = map(int, [M, I, L, O, A])

        # 读取输入部分（I个条目，每个条目占1行）
        inputs = []
        for _ in range(I):
            input_val = int(f.readline().strip())
            inputs.append(input_val)

        # 读取锁存器部分（L个条目，每个条目占1行，每行2个整数）
        latches = []
        for _ in range(L):
            cur, nxt = map(int, f.readline().strip().split())
            latches.append({
                "current": cur, 
                "next": nxt
            })

        # 读取输出部分（O个条目，每个条目占1行）
        bad = []
        for _ in range(O):
            output_val = int(f.readline().strip())
            bad.append(output_val)

        # 读取AND门部分（A个条目，每个条目占1行，每行3个整数）
        ands = []
        for _ in range(A):
            # 每行三个整数，分别代表lhs, rhs0, rhs1
            parts = list(map(int, f.readline().strip().split()))
            assert len(parts) == 3, f"AND门行格式错误，应包含3个数，实际有{len(parts)}个"
            lhs, rhs0, rhs1 = parts
            ands.append((lhs, rhs0, rhs1))

        # 返回解析后的字典结构
        return {
            "M": M, "I": I, "L": L, "O": O, "A": A,
            "inputs": inputs,
            "latches": latches,
            "ands": ands,
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
        typ, M, I, L, O, A = header.split()
        assert typ == "aig"
        M, I, L, O, A = map(int, [M, I, L, O, A])

        
        inputs = []
        for _ in range(I):
            input_val = int(f.readline().decode.strip())
            inputs.append(input_val)

        
        latches = []
        for i in range(L):
            nxt = int(f.readline().decode().strip())
            cur = 2 * (I + i + 1)
            latches.append({"current": cur, "next": nxt})

        bad = []
        for _ in range(O):
            lit = int(f.readline().decode().strip())
            bad.append(lit)
        
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
        constraints = []
        
        return {
            "M": M, "I": I, "L": L, "O": O, "A": A,
            "inputs": [2*(i+1) for i in range(I)],
            "latches": latches,
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