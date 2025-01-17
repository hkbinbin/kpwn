import argparse
import os
import sys
import fnmatch
import magic
import subprocess
from kpwn.utils import *
import shutil
import signal

template_path = os.path.join(os.path.expanduser("~"), ".kpwn.d")
repo_url = "https://github.com/Hkhanbing/kpwn_weapon.git"

# 创建框架 create的时候可以软链接
def init():
    print("[+] start init framework")
    if os.path.exists(template_path):
        print("[*] kpwn framework already exists")
        exit(1)
    os.makedirs(template_path)
    os.makedirs(os.path.join(template_path, "templates"))
    os.makedirs(os.path.join(template_path, "tools"))
    os.makedirs(os.path.join(template_path, "tools", "fs")) #
    os.makedirs(os.path.join(template_path, "src"))
    print("[+] init framework success")

# 创建kpwn工作目录
def create(filename):
    pwd = os.getcwd()
    if os.path.exists(os.path.join(pwd, filename)):
        print("[*] file already exists")
        exit(1)
    os.makedirs(os.path.join(pwd, filename))
    os.makedirs(os.path.join(pwd, filename, "exploit")) # exp目录
    os.makedirs(os.path.join(pwd, filename, "challenge")) # 题目目录
    os.symlink(os.path.join(template_path, "tools"), os.path.join(pwd, filename, "tools")) # 软链接
    os.symlink(os.path.join(template_path, "templates"), os.path.join(pwd, filename, "templates")) # 软链接
    os.symlink(os.path.join(template_path, "src"), os.path.join(pwd, filename, "src")) # 软链接
    print("[+] create kpwn environ successs")

# get weapon
def weapon():
    print("[+] try to get weapon")
    destination = os.path.join(template_path, "weapon")
    try:
        subprocess.run(['rm', '-rf', destination])
        subprocess.run(['git', 'clone', repo_url, destination], check=True)
        print(f'Successfully cloned {repo_url} into {destination}.')
    except subprocess.CalledProcessError as e:
        print(f'Error while cloning repository: {e}')
        exit(1)

    # 检查源文件夹是否存在
    if not os.path.exists(destination):
        print(f"Source folder '{destination}' does not exist.")
        return

    # 检查目标文件夹是否存在，如果不存在则创建
    if not os.path.exists(template_path):
        os.makedirs(template_path)

    # 深层次遍历源文件夹中的所有文件和文件夹
    for root, dirs, files in os.walk(destination):
        for file in files:
            source_file = os.path.join(root, file)
            # 计算目标文件的相对路径
            relative_path = os.path.relpath(source_file, destination)
            target_file = os.path.join(template_path, relative_path)

            # 确保目标目录存在
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            # 复制文件到目标文件夹，覆盖已存在的文件
            shutil.copy2(source_file, target_file)
            print(f"Copied '{source_file}' to '{target_file}'.")

        for dir in dirs:
            source_dir = os.path.join(root, dir)
            # 计算目标目录的相对路径
            relative_dir = os.path.relpath(source_dir, destination)
            target_dir = os.path.join(template_path, relative_dir)

            # 确保目标目录存在
            os.makedirs(target_dir, exist_ok=True)
            print(f"Ensured directory '{target_dir}' exists.")

    print("[+] weapon is up to date")

