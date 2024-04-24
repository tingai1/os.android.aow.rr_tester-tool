# Copyright (C) 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and your use of them is governed by the
# express license under which they were provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without
# Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties, other than those
# that are expressly stated in the License.

import glob
import os.path
import signal
import ctypes
import argparse
from argparse import ArgumentParser
import subprocess
from datetime import datetime
import time
from threading import Thread
import PIL
from PIL import Image
import readchar as readchar
import shutil
import csv
import json
from colorama import Fore, init
from zipfile import ZipFile
import re
from xml_compare import compare_xml
from update_events import update_events
from snap import take_screenshot
from util import *

adb_devices = "emulator-5554"
adb = "adb -s " + adb_devices + ' '
adb_shell = adb + 'shell '
replay_mode = True  # default in replay mode
file_event = "events.txt"  # file name to store or read events
path_event_on_device = "/data/local/tmp/"
path_rr_test_cwd = ''
path_records = "records"  # connected with path_rr_test_cwd in setup()
path_replays = "replays"  # connected with path_rr_test_cwd in setup()
path_records_pkg = ''
path_replays_pkg = ''
focus_pkg_name = ""  # to be updated in both record and replay mode
file_test_report = ''  # to combine with host name
csv_field_names = ['Package Name', 'Version', 'Result', 'CP#1', 'CP#2', 'CP#3', 'CP#4', 'CP#5', 'CP#6', 'CP#7', 'CP#8',
                   'CP#9',
                   'CP#10']
MAX_CHECK_POINTS = 10
event_channel_record_touch = ""
event_channel_replay_touch = ""
event_channel_record_keyboard = ""
event_channel_replay_keyboard = ""
record_max_35 = 0
record_max_36 = 0
replay_max_35 = 0
replay_max_36 = 0
replay_total_cnt = 0
replay_passed_cnt = 0

file_eventrec = 'eventrec'  # for arm reference device, it needs eventrec.arm version
DUT_status = 'running'

bis_arm_dev = False
file_apk_result = "apk/apk_info.csv"
apk_info_dict = {}
AoW_dir = ""
replay_speed = "1.0"
file_platform_config = "config.json"
Windows_mode = False
resolution_check = ""
density_check = ""
su_cmd = " su -c "
file_skip_reset_flag = "skip.reset.flag"
file_metadata = 'metadata.json'
swap_x_y = False
user_id = "0"
folder_apks = "apk"
scan_phone = ""
su_cmd_scan_phone = " su -c "
replay_pass_threshold = 1.0
b_integrated_with_acs = False
scan_apps_list = {}
sms_phone_adb_device_name = ""
App_DisplayID_dict = {}
focused_display_id = "0"

# the category of test results
TEST_RESULT_PASSED = 0          # "Passed"
TEST_RESULT_XML_FAILED = -1     # "Failed"
TEST_RESULT_INVALID_EVENT = -2  # "Invalid"
TEST_RESULT_SYS_CRASH = -3      # "System Crash"
TEST_RESULT_APP_CRASH = -4      # "App Crash"
TEST_RESULT_NOT_EXISTING = -5   # "Not Exists!"
TEST_RESULT_WRONG_AOW = -6      # "AoW is not right configured"
TEST_RESULT_WRONG_VERSION = -7  # "Version mismatched"


# noinspection PyBroadException
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except AttributeError:
        raise Exception("tool is not running on Windows.")


def trace_helper(func):
    def wrapper(*args, **kwargs):
        print(Fore.CYAN + func.__name__ + "()===>")
        rv = func(*args, **kwargs)
        print(Fore.BLUE + "<===" + func.__name__ + "()")
        return rv

    return wrapper


@trace_helper
def parse_arguments():
    global file_event
    global replay_mode
    global adb_devices
    global adb
    global adb_shell
    global path_records
    global path_replays
    global event_channel_record_touch
    global event_channel_replay_touch
    global event_channel_record_keyboard
    global event_channel_replay_keyboard
    global record_max_35
    global record_max_36
    global replay_max_35
    global replay_max_36
    global AoW_dir
    global replay_speed
    global Windows_mode
    global resolution_check
    global density_check
    global su_cmd
    global swap_x_y
    global user_id
    global folder_apks
    global file_platform_config
    global scan_phone
    global su_cmd_scan_phone
    global replay_pass_threshold
    global b_integrated_with_acs
    global scan_apps_list
    global sms_phone_adb_device_name
    # global focused_display_id

    # ----- read cmd options -----
    parser: ArgumentParser = argparse.ArgumentParser(
        description='''This a tool to Record and Replay test operations. ''',
        epilog="""Good luck!""")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-r', '--record', nargs='?', const="events.txt", type=str,
                       help='the file name to store events. default: events.txt')
    group.add_argument('-p', '--replay', nargs='?', const="./records", type=str,
                       help='the apk fold to run events. default: ./records')
    parser.add_argument('-d', '--device', type=str, default=adb_devices,
                        help=f'adb device to connect, default: {adb_devices}')
    parser.add_argument('-c', '--config', type=str, default='config.json',
                        help='select config file')

    args = parser.parse_args()
    print(args)
    if args.config is not None:  # select config json file
        file_platform_config = args.config
    if args.replay is not None:  # replay mode
        path_records = args.replay
        replay_mode = True
    elif args.record is not None:  # record mode
        file_event = args.record
        replay_mode = False
    # update adb related cmds
    adb_devices = args.device
    adb = "adb -s " + adb_devices + ' '
    adb_shell = adb + 'shell '  # leave space at the end for join following parts

    # ----- parse json config options -----
    try:
        with open(file_platform_config, 'r') as f:
            data = json.load(f)
            path_records = data["record_path"] if "record_path" in data else path_records
            path_replays = data["replay_path"] if "replay_path" in data else path_replays
            event_channel_record_touch = data['event_channel_record_touch'] if 'event_channel_record_touch' in data \
                else event_channel_record_touch
            event_channel_replay_touch = data['event_channel_replay_touch'] if 'event_channel_replay_touch' in data \
                else event_channel_replay_touch
            event_channel_record_keyboard = data['event_channel_record_keyboard'] if \
                'event_channel_record_keyboard' in data else event_channel_record_keyboard
            event_channel_replay_keyboard = data['event_channel_replay_keyboard'] if \
                'event_channel_replay_keyboard' in data else event_channel_replay_keyboard
            record_max_35 = data['record_max_35'] if 'record_max_35' in data else record_max_35
            record_max_36 = data['record_max_36'] if 'record_max_36' in data else record_max_36
            replay_max_35 = data['replay_max_35'] if 'replay_max_35' in data else replay_max_35
            replay_max_36 = data['replay_max_36'] if 'replay_max_36' in data else replay_max_36
            swap_x_y = data['swap_x_y'] if 'swap_x_y' in data else swap_x_y
            Windows_mode = data['Windows_mode'] if 'Windows_mode' in data else Windows_mode
            AoW_dir = data['aow_path'] if 'aow_path' in data else AoW_dir
            replay_speed = data['replay_speed'] if 'replay_speed' in data else replay_speed
            adb_devices = data['device_name'] if 'device_name' in data else adb_devices
            resolution_check = data['resolution_check'] if 'resolution_check' in data else resolution_check
            density_check = data['density_check'] if 'density_check' in data else density_check
            su_cmd = data['su_cmd'] if 'su_cmd' in data else su_cmd
            user_id = data['user_id'] if 'user_id' in data else user_id
            folder_apks = data['apk_folder'] if 'apk_folder' in data else folder_apks
            scan_phone = data['scan_phone'] if 'scan_phone' in data else scan_phone
            su_cmd_scan_phone = data['su_cmd_scan_phone'] if 'su_cmd_scan_phone' in data else su_cmd_scan_phone
            b_integrated_with_acs = data['b_integrated_with_acs'] if 'b_integrated_with_acs' in data \
                else b_integrated_with_acs
            replay_pass_threshold = data['replay_pass_threshold'] if 'replay_pass_threshold' in data \
                else replay_pass_threshold
            scan_apps_list = data['scan_apps'] if 'scan_apps' in data and type(data['scan_apps']) is dict\
                else scan_apps_list
            sms_phone_adb_device_name = data['sms_phone_adb_device_name'] if 'sms_phone_adb_device_name' in data else sms_phone_adb_device_name
            # focused_display_id = data['focused_display_id'] if 'focused_display_id' in data else focused_display_id

            adb = "adb -s " + adb_devices + ' '
            adb_shell = adb + 'shell '  # leave space at the end for join following parts
            print(f"replay_mode: {replay_mode},"
                  f"recorded_events_path:{path_records}, replay_capture_path:{path_replays},"
                  f"touch event channel:{event_channel_record_touch}=>{event_channel_replay_touch}, "
                  f"keyboard event channel: {event_channel_record_keyboard}=>{event_channel_replay_keyboard},"
                  f"swap_x_y:{swap_x_y}, "
                  f"Windows_mode:{Windows_mode}, AoW_dir:{AoW_dir},"
                  f"replay_speed:{replay_speed}, adb_devices:{adb_devices},"
                  f"resolution_check:{resolution_check}, density_check:{density_check}, su_cmd:{su_cmd}",
                  f"user_id:{user_id}, scan_phone:{scan_phone}, replay_pass_threshold:{replay_pass_threshold},"
                  f"b_integrated_with_acs: {b_integrated_with_acs}")
    except FileNotFoundError:
        print(f"{file_platform_config} is not provided, so we use default settings.")

    return


