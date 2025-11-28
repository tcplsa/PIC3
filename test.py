#!/usr/bin/env python3
"""
AIG 到 XAG 转换测试脚本
使用编译好的 aig_to_xag 模块进行测试
"""

import os
import sys
import tempfile

def setup_environment():
    """设置 Python 路径和环境"""
    # 添加 build 目录到 Python 路径
    build_dir = os.path.join(os.path.dirname(__file__), 'build')
    if os.path.exists(build_dir):
        sys.path.insert(0, build_dir)
        print(f"✅ 已添加构建目录到路径: {build_dir}")
    else:
        print(f"❌ 构建目录不存在: {build_dir}")
        return False
    
    return True

def test_module_import():
    """测试模块导入"""
    try:
        sys.path.append('/home/lyj238/wdl/IC3/build') 
        import aig_to_xag
        print("✅ aig_to_xag 模块导入成功")
        return aig_to_xag
    except ImportError as e:
        print(f"❌ 模块导入失败: {e}")
        return None

# def create_sample_aig_file():
#     """创建示例 AIG 文件用于测试"""
#     # 这是一个简单的 AIG 文件示例
#     aig_content = """aag 3 2 0 2 1
# 2
# 4
# 6
# 6 2 4
# i0 x0
# i1 x1
# o0 y0
# o1 y1
# """
    
#     # 创建临时文件
#     temp_dir = tempfile.gettempdir()
#     aig_file = os.path.join(temp_dir, "test.aig")
    
#     with open(aig_file, 'w') as f:
#         f.write(aig_content)
    
#     print(f"✅ 已创建测试 AIG 文件: {aig_file}")
#     return aig_file

def test_conversion(converter, input_aig):
    """测试转换功能"""
    print("\n🔧 开始测试 AIG 到 XAG 转换...")
    
    # 设置转换参数
    # converter.set_lut_size(4)
    # converter.set_optimization(True)
    
    # 测试转换为字符串
    print("📝 测试转换为字符串...")
    try:
        verilog_str = converter.convert_to_string(input_aig)
        if verilog_str:
            print("✅ 转换为字符串成功")
            print(f"生成的 Verilog 代码长度: {len(verilog_str)} 字符")
            # 可选：打印前几行代码预览
            lines = verilog_str.split('\n')[:10]
            print("Verilog 代码预览:")
            for line in lines:
                print(f"  {line}")
        else:
            print("❌ 转换为字符串失败 - 返回空字符串")
            return False
    except Exception as e:
        print(f"❌ 转换为字符串时出错: {e}")
        return False
    
    # 测试转换为文件
    print("\n💾 测试转换为文件...")
    try:
        output_file = os.path.join(tempfile.gettempdir(), "test_output.v")
        success = converter.convert_file(input_aig, output_file)
        if success:
            print(f"✅ 转换为文件成功: {output_file}")
            if os.path.exists(output_file):
                file_size = os.path.getsize(output_file)
                print(f"输出文件大小: {file_size} 字节")
            else:
                print("❌ 输出文件不存在")
        else:
            print("❌ 转换为文件失败")
            return False
    except Exception as e:
        print(f"❌ 转换为文件时出错: {e}")
        return False
    
    # 获取统计信息
    print("\n📊 获取转换统计信息...")
    try:
        stats = converter.get_stats()
        print("转换统计信息:")
        print(stats)
    except Exception as e:
        print(f"❌ 获取统计信息时出错: {e}")
    
    return True

def test_different_settings(converter, input_aig):
    """测试不同的转换设置"""
    print("\n⚡ 测试不同转换设置...")
    
    # 测试无优化转换
    print("1. 测试无优化转换...")
    converter.set_optimization(False)
    verilog_str_no_opt = converter.convert_to_string(input_aig)
    if verilog_str_no_opt:
        print("✅ 无优化转换成功")
    
    # 测试有优化转换
    print("2. 测试有优化转换...")
    converter.set_optimization(True)
    verilog_str_with_opt = converter.convert_to_string(input_aig)
    if verilog_str_with_opt:
        print("✅ 有优化转换成功")
    
    # 测试不同 LUT 大小
    print("3. 测试不同 LUT 大小...")
    for lut_size in [2, 4, 6]:
        converter.set_lut_size(lut_size)
        converter.set_optimization(True)
        try:
            verilog_str = converter.convert_to_string(input_aig)
            if verilog_str:
                print(f"✅ LUT 大小 {lut_size} 转换成功")
        except Exception as e:
            print(f"❌ LUT 大小 {lut_size} 转换失败: {e}")

def main():
    """主测试函数"""
    print("🚀 开始 AIG 到 XAG 转换测试")
    print("=" * 50)
    
    # 1. 设置环境
    # if not setup_environment():
    #     return
    
    # 2. 测试模块导入
    converter_module = test_module_import()
    if not converter_module:
        return
    
    # 3. 创建转换器实例
    try:
        converter = converter_module.AigToXagConverter()
        print("✅ AigToXagConverter 实例化成功")
    except Exception as e:
        print(f"❌ 创建转换器实例失败: {e}")
        return
    
    # 4. 创建测试 AIG 文件
    test_aig_file = "test.aig"
    if not test_aig_file:
        return
    
    # 5. 测试基本转换功能
    if not test_conversion(converter, test_aig_file):
        return
    
    # 6. 测试不同设置
    test_different_settings(converter, test_aig_file)
    
    print("\n" + "=" * 50)
    print("🎉 所有测试完成！")
    
    # 清理临时文件
    try:
        if os.path.exists(test_aig_file):
            os.remove(test_aig_file)
        output_file = os.path.join(tempfile.gettempdir(), "test_output.v")
        if os.path.exists(output_file):
            os.remove(output_file)
        print("🧹 已清理临时文件")
    except:
        pass

if __name__ == "__main__":
    main()