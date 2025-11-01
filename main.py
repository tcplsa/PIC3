import sys
import os
from Aiger import *
from PDR import *

show_aig = 1

def get_file_extension(file_path):
    # 使用os.path.splitext()分割文件名和扩展名
    filename, ext = os.path.splitext(file_path)
    return filename,ext

def main(args):
    # filepath = args[0]
    filepath = "./IC3/test.aig"
    filename,ext = get_file_extension(filepath)
    print("filename=",filename)
    print("fileext=",ext)
    if ext == '.aig':
        aig = read_aig(filepath)
        if show_aig == 1:
            print("Header:", aig["M"], aig["I"], aig["L"], aig["O"], aig["A"])
            print("Bad:", aig["bad"])
            print("Latches:", aig["latches"])
            for ands in aig["ands"]:
                print("AND gate:", ands)
        result = pdr_main(aig)
    elif ext == '.aag':
        aig = read_aag(filepath)
        if show_aig == 1:
            print("Header:", aig["M"], aig["I"], aig["L"], aig["O"], aig["A"])
            print("Bad:", aig["bad"])
            print("Latches:", aig["latches"])
            for ands in aig["ands"]:
                print("AND gate:", ands)
        result = pdr_main(aig)
    else:
        print("请输入正确的文件格式")
        return
    
    print(result)


if __name__ == "__main__":
    # 将命令行参数（排除脚本名）传入main函数
    main(sys.argv[1:])