def sig_handler(_, __):  # hide unused parameter: signum, frame
    msg = "Ctrl-c was pressed. Do you really want to exit? y/n "
    print(msg, end="", flush=True)
    b_user_input = readchar.readchar().lower()
    b_user_input = str(b_user_input, 'utf-8') if isinstance(b_user_input, bytes) else b_user_input
    if b_user_input == 'y':
        exit(1)
    else:
        print("", end="\r", flush=True)
        print(" " * len(msg), end="", flush=True)  # clear the printed line
        print("    ", end="\r", flush=True)


def run_sys_cmd(cmd, bsubprocss, bret=False):
    print(Fore.MAGENTA + f"[run_sys_cmd] {cmd}")
    if bsubprocss:
        ret = subprocess.Popen(cmd, shell=True,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True, encoding='UTF-8')
        if bret:
            ret = ret.stdout.read()
            # print(f"\t output ret: {ret}")
            return ret
    else:
        return os.system(cmd)


# 1.    register signal handler;
# 2.    prepare adb;
# 3.    push eventrec for arm/x86; clear log;
# 4.    make local folders: records/replays
# 5.    update global paths/report name
@trace_helper
def setup():
    global path_rr_test_cwd
    global path_replays
    global path_records
    global bis_arm_dev
    global file_eventrec
    global adb_shell
    global file_test_report
    global path_records
    global path_replays
    global App_DisplayID_dict

    # 0. check admin mode for AoW
    if AoW_dir and not is_admin():
        print("Need to Run as Administrator for AoW platform")
        exit(-3)

    # 1. register signal handler
    os.environ["LD_LIBRARY_PATH"] = "."
    signal.signal(signal.SIGINT, sig_handler)

    # 2. make adb connected
    if not adb_detect_status():
        os.system("adb kill-server")

    # 3. handle different cmd for arm/aow: eventrec name; root cmd
    check_abi_cmd = adb_shell + "getprop ro.product.cpu.abi"
    ret = run_sys_cmd(check_abi_cmd, True, True)
    bis_arm_dev = 'arm' in ret
    if bis_arm_dev:
        file_eventrec = 'eventrec.arm'
        adb_shell = adb + 'shell ' + su_cmd  # special cmd to run adb with root rights on unlocked-user device
    # else:
    # on Aow, just run "adb root" to get root rights
    # ret = os.system(adb + " root")
    # while ret:
    #     os.system("adb kill-server")
    #     ret = os.system(adb + " root")
    os.system(adb + "wait-for-device")
    # push corresponding eventrec for recording/replaying
    os.system(adb + f"push bin/{file_eventrec} " + path_event_on_device)
    os.system(adb + "shell chmod a+x " + path_event_on_device + f"/{file_eventrec}")
    os.system(adb + "shell sync")

    # 4. mkdir records/ or replays/ if it doesn't exist
    if replay_mode is False and not os.path.exists(path_records):
        os.makedirs(path_records, 0o777)
    elif replay_mode and not os.path.exists(path_replays):
        os.makedirs(path_replays, 0o777)

    # 5. update global path value & generate report name
    path_rr_test_cwd = os.getcwd()
    path_records = os.path.join(path_rr_test_cwd, path_records)
    path_replays = os.path.join(path_rr_test_cwd, path_replays)
    # save result to RR_Results_{test_host}_{test_date}.csv"
    test_host = os.popen('hostname').read().strip()
    test_date = time.strftime("%Y%m%d_%H%M%S")
    file_test_report = os.path.join(path_replays, f"RR_Results_{test_host}_{test_date}.csv")

    # 6. setprop: this property is used to keep App rights during reset App
    # it takes effect together with patch in aosp code
    setprop_cmd = adb_shell + f"setprop skip.reset.permission 1 "
    run_sys_cmd(setprop_cmd, False)

    App_DisplayID_dict = adb_get_app_display_dict()
    print(f"App_DisplayID_dict: {App_DisplayID_dict}")

    return


# some Apps store data out of their own data folder. To do a complete reset, those files need to be deleted as well.
@trace_helper
def setup_reset_apps():
    pm_reset_cmd = adb + f"shell pm clear --user {user_id} " + focus_pkg_name
    run_sys_cmd(pm_reset_cmd, False)

    # 1 掌阅
    if focus_pkg_name == 'com.chaozh.iReaderFree':
        reset_cmd_hardcoded = adb + " shell " + su_cmd + "rm -rf /data/media/0/iReader"
    # 2 画世界
    elif focus_pkg_name == 'net.huanci.hsjpro':
        reset_cmd_hardcoded = adb + " shell " + su_cmd + "rm -rf /sdcard/HuashijiePro/Draft/*"
    else:
        time.sleep(1)  # sleep is necessary for a clean reset (ex: qq.reader)
        return
    # whenever focus app in hardcoded list, we reset
    run_sys_cmd(reset_cmd_hardcoded, False)
    return

# search packagename in apk_info.csv under apk_folder
# if found and install success, return True
# else return false
def adb_install_app(pkg_name, folder_name):
    apk_info_file = os.path.join(folder_name, "apk_info.csv")
    with open(apk_info_file, "r") as file:
        reader = csv.DictReader(file)
        for app in reader:
            if app['Package Name'] == pkg_name:
                apk_file = os.path.join(folder_name, app['File Name'])
                ret = run_sys_cmd(adb + f" install --user {user_id} " + apk_file, False, True)
                return ret
    return True


# adb uninstall app only if that app is not marked as reset-skip
def adb_uninstall_app(pkg_name):
    package_replay_path = os.path.join(path_records, pkg_name)
    if os.path.exists(os.path.join(package_replay_path, file_skip_reset_flag)):
        print(f"{pkg_name} is marked as reset skip, we don't uninstall it")
    elif not b_integrated_with_acs:
        print("actually we skip uninstalling app for debug convenience. if you want uninstall automatic, tell developer")
        # run_sys_cmd(adb_shell + f"pm uninstall --user {user_id} {pkg_name}", True, False)

# output example:
# {'3': 'null',
#  '0': 'com.tencent.launcher/.MainActivity}',
#  '7': 'com.baidu.netdisk/.ui.account.LoginRegisterActivity}'}
@trace_helper
def adb_get_app_display_dict():
    pkg_disp_dict = {}
    # adb_cmd = "adb shell dumpsys SurfaceFlinger --display-id"
    adb_cmd = adb_shell + 'dumpsys window'
    output = run_sys_cmd(adb_cmd, True, True)

    match = re.findall(r"mFocusedApp=.*", output, re.MULTILINE)
    print(f"mFocusedApp match: {match}:{len(match)}")
    package_activity = []
    for idx, item in enumerate(match):
        # package_activity.append(item.split(' ')[2])
        if len(item.split(' ')) == 4:
            # package_activity.append(item.split(' ')[2][:-1])    # -1 to exclude }
            package_activity.append(item.split(' ')[2])
        else:
            package_activity.append('null')
        # pkg_disp_dict[idx] = package_activity
    match = re.findall(r"displayId=.*", output, re.MULTILINE)
    print(f"display id match: {match}")
    print(f"package_activity: {package_activity}")
    display_id = []
    for idx, item in enumerate(match):
        display_id.append(item.split('=')[1])

    if len(display_id) != len(package_activity):
        print(f"Error with getting display id({len(display_id)}!={len(package_activity)}), exit")
        exit(-1)
    else:
        for idx, package in enumerate(package_activity):
            pkg_disp_dict[display_id[idx]] = package
    print(pkg_disp_dict)
    return pkg_disp_dict


