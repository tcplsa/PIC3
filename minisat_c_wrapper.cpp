#include "minisat/simp/SimpSolver.h"
#include "minisat/core/Solver.h"
#include <cstdint>
#include <vector>

using namespace Minisat;

#define SAT 10
#define UNSAT 20

typedef void* MinisatSolver;

class ExtendedSimpSolver : public SimpSolver {
private:
    vec<Lit> custom_assumptions;
    vec<Lit> failed_assumptions;

public:
    ExtendedSimpSolver() {
        // 启用简化功能，但我们会手动管理冻结
        use_elim = true;
        use_simplification = true;
        grow = 0;
    }
    
    void addAssumption(Lit l) {
        custom_assumptions.push(l);
        Var v = var(l);
        
        // 确保变量存在
        while (v >= nVars()) newVar();
        
        // 冻结假设变量，防止被消除
        setFrozen(v, true);
    }
    
    void clearAssumptions() {
        // 解冻所有假设变量
        for (int i = 0; i < custom_assumptions.size(); i++) {
            Var v = var(custom_assumptions[i]);
            if (v < nVars()) {
                setFrozen(v, false);
            }
        }
        
        custom_assumptions.clear();
        failed_assumptions.clear();
    }
    
    const vec<Lit>& getAssumptions() const {
        return custom_assumptions;
    }
    
    const vec<Lit>& getFailedAssumptions() const {
        return failed_assumptions;
    }
    
    bool solveWithAssumptions() {
        // 在求解前再次确保所有假设变量被冻结
        for (int i = 0; i < custom_assumptions.size(); i++) {
            Var v = var(custom_assumptions[i]);
            setFrozen(v, true);
        }
        
        failed_assumptions.clear();
        bool result = solve(custom_assumptions);
        
        // 如果UNSAT，分析冲突以找出失败假设
        if (!result && conflict.size() > 0) {
            // 从冲突子句中提取失败的假设
            for (int i = 0; i < conflict.size(); i++) {
                Lit conflict_lit = conflict[i];
                
                // 检查这个冲突文字是否在假设中
                for (int j = 0; j < custom_assumptions.size(); j++) {
                    Lit assumption_lit = custom_assumptions[j];
                    
                    // 如果变量相同且符号相反，则这个假设导致了冲突
                    if (var(assumption_lit) == var(conflict_lit) && 
                        sign(assumption_lit) != sign(conflict_lit)) {
                        failed_assumptions.push(assumption_lit);
                        break;
                    }
                }
            }
        }else if (!result && conflict.size() == 0){
            for (int j = 0; j < custom_assumptions.size(); j++) {
                Lit assumption_lit = custom_assumptions[j];
                failed_assumptions.push(assumption_lit);

            }
        }
        
        return result;
    }
    
    // 提供手动冻结/解冻方法
    void freezeVariable(Var v) {
        if (v < nVars()) {
            setFrozen(v, true);
        }
    }
    
    void unfreezeVariable(Var v) {
        if (v < nVars()) {
            setFrozen(v, false);
        }
    }
};

// 创建求解器
extern "C" MinisatSolver minisat_create() {
    ExtendedSimpSolver* solver = new ExtendedSimpSolver();
    solver->random_seed = 0;
    return solver;
}

// 释放求解器
extern "C" void minisat_destroy(MinisatSolver solver) {
    delete static_cast<ExtendedSimpSolver*>(solver);
}

// 添加子句
extern "C" bool minisat_add_clause(MinisatSolver solver, int* lits, int len) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    vec<Lit> clause;
    for (int i = 0; i < len; i++) {
        int dimacs_lit = lits[i];
        int var = abs(dimacs_lit) - 1;
        bool sign = (dimacs_lit < 0);
        while (var >= s->nVars()) s->newVar();
        clause.push(mkLit(var, sign));
    }
    return s->addClause(clause);
}

// 求解
extern "C" int minisat_solve(MinisatSolver solver) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    bool result = s->solveWithAssumptions();
    return result ? SAT : UNSAT;
}

// 设置假设
extern "C" void minisat_set_assumptions(MinisatSolver solver, int* lits, int len) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    s->clearAssumptions();  // 这会解冻之前的假设变量
    
    for (int i = 0; i < len; i++) {
        if (lits[i] == 0) break;
        int var_index = abs(lits[i]) - 1;
        bool sign = lits[i] < 0;
        
        while (var_index >= s->nVars()) {
            s->newVar();
        }
        
        Lit l = mkLit(var_index, sign);
        s->addAssumption(l);  // 这会冻结新添加的假设变量
    }
}

// 获取变量值
extern "C" int minisat_model_value(MinisatSolver solver, int var) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    if (var < 0 || var >= s->nVars()) return 0;
    
    lbool val = s->model[var];
    if (val == l_True) return 1;
    if (val == l_False) return -1;
    return 0;
}

// 获取最大变量
extern "C" int minisat_max_var(MinisatSolver solver) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    return s->nVars();
}

// 清除假设
extern "C" void minisat_clear_assumptions(MinisatSolver solver) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    s->clearAssumptions();
}

// 获取失败假设
extern "C" int* minisat_get_failed_assumptions(MinisatSolver solver, int* out_size) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    static std::vector<int> failed_lits;
    failed_lits.clear();
    
    const vec<Lit>& failed = s->getFailedAssumptions();
    for (int i = 0; i < failed.size(); i++) {
        Lit l = failed[i];
        int dimacs_lit = var(l) + 1;
        if (sign(l)) {
            dimacs_lit = -dimacs_lit;
        }
        failed_lits.push_back(dimacs_lit);
    }
    
    *out_size = failed_lits.size();
    return failed_lits.data();
}

// 手动冻结变量
extern "C" void minisat_freeze_var(MinisatSolver solver, int var) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    s->freezeVariable(var);
}

// 手动解冻变量
extern "C" void minisat_unfreeze_var(MinisatSolver solver, int var) {
    ExtendedSimpSolver* s = static_cast<ExtendedSimpSolver*>(solver);
    s->unfreezeVariable(var);
}