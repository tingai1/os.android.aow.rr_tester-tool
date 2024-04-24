import argparse
import csv
import subprocess
import os
import re
from argparse import ArgumentParser
import platform

adb_devices = "HVA0763H"
adb = "adb -s " + adb_devices + ' '
# os.system(adb)

workdir = "."
apk_path = os.path.join(workdir, 'apk')
# adb_apth= os.path.join(workdir,'adb.exe')
aapt_path = os.path.join('bin', 'aapt.exe')
filename_list = []
bParseMode = False
bUninstallMode = False
csv_field_names = ['File Name', 'App Name', 'Package Name']
apk_result_csv = "apk/apk_info.csv"
uninstall_list = "uninstall_list.txt"


# 获取安装目录的apk包名
def get_apk_base_info(filename):
    p = subprocess.Popen(aapt_path + " dump badging " + filename,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    match = re.compile("package: name='(\S+)'").match(output.decode())
    if not match:
        # raise Exception("can't get packageinfo")
        return ""
    package_name = match.group(1)
    return package_name


def get_app_name(filename):
    # print(aapt_path + " dump badging " + apk_path + '/' + os.path.splitext(filename)[0] + '.apk')
    p = subprocess.Popen(aapt_path + " dump badging " + filename,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE,
                         stdin=subprocess.PIPE, shell=True)
    (output, err) = p.communicate()
    # print(f"get_app_name: {filename}: " + output.decode())
    match = re.compile("application-label:'(.*)'").search(output.decode("utf8", "ignore"))
    if not match:
        # raise Exception("can't get packageinfo")
        return ""
    app_name = match.group(1)

    return app_name


# 比较是否有相同包名的旧应用，若有卸载
def uninstall_old_app():
    new_package_name = []
    for filename in filename_list:
        if not filename.endswith('APK') and not filename.endswith('apk'):
            continue
        print(f"[uninstall_old_app] filename: {filename}")
        apk_name = get_apk_base_info(filename)
        # print(apk_name)
        new_package_name.append(apk_name)
    # print(new_package_name)
    # 获取已安装旧应用的包名
    old_installed_apk_name = os.popen("adb shell pm list package -3").read()
    old_package_name = []
    for line in old_installed_apk_name.splitlines():
        appname = line.replace("package:", "")
        old_package_name.append(appname)

    # print(old_package_name)

    def similarity(a, b):
        return [item for item in a if item in b]

    need_uninstall = similarity(new_package_name, old_package_name)
    if len(need_uninstall) == 0:
        print("没有重复的旧app")
    else:
        print("存在已安装旧版本，正在卸载旧版本")
        for appname in need_uninstall:
            print("正在卸载包名为%s的App" % appname)
            os.system("adb shell pm uninstall %s" % appname)
        print("所有旧版本App已经卸载完毕！...")


# 安装新应用
def install_apk():
    install_succ = 0
    install_fail = 0
    fail_list = []
    # uninstall_old_app()
    if filename_list is None:
        print(f"there is no apk to install, {apk_path} doesn't exist.")
        exit(0)

    print(f"[install_apk] filename_list: {filename_list}")
    for filename in filename_list:
        if os.path.splitext(filename)[1] == '.APK' or os.path.splitext(filename)[1] == '.apk':
            print('正在安装apk包：%s' % filename)
            p = subprocess.Popen(adb + ' install -g apk/' + filename,
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,
                                 universal_newlines=True,
                                 shell=True)
            try:
                outs = p.communicate()[0]
                if outs.find('Success') == 0:
                    print('ok\n')
                    install_succ = install_succ + 1
                else:
                    print('can not install\n')
                    install_fail = install_fail + 1
                    fail_list.append(filename)
            except Exception:
                p.kill()

    print('安装成功总数：', install_succ)
    print('安装失败总数：', install_fail)
    print('安装失败的文件有：', fail_list)


def parse_arguments():
    global adb
    global adb_devices
    global bParseMode
    global uninstall_list
    global bUninstallMode
    global apk_path
    global filename_list
    global apk_result_csv

    parser: ArgumentParser = argparse.ArgumentParser(
        description='''This a tool to install/uninstall/parse apk files under apk folder. ''',
        epilog="""Good luck!""")

    parser.add_argument('-d', '--device', type=str, default=adb_devices,
                        help=f'adb device to connect, default: {adb_devices}')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-i', '--install', type=str,
                       help='to install apk under target folder.')
    group.add_argument('-u', '--uninstall', type=str,
                       help=f'to uninstall the packages within apk_info.csv under target folder.')
    group.add_argument('-p', '--parse', type=str,
                       help=f'parse apk to apk_info.csv under target folder.')

    args = parser.parse_args()
    print(args)
    adb_devices = args.device
    adb = "adb -s " + adb_devices + ' '

    if args.install is not None:    # install mode
        print("we run in install mode.")
        apk_path = os.path.join(workdir, f'{args.install}')
        print(f"the apk folder is {apk_path}, there are {filename_list}. we parse info to {apk_result_csv}")
    elif args.parse is not None:  # parse mode
        print("we run in parse mode.")
        bParseMode = True
        apk_path = os.path.join(workdir, f'{args.parse}')
    elif args.uninstall is not None:    # uninstall mode
        print("we run in uninstall mode.")
        uninstall_list = args.uninstall
        apk_path = os.path.join(workdir, f'{args.uninstall}')
        bUninstallMode = True
    else:
        print('You must select a mode: install/uninstall/parse.')
        exit(0)
    # filename_list = os.listdir(apk_path)
    for root, dir, files in os.walk(apk_path):
        for file in files:
            filename_list.append(os.path.join(root,file))

    apk_result_csv = os.path.join(apk_path, "apk_info.csv")

    return


def parse_apk():
    result_dict = {}
    with open(apk_result_csv, 'w', newline='') as csvfile:
        csvfile.truncate(0)

        writer = csv.DictWriter(csvfile, csv_field_names)
        writer.writeheader()
        writer.writerow({'File Name': '', 'App Name': '', 'Package Name': ''})
        for filename in filename_list:
            if filename == "apk_info.csv":
                continue
            package_name = get_apk_base_info(filename)
            app_name = get_app_name(filename)
            if package_name and app_name:
                result_dict.update({"Package Name": package_name})
                start = len(apk_path) if (apk_path[-1]=='/') else len(apk_path)+1
                result_dict.update({"File Name": filename[start:]})
                result_dict.update({"App Name": app_name})
                writer.writerow(result_dict)
                print(f"[parse_apk] file name: {filename}; App name: {app_name}; Package name: {package_name}")
        print(f"[parse_apk] update result to {apk_result_csv}")
    return


def uninstall_app():
    with open(apk_result_csv, 'r') as applist:
        for item in applist:
            packagename = item.split(',')[2]
            if packagename.strip() == "Package Name" or packagename.strip() == "":
                continue
            uninstall_cmd = adb + " uninstall " + packagename
            print(uninstall_cmd + '...')
            os.system(uninstall_cmd)
    return


def main():
    global aapt_path

    os_name = platform.system()
    if os_name == "Linux":
        os.environ["LD_LIBRARY_PATH"] = "bin"
        aapt_path = os.path.join('bin', 'aapt')
        os.system(f"chmod a+x {aapt_path}")
    parse_arguments()
    if bParseMode:
        parse_apk()
    elif bUninstallMode:
        uninstall_app()
    else:
        install_apk()
    return


if __name__ == "__main__":
    main()