def adb_chk_pkg_existence(pkg_name):
    check_package_cmd = adb + f"""shell " pm list package --user {user_id} | grep -e {pkg_name}$" """
    check_package = run_sys_cmd(check_package_cmd, True, True)
    if pkg_name not in check_package:
        # to finish one time in replay loop
        ret = adb_install_app(pkg_name, folder_apks)
        return ret == 0
    return True


def adb_chk_file_existence(filename):
    check_file_cmd = adb + f"""shell "ls {filename} " """
    check_file_ret = run_sys_cmd(check_file_cmd, True, True)
    if filename == check_file_ret.strip():
        return True
    return False


def adb_detect_status(reboot=False):
    if reboot:
        os.system("adb kill-server")
        time.sleep(2)
    adb_detect_cmd = adb + " get-state"
    ret = subprocess.Popen(adb_detect_cmd, shell=True, stdout=subprocess.PIPE).stdout
    adb_state = ret.read().decode().replace('\r', '').replace('\n', '')
    return adb_state == "device"


@trace_helper
def adb_get_focused_pkg_name():
    get_package_cmd = adb + """shell "dumpsys window | grep -i mFocusedApp " """
    try:
        get_packagename = run_sys_cmd(get_package_cmd, True, True)
    except IndexError:
        print("It seems no App running in foreground!")
        exit(-1)
    print(f"get_packagename: {get_packagename}")
    focused_pkg_names = re.findall(r" [0-9a-zA-Z._]+/", get_packagename, re.M)
    for i, pkg in enumerate(focused_pkg_names):
        focused_pkg_names[i] = focused_pkg_names[i].strip().strip('/')
    print(f"focused_pkg_names: {focused_pkg_names}, {type(focused_pkg_names)}")
    return focused_pkg_names


@trace_helper
def adb_get_focused_app_version():
    get_version_cmd = f"\"dumpsys package {focus_pkg_name} | grep versionName\""
    version = '0.0'
    try:
        version = run_sys_cmd(adb_shell + get_version_cmd, True, True).split("=")[1].strip()
    except IndexError:
        print("[adb] failed to get app version. adb lost?")
    return version


def adb_pull_file(src, dst):
    print(f"[adb] pull {src} to {dst}")
    count = 0
    while not adb_chk_file_existence(src) and count < 10:
        time.sleep(0.1)
        count += 1
    if count < 10:
        run_sys_cmd(adb + f"pull {src} " + f"{dst}", False)
        run_sys_cmd(adb + f"shell rm {src}", False)
        return True
    else:
        return False


# run uiautomator to dump and pull xml file to {path}/window_dump_{time_offset}.xml
# time_offset like '0012'
def adb_capture_pull_window(time_offset, path):
    dump_cmd = f'uiautomator dump --windows'
    run_sys_cmd(adb + 'shell "' + dump_cmd + '"', False)

    src_file = "/sdcard/window_dump.xml"
    dst_file = os.path.join(path, "window_dump_" + time_offset + ".xml")
    ret = adb_pull_file(src_file, dst_file)
    if not ret:
        print(Fore.RED + f"[capture xml] {time_offset}: fail to dump window")


# run screencap to capture screen and pull png file to {path}/screencap_{time_offset}.png
# time_offset like '0012'
def adb_capture_pull_screen(time_offset, path):
    #run_sys_cmd(adb + f"shell screencap -d {focused_display_id} -p " + path_event_on_device + "screencap.png", False)

    #src_file = os.path.join(path_event_on_device, "screencap.png")
    #dst_file = os.path.join(path, "screencap_" + time_offset + ".png")
    #ret = adb_pull_file(src_file, dst_file)
    #if not ret:
     #   print(Fore.RED + f"[capture screen] {time_offset}: fail to capture screen")
    take_screenshot(path + "/screencap_" + time_offset + ".png")

# clear and run logcat in background
@trace_helper
def adb_start_logcat():
    logcat_clear_cmd = adb + "logcat -c"
    run_sys_cmd(logcat_clear_cmd, False)
    logcat_start_cmd = adb_shell + f' "logcat > {path_event_on_device}rr.logcat" '
    run_sys_cmd(logcat_start_cmd, True)
    return


@trace_helper
def adb_stop_logcat(pkg_name, pkg_path):
    pids_of_logcat = run_sys_cmd(adb + f"shell pidof logcat", True, True)
    # kill logcat to avoid .log file too large
    # it may meet permission error with LogCat daemon, but it doesn't matter
    for pid in pids_of_logcat.split():
        run_sys_cmd(adb_shell + " kill -9 " + pid, False)
    log_file_local = os.path.join(pkg_path, f'{pkg_name}.logcat')
    run_sys_cmd(adb + "pull " + path_event_on_device + 'rr.logcat' + ' ' + log_file_local, False)
    return


@trace_helper
def start_app(baow, pkg_name, activity_name, target_display_id):
    # there are 3 methods to start App via adb command:
    # 1: AoW mode which calls Androws.exe to start App
    # 2: monkey command which needs package name only, but not able to select display ID
    # 3: am start which needs activity name, but could support display ID
    # on different platforms, these two methods could be chosen depends on requirements.
    # currently, AoW needs start App on display ID other than 0, but IVI hasn't that requirement.
    if baow:
        os.chdir(AoW_dir)
        pm_start_cmd = f".\Androws.exe --launch-pkg-name {pkg_name} --vm-pscreen-width 1200 " \
                       f"--vm-pscreen-height 2000 --vm-screen-width 2000 --vm-screen-height 1200"
        run_sys_cmd(pm_start_cmd, False)
        os.chdir(path_rr_test_cwd)
    elif activity_name is None:  # IVI case
        pm_start_cmd = adb + "shell " + f'"monkey --pct-syskeys 0 -p {pkg_name} ' \
                                        f'-c android.intent.category.LAUNCHER 1 &>/dev/null"'
        run_sys_cmd(pm_start_cmd, False)
    else:  # AoW case
        pm_start_cmd = adb_shell + su_cmd + f"am start -n {pkg_name}/{activity_name} " \
                                            f"--display {target_display_id}"
        run_sys_cmd(pm_start_cmd, False)
    return


def AoW_launch():
    os.chdir(AoW_dir)
    print("[AoW_launch] we are going to reboot AoW right now...")
    launch_cmd = ".\Androws.exe --launch-pkg-name com.android.settings --vm-screen-width 2000 --vm-screen-height 1200"
    run_sys_cmd(launch_cmd, True)
    os.chdir(path_rr_test_cwd)
    return


# return after adb is back
def AoW_reboot():
    global DUT_status
    if AoW_dir == "":
        print("AoW path is not set, we couldn't relaunch AoW.")
        exit(-1)

    if DUT_status == 'restarting':
        return
    print('[AoW_reboot] we are to reboot DUT...')
    DUT_status = 'restarting'
    thread1 = Thread(target=AoW_launch, args=())
    thread1.start()

    while not adb_detect_status(False):
        print("[AoW_reboot] DUT is restarting, waiting in AoW_reboot()\n")
        time.sleep(5)
    DUT_status = 'running'
    print("[AoW_reboot] DUT is back! Here we go...")
    # AoW new version doesn't support adb root anymore
    # if not bis_arm_dev:
    #     ret = os.system(adb + " root")
    #     if ret:
    #         print(f"[reboot] failed to run adb root: {ret}, it's not acceptable.")
    #         exit(-1)
    return


