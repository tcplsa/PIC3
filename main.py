import sys
import os
import shutil
from Aiger import *
from PDR import *
import time


show_aig = 0

def get_file_extension(file_path):
    # 使用os.path.splitext()分割文件名和扩展名
    filename, ext = os.path.splitext(file_path)
    return filename,ext

def main(args):
    # filepath = args[0]
    # filepath = "./testing files/2019/mann/unknown/ridecore.aig"
    filepath = "test.aig"
    filename,ext = get_file_extension(filepath)
    print("filename=",filename)
    print("fileext=",ext)
    # copy opened file into Unsolved_files (avoid duplicates)
    repo_root = os.path.dirname(os.path.abspath(__file__))
    unsolved_dir = os.path.join(repo_root, 'Unsolved_files')
    os.makedirs(unsolved_dir, exist_ok=True)
    unsolved_path = None
    try:
        import hashlib
        def file_hash(path):
            h = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    h.update(chunk)
            return h.hexdigest()

        if ext in ('.aig', '.aag'):
            src = os.path.abspath(filepath)
            candidate = os.path.join(unsolved_dir, os.path.basename(filepath))
            if os.path.exists(candidate):
                try:
                    if file_hash(src) == file_hash(candidate):
                        unsolved_path = candidate
                        print(f"File already in Unsolved_files, using: {unsolved_path}")
                    else:
                        base, suf = os.path.splitext(os.path.basename(filepath))
                        i = 1
                        while True:
                            cand = os.path.join(unsolved_dir, f"{base}_{i}{suf}")
                            if not os.path.exists(cand):
                                shutil.copy2(src, cand)
                                unsolved_path = cand
                                break
                            else:
                                if file_hash(src) == file_hash(cand):
                                    unsolved_path = cand
                                    break
                            i += 1
                except Exception:
                    # fallback: copy with unique name
                    base, suf = os.path.splitext(os.path.basename(filepath))
                    i = 1
                    while True:
                        cand = os.path.join(unsolved_dir, f"{base}_{i}{suf}")
                        if not os.path.exists(cand):
                            shutil.copy2(src, cand)
                            unsolved_path = cand
                            break
                        i += 1
            else:
                shutil.copy2(src, candidate)
                unsolved_path = candidate
                print(f"Copied to Unsolved_files: {unsolved_path}")
    except Exception as e:
        print(f"Warning: failed to copy to Unsolved_files: {e}")
    start_time = time.perf_counter()
    if ext == '.aig':
        aig = read_aig(filepath)
        if show_aig == 1:
            print("Header:", aig["M"], aig["I"], aig["L"], aig["O"], aig["A"])
            print("Bad:", aig["bad"])
            print("Latches:", aig["latches"])
            print("Constraints:", aig["constraints"])
            for ands in aig["ands"]:
                print("AND gate:", ands)
        result = pdr_main(aig)
    elif ext == '.aag':
        aig = read_aag(filepath)
        if show_aig == 1:
            print("Header:", aig["M"], aig["I"], aig["L"], aig["O"], aig["A"])
            print("Bad:", aig["bad"])
            print("Latches:", aig["latches"])
            print("Constraints:", aig["constraints"])
            for ands in aig["ands"]:
                print("AND gate:", ands)
        result = pdr_main(aig)
    else:
        print("请输入正确的文件格式")
        return
    if result == 20:
        print("The design is SAFE")
    elif result == 10:
        print("The design is UNSAFE")
    else:
        print("UnSolved")
    end_time = time.perf_counter()
    print(f"Elapsed time: {end_time - start_time:.6f} seconds")
    # If we processed an AIG/AAG file, move the copy from Unsolved_files to tested_files
    try:
        tested_dir = os.path.join(repo_root, 'tested_files')
        os.makedirs(tested_dir, exist_ok=True)
        if ext in ('.aig', '.aag') and unsolved_path:
            # decide destination in tested_files
            dst = os.path.join(tested_dir, os.path.basename(unsolved_path))
            try:
                import hashlib
                def file_hash(path):
                    h = hashlib.sha256()
                    with open(path, 'rb') as f:
                        for chunk in iter(lambda: f.read(8192), b''):
                            h.update(chunk)
                    return h.hexdigest()

                if os.path.exists(dst):
                    if file_hash(unsolved_path) == file_hash(dst):
                        # identical -- remove unsolved copy
                        os.remove(unsolved_path)
                        print(f"Already in tested_files, removed unsolved copy: {dst}")
                    else:
                        base, suf = os.path.splitext(os.path.basename(unsolved_path))
                        i = 1
                        while True:
                            candidate = os.path.join(tested_dir, f"{base}_{i}{suf}")
                            if not os.path.exists(candidate):
                                dst = candidate
                                break
                            else:
                                if file_hash(unsolved_path) == file_hash(candidate):
                                    # duplicate found
                                    os.remove(unsolved_path)
                                    dst = None
                                    print(f"Already in tested_files as {candidate}, removed unsolved copy")
                                    break
                            i += 1
                        if dst:
                            shutil.move(unsolved_path, dst)
                            print(f"Moved to tested_files: {dst}")
                else:
                    shutil.move(unsolved_path, dst)
                    print(f"Moved to tested_files: {dst}")
            except Exception:
                # fallback: move with unique name
                base, suf = os.path.splitext(os.path.basename(unsolved_path))
                i = 1
                while True:
                    candidate = os.path.join(tested_dir, f"{base}_{i}{suf}")
                    if not os.path.exists(candidate):
                        dst = candidate
                        break
                    i += 1
                shutil.move(unsolved_path, dst)
                print(f"Moved to tested_files (fallback): {dst}")
    except Exception as e:
        print(f"Warning: failed to move from Unsolved_files to tested_files: {e}")

    # print(result)


if __name__ == "__main__":
    # 将命令行参数（排除脚本名）传入main函数
    main(sys.argv[1:])