# prepare local
def local(filename):
    pwd = os.getcwd()
    if not os.path.exists(os.path.join(pwd, filename)):
        print("[*] please create first")
        exit(1)
    os.chdir(os.path.join(pwd, filename))  # 切换工作目录

    # 展开rootfs
    pattern = '*.cpio'
    matching_files = []
    
    for filename in os.listdir("challenge"):
        if fnmatch.fnmatch(filename, pattern):
            matching_files.append(filename)

    for file in matching_files:  # 理论上只有一个match
        flag_is_gzip = False
        file_type = check_file_type(os.path.join('challenge', file))
        
        if "gzip" in file_type:
            print("[+] detect gzip file: ")
            subprocess.run(['mv', os.path.join('challenge', file), os.path.join('challenge', file + '.gz')],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['gzip', '-d', os.path.join('challenge', file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            flag_is_gzip = True

        # mkdir rootfs
        subprocess.run(['mkdir', 'rootfs'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['cp', os.path.join('challenge', file), 'rootfs'],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['cpio', '-idmv', '-D', 'rootfs'], input=open(os.path.join('rootfs', file), 'rb').read(),
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(['rm', os.path.join('rootfs', file)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 处理完之后将必要的sh迁移过来 fs里面的
        subprocess.run(['cp', 'tools/fs/*', './rootfs'], shell=True,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        if flag_is_gzip:
            subprocess.run(['gzip', os.path.join('challenge', file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            subprocess.run(['mv', os.path.join('challenge', file + '.gz'), os.path.join('challenge', file)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("[+] rootfs build finish")

    # 收集必要信息写入config
    # 找寻sh
    pattern = '*.sh'
    matching_files = []

    for filename in os.listdir("challenge"):
        if fnmatch.fnmatch(filename, pattern):
            matching_files.append(filename)

    config_data = ""
    for file in matching_files:  # 理论上只有一个match
        config_data += f"boot: {file}\n"
        
    with open("config", "w") as f:
        f.write(config_data)

    print("[+] config file build finish")

def debug():
    print("[+] debug")
    with open("config", "r") as f:
        file_data = f.read()
    offset = file_data.find("boot: ")
    end = file_data.find("\n", offset)
    boot_file = file_data[offset + 6:end]
    print(f"[+] boot file: {boot_file}")
    subprocess.run(["chmod", "+x", f"{os.path.join('challenge', boot_file)}"])
    # start tmux
    print(f"[+] starting tmux")
    session_name = "kpwn-debug"
    # 先切换challenge目录
    subprocess.run(["tmux", "new-session", "-d", "-s", session_name])

    # for sh
    subprocess.run(["tmux", "send-keys", "-t", f"{session_name}:0", "cd ./challenge", "C-m"])
    subprocess.run(["tmux", "send-keys", "-t", f"{session_name}:0", f"./{boot_file}", "C-m"])

    # for gdb
    subprocess.run(["tmux", "split-window", "-h", "-t", f"{session_name}:0"])
    subprocess.run(["tmux", "send-keys", "-t", f"{session_name}:0.1", "gdb", "C-m"])

    # 捕捉信号确保退出时关闭 tmux
    signal.signal(signal.SIGINT, lambda sig, frame: signal_handler(sig, frame, session_name))
    signal.signal(signal.SIGTERM, lambda sig, frame: signal_handler(sig, frame, session_name))

    # 附加到 tmux 会话
    try:
        subprocess.run(["tmux", "attach", "-t", session_name])
    except Exception as e:
        print(f"[-] attach tmux error: {e}")
    finally:
        cleanup_tmux(session_name)

    print("[+] tmux started")


def main():
    # 创建命令行解析器
    parser = argparse.ArgumentParser(description='Generate a kernel pwn struct.')

    # 子parser
    subparsers = parser.add_subparsers(dest='command', help='Subcommands')

    # kpwn init
    subparsers.add_parser('init', help='kpwn init')

    # kpwn create
    create_parser = subparsers.add_parser('create', help='kpwn create <dirname>')
    create_parser.add_argument('dirname', help='The name of the workdir to create')

    # kpwn local
    local_parser = subparsers.add_parser('local', help='kpwn local <dirname>')
    local_parser.add_argument('dirname', help='The name of the workdir to init')

    # kpwn weapon
    weapon_parser = subparsers.add_parser('weapon', help='kpwn weapon')

    # kpwn debug
    debug_parser = subparsers.add_parser('debug', help='kpwn debug')

    # 如果没有提供参数，则打印帮助信息
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    # 解析命令行参数

    # 解析命令行参数
    args = parser.parse_args()

    if args.command == 'init':
        init()
    elif args.command == 'create':
        create(args.dirname)
    elif args.command == 'local':
        local(args.dirname)
    elif args.command == 'weapon':
        weapon()
    elif args.command == 'debug':
        debug()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