# 1. prepare path_records_pkg/ folder
# 2. reset App if needed
# 3. save App version
# 4. save metadata
@trace_helper
def record_setup():
    global focus_pkg_name
    global path_records_pkg
    global focused_display_id
    b_app_requires_network = True

    # 1.1 get package name
    focus_pkg_name = adb_get_focused_pkg_name()
    if not len(focus_pkg_name):
        print("[record] not on any App, to quit.")
        exit(-2)  # invalid state for record
    elif len(focus_pkg_name) > 2:
        print("[record] more than 1 app is running... pls kill one and try again")
        exit(-2)

    while True:
        msg = Fore.YELLOW + f"[record] which App do you want to record? \n {App_DisplayID_dict}"
        # print(msg, end="", flush=True)
        target_display_id = input(msg)
        if target_display_id in App_DisplayID_dict.keys():
            break
    focused_display_id = target_display_id
    focus_pkg_name = App_DisplayID_dict[focused_display_id]
    print(f"focus_pkg_name:{focus_pkg_name}, focused_display_id: {focused_display_id}")
    main_activity_name = focus_pkg_name.split('/')[1]
    focus_pkg_name = focus_pkg_name.split('/')[0]

    # 1.2 mkdir records/package_name
    path_records_pkg = os.path.join(path_records, focus_pkg_name)
    if os.path.exists(path_records_pkg):
        # clean folder
        files = glob.glob(os.path.join(path_records_pkg, '*'))
        for f in files:
            os.remove(f)
    else:
        os.mkdir(path_records_pkg, 0o777)

    # 2. reset App to new installed state if needed
    while True:
        msg = Fore.YELLOW + "[record] do you want to reset App/game before recording:  y/n?"
        print(msg, end="", flush=True)
        b_reset_app_c = readchar.readchar().lower()
        b_reset_app_c = str(b_reset_app_c, 'utf-8') if isinstance(b_reset_app_c, bytes) else b_reset_app_c
        if b_reset_app_c == 'y':
            print("Y")
            setup_reset_apps()
            start_app(AoW_dir != "", focus_pkg_name, main_activity_name, focused_display_id)
            b_reset_app = True
            break
        elif b_reset_app_c == 'n':
            print("N")
            # store configuration for replay process
            f = open(os.path.join(path_records_pkg, file_skip_reset_flag), 'w')
            f.close()
            b_reset_app = False
            break

    # 2.1 ask if App needs network
    msg = Fore.YELLOW + "[record] this app requires network:  Y/n?"
    print(msg, flush=True)
    b_user_input = readchar.readchar().lower()
    b_user_input = str(b_user_input, 'utf-8') if isinstance(b_user_input, bytes) else b_user_input
    if b_user_input == 'n':
        b_app_requires_network = False
        print("This App doesn't require network.")

    # 3. save app version
    focused_pkg_version = adb_get_focused_app_version()
    version_file = os.path.join(path_records_pkg, f"{focused_pkg_version}.ver")
    with open(version_file, 'w') as f:
        f.write('')

    # 4. save metadata json file
    # package_name/resolution/dpi/app_reset_flag/orientation/auto_rotate; internet_required
    metadata = {
        "package_name": "",
        "auto_rotate": False,
        "resolution": "1280x720",
        "orientation": "3",
        "dpi": "280",
        "internet_required": True,
        "app_reset_flag": "yes",
        "main_activity": "",
        "focused_display_id": ""
    }

    orientation_cmd = adb_shell + "settings get system user_rotation"
    orientation = run_sys_cmd(orientation_cmd, True, True).strip()
    auto_rotate_cmd = adb_shell + "settings get system accelerometer_rotation"
    auto_rotate = run_sys_cmd(auto_rotate_cmd, True, True).strip()
    wm_size_cmd = adb_shell + " wm size"
    wm_size = run_sys_cmd(wm_size_cmd, True, True)
    wm_density_cmd = adb_shell + " wm density"
    wm_density = run_sys_cmd(wm_density_cmd, True, True)
    try:
        print(f"wm_size: {wm_size}")
        wm_size = wm_size.split()[2]
        print(f"wm_density: {wm_density}")
        wm_density = wm_density.split()[2]
    except IndexError:
        raise Exception("[setup] get wm size/density failed. adb lost? need reboot?")

    metadata.update({
        "package_name": focus_pkg_name,
        "auto_rotate": auto_rotate,
        "resolution": wm_size,
        "orientation": orientation,
        "dpi": wm_density,
        "internet_required": b_app_requires_network,
        "app_reset_flag": "yes" if b_reset_app else 'no',
        "main_activity": main_activity_name,
        "focused_display_id": focused_display_id
    })
    with open(os.path.join(path_records_pkg, file_metadata), 'w') as meta_file:
        json.dump(metadata, meta_file)

    return


# 1.    start eventrec on device
# 2.    start logcat on host
# 3.    make sure use operate device in time (<0.5s)
@trace_helper
def record_start():
    # 1. kill eventrec processes and start new
    pids_of_eventrec = run_sys_cmd(adb + f"shell pidof {file_eventrec}", True, True)
    for pid in pids_of_eventrec.split():
        run_sys_cmd(adb_shell + su_cmd + " kill -9 " + pid, False)

    print("[record] start eventrec in adb shell")
    rm_event_cmd = adb_shell + " rm " + path_event_on_device + file_event
    start_event_record_cmd = adb_shell + path_event_on_device + f'{file_eventrec} ' + path_event_on_device + file_event
    run_sys_cmd(rm_event_cmd, True)
    run_sys_cmd(start_event_record_cmd, True)

    # 2. start logcat on host
    adb_start_logcat()

    # 3. wait for events generated
    time.sleep(1)  # 0.5s is allowed as the gap btw start & operation on device
    if adb_chk_file_existence(path_event_on_device + file_event):
        check_events_cmd = adb_shell + "stat " + path_event_on_device + file_event + " -c %s"
        events_size = run_sys_cmd(check_events_cmd, True, True)
        if int(events_size):
            return True
        return False  # if events.txt size = 0, no input event happened
    else:
        return False


# prepare zip file including what acs server wants


# 1.    kill eventrec and pull events file
# 2.    start logcat
# 3.    force-stop App under recording for non-acs case
# 4.    zip files for acs server
@trace_helper
def record_stop():
    print("[record] stop record (kill eventrec)")
    pid_of_eventrec = run_sys_cmd(adb + f"shell pidof {file_eventrec}", True, True)
    if pid_of_eventrec != '':
        run_sys_cmd(adb_shell + " kill -9 " + pid_of_eventrec, False)

    file_event_local = os.path.join(path_records_pkg, file_event)
    run_sys_cmd(adb + "pull " + path_event_on_device + file_event + ' ' + file_event_local, False)
    run_sys_cmd(adb + f"shell rm {path_event_on_device + file_event} ", False)

    adb_stop_logcat(focus_pkg_name, path_records_pkg)

    # force stop current app, to avoid multiple focused apps which causes incorrect focus_pkg_name
    if not b_integrated_with_acs:
        start_settings_cmd = adb_shell + f"am start -n android.settings.SETTINGS"
        run_sys_cmd(start_settings_cmd, True)
        force_stop_cmd = adb_shell + f"am force-stop {focus_pkg_name}"
        run_sys_cmd(force_stop_cmd, True)
    else:   # zip folder with event file/metadata/png/xml
        rr_zip_recorded_files()

    return


# capture QR screen and rename to qrcode.{time_offset}.{scan_app_pkg}.png
def record_cap_qrcode(time_offset, qr_type):
    # normal captured png file previously
    screencap_file = os.path.join(path_records_pkg, "screencap_" + time_offset + ".png")
    # rename to a special format file name for detection during replay
    scan_app_pkg_name = scan_apps_list[qr_type]
    qr_file = 'qrcode.' + time_offset + '.' + scan_app_pkg_name + '.png'
    qr_file = os.path.join(path_records_pkg, qr_file)
    print(f"[record] to rename {screencap_file} to QR code file: {qr_file}")
    os.rename(screencap_file, qr_file)
    return


def record_handle_sms_verification_code(time_offset):
    # normal captured png file previously
    screencap_file = os.path.join(path_records_pkg, "screencap_" + time_offset + ".png")
    # rename to a special format file name for detection during replay
    sms_file = 'sms.' + time_offset + '.png'
    sms_file = os.path.join(path_records_pkg, sms_file)
    print(f"[record] to rename {screencap_file} to sms special file: {sms_file}")
    os.rename(screencap_file, sms_file)
    return


def record_mark_perf_collector_point(time_offset):
    # normal captured png file previously
    screencap_file = os.path.join(path_records_pkg, "screencap_" + time_offset + ".png")
    # rename to a special format file name for detection during replay
    perf_file = 'perf_collector.' + time_offset + '.png'
    perf_file = os.path.join(path_records_pkg, perf_file)
    print(f"[record] to rename {screencap_file} to perf special file: {perf_file}")
    os.rename(screencap_file, perf_file)
    return


def record_event_loop():
    start_time = 0

    while True:
        msg = Fore.YELLOW + \
              "[record] please select: start(s), capture(c), wechat_scan(w), qq_scan(q), sms(m), perf(p), end(e):\n"
        print(msg, end="", flush=True)
        b_user_input = readchar.readchar().lower()
        res = str(b_user_input, 'utf-8') if isinstance(b_user_input, bytes) else b_user_input
        if res == 's':
            if start_time:
                print("[record] already started. pls capture or exit.")
                continue
            if record_start():
                now = datetime.now()
                start_time = datetime.timestamp(now)
                print("[record] recording starts successfully!")
            else:
                # as eventrec ignores the time before 1st event; user had better to click at the start of recording
                print(Fore.RED + "[record] record start fails, pls retry. (remember to touch screen at the same time!)")
        elif res == 'c' or res == 'm' or res == 'p' or res in scan_apps_list.keys():
            if start_time:
                now = datetime.now()
                capture_time_offset = '{:0>9.4f}'.format((datetime.timestamp(now) - start_time))  # sth like 0012.1234
                adb_capture_pull_window(capture_time_offset, path_records_pkg)
                adb_capture_pull_screen(capture_time_offset, path_records_pkg)
                if res == 'c':
                    pass
                elif res == 'm':
                    print(Fore.RED, "Please move focus to the verification input box and wait for enough time...")
                    record_handle_sms_verification_code(capture_time_offset)
                elif res == 'p':
                    print("put a mark here to collect performance data during replay.")
                    record_mark_perf_collector_point(capture_time_offset)
                else:
                    record_cap_qrcode(capture_time_offset, res)
            else:
                print("[record] please start record before capture.")
        elif res == 'e':
            if start_time:
                record_stop()
            exit(0)
        else:
            continue
    return


# AoW need administrator privilege to restart Androws.exe. It also needs to run in test mode to enable nav/status bars.
# Besides, the resolution & density needs to be same to reference platform.
# this function does those checks.
def replay_aow_platform_check():
    # check if tool runs on Windows for AoW, which needs administrator privilege
    if Windows_mode and not is_admin():
        raise Exception("Replay for AoW on Windows requires Administrator privilege for AoW reboot. Please Run As"
                        "Administrator and try again")

    # check if aow runs in test mode
    if not adb_chk_file_existence("/data/local/tmp/aow.autotest.platform"):
        raise Exception("AoW is not running in test mode. Please touch /data/local/tmp/aow.autotest.platform in adb "
                        "shell.")

    if resolution_check and density_check:
        # check aow screen size to make sure it's 2000*1200
        wm_size_cmd = adb_shell + " wm size"
        ret = subprocess.Popen(wm_size_cmd.split(), shell=True,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True)
        wm_size = ret.stdout.read()
        wm_density_cmd = adb_shell + " wm density"
        ret = subprocess.Popen(wm_density_cmd.split(), shell=True,
                               stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE,
                               text=True)
        wm_density = ret.stdout.read()
        try:
            wm_size = wm_size.split()[2]
            wm_density = wm_density.split()[2]

            if wm_density != density_check or \
                    (wm_size != resolution_check
                     # reverse resolution is for reference pad
                     and wm_size != resolution_check.split('x')[1] + 'x' + resolution_check.split('x')[0]):
                raise Exception("[setup] Replaying platform is not running with expected resolution & density." +
                                "run .\Androws.exe --launch-pkg-name com.android.settings --vm-screen-width 2000 \
                                --vm-screen-height 1200 and make sure density in Androws.json is 240.")
        except IndexError:
            raise Exception("[setup] get wm size/density failed. adb lost? need reboot?")


# if platform is invalid, we exit(-1) directly
@trace_helper
def replay_platform_check():
    # AoW uses itself as record platform, needn't check bars/resolution/density anymore
    # if AoW_dir:
    #     replay_aow_platform_check()
    pass


# 1.    prepare replay folder,
# 2.    check App versions
# return TEST_RESULT_WRONG_VERSION or none, or exit()
@trace_helper
def replay_pkg_setup(package_replay_path):
    if os.path.exists(package_replay_path):
        shutil.rmtree(package_replay_path)
    os.makedirs(package_replay_path, 0o777)
    recorded_pkg_path = os.path.join(path_records, focus_pkg_name)

    # check app version
    focused_pkg_version = adb_get_focused_app_version()
    recorded_app_version = ''
    # get version from *.*.*.version and compare
    for x in os.listdir(recorded_pkg_path):
        if x.endswith(".ver"):
            recorded_app_version = x.strip('.ver')
    if recorded_app_version != '' and recorded_app_version != focused_pkg_version:
        print(Fore.RED, f" App(focus_pkg_name) versions mismatched: {recorded_app_version} vs {focused_pkg_version}")
        # return TEST_RESULT_WRONG_VERSION

    # # reset display orientation
    # wid, hgt = 2000, 1200
    # for x in os.listdir(recorded_pkg_path):
    #     if x.endswith(".png"):
    #         img = PIL.Image.open(os.path.join(recorded_pkg_path, x))
    #         wid, hgt = img.size
    #         break   # each png file should have same resolution
    # user_rotation = 0 if wid > hgt else 3
    # rotation_reset_cmd_1 = adb_shell + f"settings put system accelerometer_rotation 0"
    # run_sys_cmd(rotation_reset_cmd_1, False)
    # rotation_reset_cmd_2 = adb_shell + f"settings put system user_rotation {user_rotation}"
    # run_sys_cmd(rotation_reset_cmd_2, False)
    # print(f"[replay_pkg_setup] {rotation_reset_cmd_2}")
    return


# push qr code to scan_server
# push eventrec and events if exists
# update photo database
# trigger scan_app_pkg scan replay with events
# start scan_app_pkg (put this behind replay step to unlock device first)
def replay_scan_qr_code(qrcode_png, scan_app_pkg_name):
    print(f"qr_type:{scan_app_pkg_name}, qrcode_png: {qrcode_png}")
    # 1. push qr png to another scan_app_pkg logged phone
    # non-scan app doesn't need this push
    qrcode_png_path = f"/data/media/{user_id}/DCIM/"
    push_qr_cmd = f'adb -s {scan_phone} push {qrcode_png} {qrcode_png_path}'
    run_sys_cmd(push_qr_cmd, False)

    # 2. replay scan process on that phone
    # push eventrec.scan events.scan.txt onto device
    # user needs to prepare them on scan server themselves
    scan_qr_replay = os.path.join('bin', 'scan_qr_replay')
    if not os.path.exists(scan_qr_replay):
        scan_qr_replay = os.path.join('bin', file_eventrec)
    push_scan_qr_cmd = f'adb -s {scan_phone} push {scan_qr_replay} {path_event_on_device}'
    run_sys_cmd(push_scan_qr_cmd, False)

    scan_qr_events_file = f'{scan_app_pkg_name}.scan.events'
    scan_qr_events = os.path.join('bin', scan_qr_events_file)
    if os.path.exists(scan_qr_events):
        push_scan_qr_cmd = f'adb -s {scan_phone} push {scan_qr_events} {path_event_on_device}'
        run_sys_cmd(push_scan_qr_cmd, False)
    else:
        print(f"{scan_qr_events_file} doesn't exist, we assume it's on scan_server /data/local/tmp/ already.")

    # update gallery database to show uploaded QR code
    if False:   # for arm pad only
        stop_cmd = f'adb -s {scan_phone} shell {su_cmd_scan_phone} stop'
        run_sys_cmd(stop_cmd, False)
        time.sleep(5)
        start_cmd = f'adb -s {scan_phone} shell {su_cmd_scan_phone} start'
        run_sys_cmd(start_cmd, False)
        time.sleep(30)
    else:  # non-scan app doesn't need this
        update_gallery_cmd = f'adb -s {scan_phone} shell am broadcast --user {user_id} -a ' \
                             f'android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file:///sdcard/DCIM'
        run_sys_cmd(update_gallery_cmd, False)

    # poweron_display_cmd = f'adb -s {scan_phone} shell input keyevent 26'
    # run_sys_cmd(poweron_display_cmd, False)
    # need to run events first
    chmod_x_cmd = f'adb -s {scan_phone} shell {su_cmd_scan_phone} chmod a+x {path_event_on_device}scan_qr_replay'
    run_sys_cmd(chmod_x_cmd, False)
    trigger_scan_qr_cmd = f'adb -s {scan_phone} shell {su_cmd_scan_phone} {path_event_on_device}scan_qr_replay ' \
                          f'-p {path_event_on_device}{scan_qr_events_file}'
    run_sys_cmd(trigger_scan_qr_cmd, True, False)

    start_scan_cmd = f'adb -s {scan_phone} shell monkey --pct-syskeys 0 -p {scan_app_pkg_name} ' \
                     f'-c android.intent.category.LAUNCHER 1'
    run_sys_cmd(start_scan_cmd, False)

    # 3. delete qr png
    # push_qr_cmd = f'adb -s {scan_phone} shell  {su_cmd} rm {qrcode_png_path}/{qrcode_png}'
    # run_sys_cmd(push_qr_cmd, False)
    return


def replay_get_sms_code():
    start_time = time.time()
    get_phone_time_cmd = f'adb -s {sms_phone_adb_device_name} shell date "+%s"'
    phone_check_time = run_sys_cmd(get_phone_time_cmd, True, True)
    sms_msg = "验证码：8888"
    time_out_len = 60
    while (time.time()-start_time)<time_out_len:
        time.sleep(1)
        # get_sms_cmd = f'''
        #	adb -s {sms_phone_adb_device_name} shell "content query --uri content://sms/inbox --sort 'date DESC' --where \"read='0'\" --projection date,body"
        #	'''
        get_sms_cmd = f'adb -s {sms_phone_adb_device_name} shell "content query --uri content://sms/inbox --projection date,body"'
        first_sms_msg = run_sys_cmd(get_sms_cmd, True, True)
        print(f"first_sms_msg: {first_sms_msg}")
        if first_sms_msg == '':
            continue
        first_sms_msg = first_sms_msg.splitlines()[0]
        sms_recv_time=re.findall(r"date=[\d]+", first_sms_msg, re.M)[0][5:-3] # exclude "date=" & change from ms to s
        if sms_recv_time < phone_check_time:
            continue
        print(f"first_sms_msg:{first_sms_msg}")
        verification_body = re.findall(r"body=.*", first_sms_msg, re.M)[0][5:]
        print(f"we received sms: {verification_body}")
        return verification_body
    print(f"[replay] failed to receive SMS verification within {time_out_len}s. return fake code: {sms_msg}")
    return sms_msg


def replay_parse_sms_code(sms_msg):
    code = ''
    
    match = re.search(r'(\d{4,})', sms_msg)
    if match:
        code = match.group(1)
        print(f"[sms] we get verification code: {code}")

    return code


def replay_input_verification_code(verification_code):
    input_text_cmd = f"adb -s {adb_devices} shell input text {verification_code}"
    run_sys_cmd(input_text_cmd, False, False)
    return


# 1.    start logcat
# 2.    start app
# 3.    reset orientation according to png files
# 4.    start eventrec -p
# 5.    while loop to pull xml/png
# 6.    stop logcat/wait for eventrec stop/kill App
@trace_helper
def replay_single_count(snaps, replay_pkg_path, count):
    # 1.5 start logcat
    adb_start_logcat()

    # update replay_pkg_path to replay_pkg_path/loop_{count} to avoid files overwritten
    if count > 0:  # this is in a loop mode
        replay_pkg_path_c = os.path.join(replay_pkg_path, f'loop_{count + 1}')
        if os.path.exists(replay_pkg_path_c):
            shutil.rmtree(replay_pkg_path_c)
        os.makedirs(replay_pkg_path_c, 0o777)
        replay_pkg_path = replay_pkg_path_c  # replay replay_pkg_path with a sub folder {loop_i) in it

    # 2. start App
    print("[replay] start: " + focus_pkg_name)

    with open(os.path.join(path_records_pkg, file_metadata), 'r') as f:
        data = json.load(f)
        main_activity_name = data["main_activity"] if "main_activity" in data else "invalid activity name"
        orientation = data["orientation"] if "orientation" in data else "3"
        auto_rotate = data["auto_rotate"] if "auto_rotate" in data else "1"
        orientation_cmd = adb_shell + f"settings put system user_rotation {orientation}"
        run_sys_cmd(orientation_cmd, False, False)
        auto_rotate_cmd = adb_shell + f"settings put system accelerometer_rotation {auto_rotate}"
        run_sys_cmd(auto_rotate_cmd, False, False)

    start_app(AoW_dir != "", focus_pkg_name, main_activity_name, focused_display_id)

    # reset display orientation
    wid, hgt = 2000, 1200
    recorded_pkg_path = os.path.join(path_records, focus_pkg_name)
    for x in os.listdir(recorded_pkg_path):
        if x.endswith(".png"):
            try:
                img = PIL.Image.open(os.path.join(recorded_pkg_path, x))
                wid, hgt = img.size
            except PIL.UnidentifiedImageError:
                print(f'invalid image file: {x}')
                wid, hgt = 0, 0
            break  # each png file should have same resolution (? seems no)
    if wid and hgt: # only when png is valid, we update rotation setting
        user_rotation = 0 if wid > hgt else 3
        rotation_reset_cmd_1 = adb_shell + f"settings put system accelerometer_rotation 0"
        run_sys_cmd(rotation_reset_cmd_1, False)
        rotation_reset_cmd_2 = adb_shell + f"settings put system user_rotation {user_rotation}"
        run_sys_cmd(rotation_reset_cmd_2, False)
        print(f"[replay_setup] {rotation_reset_cmd_2}")

    # waiting & system crash detect #1
    for i in range(10, 0, -1):
        print(f"[replay] waiting for App run up: {i}")
        time.sleep(1)  # wait until app starts up
        if not adb_detect_status():
            print("[replay] DUT lost during app start, to return and reboot AoW")
            adb_stop_logcat(focus_pkg_name, replay_pkg_path)
            return TEST_RESULT_SYS_CRASH

    # 3. start eventrec -p events.txt in background
    speed_option = " " if bis_arm_dev else f" -s {replay_speed} "  # only x86 version support speed control
    max_35_36_option = f" -m {record_max_35} {record_max_36} {replay_max_35} {replay_max_36}" \
        if record_max_35 and record_max_36 and replay_max_35 and replay_max_36 else ""

    start_event_replay_cmd = adb_shell + path_event_on_device + f"{file_eventrec} " \
        + f'-p {path_event_on_device}{file_event} ' + speed_option + max_35_36_option
    run_sys_cmd(start_event_replay_cmd, True)
    event_play_start_time = time.time()  # event replay starts now

    # 4. while loop: sleep & capture windows/screen to replay folder
    for capture_point in snaps:
        # system crash detect #2
        if not adb_detect_status():
            print("[replay] DUT lost during replay capture points, to reboot at the end of this test case")
            adb_stop_logcat(focus_pkg_name, replay_pkg_path)
            return TEST_RESULT_SYS_CRASH

        # app crash detect
        if focus_pkg_name not in adb_get_focused_pkg_name():
            if "com.tencent.mm" not in adb_get_focused_pkg_name():
                print(f"[replay] App crashes during replay capture points, stop replaying on {focus_pkg_name}")
                adb_stop_logcat(focus_pkg_name, replay_pkg_path)
                return TEST_RESULT_APP_CRASH
        
        while (time.time() - event_play_start_time) < capture_point * float(replay_speed):
            time.sleep(0.1)

        # check if a checkpoint of QR scan
        pattern = 'qrcode.*' + str(capture_point) + '*.png'    # match 3rd party scan app case
        qrcode_png = glob.glob(os.path.join(recorded_pkg_path, pattern))
        # check if a checkpoint of SMS verification code
        pattern = 'sms.*' + str(capture_point) + '*.png'
        sms_png = glob.glob(os.path.join(recorded_pkg_path, pattern))
        print(f"pattern:{pattern}; sms_png:{sms_png}")
        pattern = 'perf_collector.*' + str(capture_point) + '*.png'
        perf_png = glob.glob(os.path.join(recorded_pkg_path, pattern))
        print(f"pattern:{pattern}; perf_png:{perf_png}")
        if len(qrcode_png) == 1:
            print(f"we got qr code png: {qrcode_png} with {pattern} under {recorded_pkg_path}")
            # we should scan qr code here, but we need to pull the latest qr code rather than use the recorded one
            adb_capture_pull_screen("QR", '.')
            up_to_date_qrcode_png = 'screencap_QR.png'
            # extract pkg name from png file name, ex: get 'com.tencent.qq' from 'qrcode.0003.1234.com.tencent.qq.png'
            scan_app_pkg_name = os.path.basename(qrcode_png[0])[17:-4]
            replay_scan_qr_code(up_to_date_qrcode_png, scan_app_pkg_name)
            # os.remove(qrcode_png[0])
            # even for qr code case, we still need capture xml for further result check
        elif len(sms_png) == 1:
            print(f"we got sms png: {sms_png} with {pattern} under {recorded_pkg_path}")
            sms_msg = replay_get_sms_code()
            verification_code = replay_parse_sms_code(sms_msg)
            replay_input_verification_code(verification_code)
            # os.remove(qrcode_png[0])
            # even for qr code case, we still need capture xml for further result check
        elif len(perf_png) == 1:
            # @Tongxian to call his function here. TODO
            pass
        else:
            print("[replay] capture at point " + str(capture_point))
            capture_point_fmt = '{:0>9.4f}'.format(capture_point)
            adb_capture_pull_window(str(capture_point_fmt), replay_pkg_path)
            adb_capture_pull_screen(str(capture_point_fmt), replay_pkg_path)        


    # 5. eventrec -p should stop
    print("[replay] wait for eventrec to stop")
    pid_of_eventrec = run_sys_cmd(adb + f"shell pidof {file_eventrec}", True, True)
    while pid_of_eventrec != "":
        pid_of_eventrec = run_sys_cmd(adb + f"shell pidof {file_eventrec}", True, True)
        time.sleep(0.1)
        # crash detect #3
        if not adb_detect_status():
            print("[replay] DUT lost during waiting replay finish, to reboot at the end of this test case")
            adb_stop_logcat(focus_pkg_name, replay_pkg_path)
            return TEST_RESULT_SYS_CRASH

    # 5.5 stop logcat
    adb_stop_logcat(focus_pkg_name, replay_pkg_path)
            
    # 6. 1/2 we saw aow unstable during continue replay, force-stop app here
    if not b_integrated_with_acs:
        force_stop_cmd = adb_shell + f"am force-stop {focus_pkg_name}"
        run_sys_cmd(force_stop_cmd, True)
    return


# 1.    translate events.txt from records/pkg/
# 2.    push to device
# 3.    generate snaps[]
@trace_helper
def replay_prepare_events(recorded_pkg_path):
    # 1. find records\{apk_package}\events.txt; translate it if event channel different
    recorded_event_file = os.path.join(recorded_pkg_path, file_event)
    if not os.path.exists(recorded_event_file):  # shouldn't happen:
        print("[replay] events doesn't exist under " + recorded_pkg_path + "! pls pass the right path of events.")
        return TEST_RESULT_INVALID_EVENT
    to_update_event_channels = dict()
    # translate events.txt to match current display size/input devices
    if len(event_channel_record_touch) and len(event_channel_replay_touch) \
            and event_channel_record_touch != event_channel_replay_touch:
        to_update_event_channels.update({f"{event_channel_record_touch}": f"{event_channel_replay_touch}"})
    if len(event_channel_record_keyboard) and len(event_channel_replay_keyboard) \
            and event_channel_record_keyboard != event_channel_replay_keyboard:
        to_update_event_channels.update({f"{event_channel_record_keyboard}": f"{event_channel_replay_keyboard}"})

    if len(to_update_event_channels):
        print(f"[replay] to update event channel for replay: {to_update_event_channels}")
        new_events_file = os.path.join(path_replays_pkg, file_event)
        ret = update_events(to_update_event_channels, swap_x_y, recorded_event_file, new_events_file)
        if ret == TEST_RESULT_INVALID_EVENT:  # shouldn't happen
            return ret
    else:
        new_events_file = recorded_event_file

    # 2. push events.txt to device
    print("[repay] push updated events.txt to device")
    push_event_cmd = adb + "push " + new_events_file + " " + os.path.join(path_event_on_device, file_event)
    run_sys_cmd(push_event_cmd, False)

    # 3. sort snap files *0012*...; generate sleep intervals
    windows_dum_files = [f for f in os.listdir(recorded_pkg_path) if re.match(r'window.*[0-9]*.xml', f)]
    if len(windows_dum_files) == 0:
        print(f"no dumped window found in {recorded_pkg_path}, are you sure it's expected?")
    snaps = []
    for file_name in windows_dum_files:
        try:
            capture_time: float = float(file_name[12:21])
        except IndexError:  # shouldn't arrive here
            capture_time = 0.0  # to suppress pycharm warning
            print(f"{file_name} is invalid, capture time: {capture_time}. "
                  f"it should contain capture time like window_dump_0027.0704.xml")
            exit(-1)
        snaps.append(capture_time)
    snaps.sort()
    return snaps


# 1.    push events.txt to device
# 2.    check if loop mode
@trace_helper
def replay_event_loop(recorded_pkg_path):
    snaps = replay_prepare_events(recorded_pkg_path)
    count_after_login = 0
    # check if [1234].loop exists
    replay_count = 1
    for x in os.listdir(recorded_pkg_path):
        if x.endswith('.loop'):
            loop_file_name = x.strip('.loop')
            if loop_file_name.isdigit():
                replay_count = int(loop_file_name)
                print(f"[replay] we are to repeat replaying {focus_pkg_name} for {replay_count} times")

    # replay loop (at lease once)
    ret_summary = True
    for count in range(replay_count):
        # 1. reset App to new installed state, only when skip_reset_flag_file doesn't exit
        if not os.path.exists(os.path.join(path_records_pkg, file_skip_reset_flag)):
            setup_reset_apps()
        else:
            print("[replay_single_count] skip reset app")
        ret = replay_single_count(snaps, path_replays_pkg, count)
        ret = verify_replay_result(ret, focus_pkg_name, recorded_pkg_path, path_replays_pkg, count)
        b_login_ok = ret  # if replay is successful, we think login is done.
        ret_summary = ret_summary & ret  # per ivi, only all passed is considered as passed.
        count_after_login = replay_count - 1 - count
        if not b_login_ok:
            print("[replay_single_count] skip reset app but not login, we continue trying before_login events")
            continue
        else:
            post_recorded_pkg_path = recorded_pkg_path + "_after_login"
            file_skip_reset_flag_post = os.path.join(post_recorded_pkg_path, file_skip_reset_flag)
            if os.path.exists(file_skip_reset_flag_post):
                print(f"as login succeed, and we have {file_skip_reset_flag_post}, we are to switch to that.")
                break   # we are to switch to 2nd events folder
    # replay events of post login
    recorded_pkg_path = recorded_pkg_path+"_after_login"        # this is the rule of naming events folder after login
    if os.path.exists(recorded_pkg_path):
        replay_pkg_path = path_replays_pkg + "_after_login"
        replay_pkg_setup(replay_pkg_path)
        snaps = replay_prepare_events(recorded_pkg_path)
        if snaps != TEST_RESULT_INVALID_EVENT and len(snaps) != 0:
            print(Fore.YELLOW + f"got 2nd events folder, we are switching to that: ", recorded_pkg_path,
                  f" with {count_after_login} loops")
            for count in range(count_after_login):
                print(Fore.BLACK + f"replay {recorded_pkg_path} with {count}/{count_after_login}")
                ret = replay_single_count(snaps, replay_pkg_path, count)
                ret = verify_replay_result(ret, focus_pkg_name + "_after_login", recorded_pkg_path, replay_pkg_path,
                                           count)
                ret_summary = ret_summary & ret  # per ivi, only all passed is considered as passed.

    return ret_summary  # True(Passed) or False(Failed)


def replay_retries(retry_times=1):
    replay_ret = False
    recorded_package_path = os.path.join(path_records, focus_pkg_name)
    for count in range(retry_times):
        replay_ret = replay_event_loop(recorded_package_path)
        if replay_ret:  # skip the following loop if passed
            break
    return replay_ret


# check replay_result, compare xml and update report
@trace_helper
def verify_replay_result(replay_result, pkg_name, record_pkg_path, replay_pkg_path, count):
    global replay_total_cnt
    global replay_passed_cnt

    if count > 0:  # this is in a loop mode
        replay_pkg_path_c = os.path.join(replay_pkg_path, f'loop_{count + 1}')
        if not os.path.exists(replay_pkg_path_c):
            print(f"{replay_pkg_path_c} doesn't exist, something wrong, we are to quit.")
        replay_pkg_path = replay_pkg_path_c  # replay replay_pkg_path with a sub folder {loop_i) in it

    replay_total_cnt += 1
    print(f"[verify_replay_result] replay_total_cnt++: {replay_total_cnt}")

    # go through replay/ folder
    replay_ret = True
    result_dict = {"Package Name": pkg_name}
    i = 0
    xml_count = 0
    screencap_count = 0

    # collect app version info
    version = adb_get_focused_app_version()
    result_dict.update({"Version": version})

    if replay_result == TEST_RESULT_INVALID_EVENT:  # events.txt doesn't exist
        result_dict.update({"Result": "Invalid"})
        print("[verify] events.txt doesn't exist")
        replay_ret = False
    elif replay_result == TEST_RESULT_SYS_CRASH:  # AoW system crashed
        result_dict.update({"Result": "System Crash"})
        print("[verify] receive crash, to reboot")
        if AoW_dir:
            AoW_reboot()  # this is the only case of reboot DUT
        replay_ret = False
    elif replay_result == TEST_RESULT_APP_CRASH:  # App crashed
        result_dict.update({"Result": "App Crash"})
        print("[verify] App crashed")
        replay_ret = False
    elif replay_result == TEST_RESULT_WRONG_VERSION:  # App version mismatched
        result_dict.update({"Result": "Version Mismatched"})
        print("[verify] App Version Mismatched")
        replay_ret = False
    else:
        time.sleep(2)  # wait for the last xml to be pulled
        for x in os.listdir(replay_pkg_path):
            if x.endswith(".xml"):
                xml_count += 1
            if x.endswith(".png"):
                screencap_count += 1
        if xml_count == screencap_count:
            passed_xml_i = 0
            for x in os.listdir(replay_pkg_path):
                if x.endswith(".xml"):
                    # prepare screen_***.png.lv/rv in replay folder
                    cp_png_filename = 'screencap_' + '.'.join(x.split('_')[2].split('.')[:2]) + '.png'
                    record_png_file = os.path.join(record_pkg_path, cp_png_filename)
                    # for qr/sms case, the png file name is not the usual format
                    if not os.path.exists(record_png_file):
                        print(f"this is not a normal capture point, we skip: {x}")
                        continue
                    # verify xml: 0  window_dump_0043.2264.xml
                    print(f"verify xml: {i}  {x}")
                    i += 1
                    if i > MAX_CHECK_POINTS:
                        print(f"[verify] check points exceeds the max value: {MAX_CHECK_POINTS}")
                        replay_ret = False
                        break
                    if os.path.exists(os.path.join(record_pkg_path, x)):
                        # todo: need to pass the focused_display_id of both record and replay to xml compare logic
                        ret = compare_xml(os.path.join(record_pkg_path, x),
                                          os.path.join(replay_pkg_path, x),
                                          focused_display_id)
                        result_dict.update({f"CP#{i}": str(ret)})
                        if ret:
                            passed_xml_i += 1
                        else:
                            # prepare screen_***.png.lv/rv in replay folder
                            cp_png_filename = 'screencap_'+'.'.join(x.split('_')[2].split('.')[:2]) + '.png'
                            record_png_file = os.path.join(record_pkg_path, cp_png_filename)
                            # for qr/sms case, the png file name is not the usual format
                            if not os.path.exists(record_png_file):
                                qr_png_filename = 'qr.' + '.'.join(x.split('_')[2].split('.')[:2]) + '.png'
                                qr_png_filename = os.path.join(record_pkg_path, qr_png_filename)
                                if os.path.exists(qr_png_filename):
                                    record_png_file = qr_png_filename
                                    print(f" this is a checkpoint with qr code. qr_png_filename: {qr_png_filename}")
                                else:
                                    sms_png_filename = 'sms.' + '.'.join(x.split('_')[2].split('.')[:2]) + '.png'
                                    sms_png_filename = os.path.join(record_pkg_path, sms_png_filename)
                                    record_png_file = sms_png_filename
                                    print(
                                        f"this is a checkpoint with sms verification. sms_png_filename: {sms_png_filename}")

                            replay_png_file = os.path.join(replay_pkg_path, cp_png_filename)
                            shutil.copyfile(record_png_file,
                                            os.path.join(replay_pkg_path,
                                                         '.'.join(cp_png_filename.split('.')[:-1]) + '.png.lv'))
                            shutil.copyfile(replay_png_file,
                                            os.path.join(replay_pkg_path,
                                                         '.'.join(cp_png_filename.split('.')[:-1]) + '.png.rv'))
                            print(f"[replay] get mismatch on {x}, we save png.lv/rv for reference.")

                        # replay_ret &= ret # new pass rules: pass rate >= replay_pass_threshold
            compare_xml_ret = (passed_xml_i/i) >= replay_pass_threshold if i != 0 else True
            replay_ret &= compare_xml_ret
            replay_ret &= compare_xml_ret
        else:
            print(f"[verify] got {xml_count} xml files but {screencap_count} screencap, window dump failed?")
            replay_ret = False
        if replay_ret:
            replay_passed_cnt += 1
            print(f"[verify_replay_result] replay_passed_cnt++: {replay_passed_cnt}")
        # TEST_RESULT_PASSED or TEST_RESULT_XML_FAILED
        result_dict.update({"Result": "Passed" if replay_ret else "Failed"})

    with open(file_test_report, 'a', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, csv_field_names)
        writer.writerow(result_dict)
        print(f"[verify] update result to {file_test_report}")

    return replay_ret


def rr_zip_recorded_files():
    with ZipFile(os.path.join(path_records, f'{focus_pkg_name}.record.zip'), 'w') as zipfile:
        for file in os.listdir(path_records_pkg):
            # add what files you want to zip file here
            if file.endswith(".xml") or file == file_event or file == file_metadata:
                full_path = os.path.join(path_records_pkg, file)
                zipfile.write(full_path, arcname=file)
    return


# if passed cp#/total cp# >= threshold_val, then we regard the test case is passed.
def rr_set_threshold(threshold_val):
    global replay_pass_threshold
    replay_pass_threshold = threshold_val
    print(f"set threshold of checkpoint pass rate to {threshold_val}")
    return


def rr_replay_one_package(pkg):
    global focus_pkg_name
    global path_replays_pkg
    global path_records_pkg
    global replay_total_cnt

    recorded_package_path = os.path.join(path_records, pkg)
    if os.path.isdir(recorded_package_path) and not recorded_package_path.endswith("_after_login"):
        focus_pkg_name = pkg
        print(f"[replay] switch to {pkg}")
        # events.txt is mandatory for each replay-able folder
        if os.path.exists(os.path.join(recorded_package_path, 'events.txt')):
            if adb_chk_pkg_existence(pkg):  # same app should exist on DUT
                path_replays_pkg = os.path.join(path_replays, pkg)
                path_records_pkg = os.path.join(path_records, pkg)
                replay_pkg_setup(path_replays_pkg)
                replay_ret = replay_event_loop(recorded_package_path)
                print("[replay] Test result: ", " Passed!" if replay_ret else "Failed!!")
                # we saw aow unstable during continue replay, delay a while here
                time.sleep(10)
                # retry logic for stable result
                if replay_ret or replay_ret in [TEST_RESULT_INVALID_EVENT]:  # such failures needn't retry
                    adb_uninstall_app(pkg)
                    return
                # use loop mode instead, we don't retry anymore
                # retry_ret = replay_retries(0)
                # print("[replay retried] Test result: " + " Passed!" if retry_ret else "Failed!!")
                adb_uninstall_app(pkg)
            else:
                replay_total_cnt += 1
                print(f"[main] replay_total_cnt++: {replay_total_cnt}")
                result_dict = {"Package Name": pkg}
                # TEST_RESULT_NOT_EXISTING
                result_dict.update({"Result": "Not Exists!"})
                with open(file_test_report, 'a', newline='') as csv_file:
                    writer = csv.DictWriter(csv_file, csv_field_names)
                    writer.writerow(result_dict)
                print(f"[replay] Test result: {pkg} does not exist on platform.")
                return
        else:
            print(f"[replay] switch to {pkg} but events.txt is not found, skip.")
    return


def rr_replay_setup():
    replay_platform_check()
    # prepare the head of csv record: package name,,result,,check point 1,,check point 2,,check point 3
    with open(file_test_report, 'w', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=csv_field_names)
        writer.writeheader()
        writer.writerow({'Package Name': '', 'Version': '', 'Result': '', 'CP#1': '', 'CP#2': '', 'CP#3': ''})
    return


def main():
    global focus_pkg_name
    global path_replays_pkg
    global path_records_pkg
    global replay_total_cnt

    # for color output
    os.system("")
    init(autoreset=True)

    parse_arguments()
    setup()
    if not replay_mode:
        print("[record] enter mode")
        record_setup()
        record_event_loop()
    else:
        print("[replay] enter mode")
        rr_replay_setup()
        for pkg in os.listdir(path_records):
            rr_replay_one_package(pkg)
        print(f"[replay mode] all test cased finished with {replay_passed_cnt} passed "
              f"and {replay_total_cnt - replay_passed_cnt} failed.")
    return


if __name__ == "__main__":
    main()
