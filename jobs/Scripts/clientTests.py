import socket
import sys
import os
from time import sleep, strftime, gmtime
import shlex
import traceback
import win32gui
import pyautogui
import pyscreenshot
import shlex
import json
import pydirectinput
from threading import Thread
from pyffmpeg import FFmpeg
from threading import Thread
from utils import collect_traces
import win32api
sys.path.append(os.path.abspath(os.path.join(
    os.path.dirname(__file__), os.path.pardir, os.path.pardir)))
from jobs_launcher.core.config import *

pyautogui.FAILSAFE = False


current_image_num = 1
SERVER_ACTIONS = ["execute_cmd", "check_game", "check_window", "press_keys_server", "click_server", "start_test_actions_server"]


def execute_cmd(sock, action):
    sock.send(action.encode("utf-8"))


def check_window(sock, action):
    sock.send(action.encode("utf-8"))


def make_screen(screen_path, screen_name=""):
    screen = pyscreenshot.grab()
    if screen_name:
        screen = screen.convert("RGB")
        global current_image_num
        screen.save(os.path.join(screen_path, "{:03}_{}.jpg".format(current_image_num, screen_name)))
        current_image_num += 1


def record_video(video_path, audio_device_name, video_name, resolution, duration):
    video_full_path = os.path.join(video_path, video_name + ".mp4")
    time_flag_value = strftime("%H:%M:%S", gmtime(int(duration)))
    
    resolution = "1920x1080"

    recorder = FFmpeg()
    main_logger.info("Start to record video")

    recorder.options("-f gdigrab -video_size {resolution} -i desktop -f dshow -i audio=\"{audio_device_name}\" -t {time} -q:v 3 -pix_fmt yuv420p {video}"
        .format(resolution=resolution, audio_device_name=audio_device_name, time=time_flag_value, video=video_full_path))

    main_logger.info("Finish to record video")


def move(x, y):
    main_logger.info("Move to x = {}, y = {}".format(x, y))
    pyautogui.moveTo(int(x), int(y))
    sleep(1)


def click():
    pyautogui.click()
    sleep(1)


def do_sleep(seconds):
    sleep(int(seconds))


def press_keys(keys_string):
    keys = keys_string.split()

    for key in keys:
        main_logger.info("Press: {}".format(key))
        pyautogui.press(key)

        if "enter" in key:
            sleep(2)
        else:
            sleep(1)


def press_keys_server(sock, action):
    sock.send(action.encode("utf-8"))


def sleep_and_screen(initial_delay, number_of_screens, delay, screen_name, sock, start_collect_traces, screen_path, archive_path, archive_name):
    sleep(int(initial_delay))

    screen_number = 1

    while True:
        make_screen(screen_path, screen_name="{}_{:02}".format(screen_name, screen_number))
        screen_number += 1

        if screen_number > int(number_of_screens):
            break
        else:
            sleep(int(delay))

    try:
        sock.send("gpuview".encode("utf-8"))
        response = sock.recv(1024).decode("utf-8")
        main_logger.info("Server response for 'gpuview' action: {}".format(response))

        if start_collect_traces == "True":
            collect_traces(archive_path, archive_name + "_client.zip")
    except Exception as e:
        main_logger.warning("Failed to collect GPUView traces: {}".format(str(e)))
        main_logger.warning("Traceback: {}".format(traceback.format_exc()))


def finish(sock):
    sock.send("finish".encode("utf-8"))
    response = sock.recv(1024).decode("utf-8")
    main_logger.info("Server response for 'finish' action: {}".format(response))


def abort(sock):
    sock.send("abort".encode("utf-8"))
    response = sock.recv(1024).decode("utf-8")
    main_logger.info("Server response for 'abort' action: {}".format(response))


def retry(sock):
    sock.send("retry".encode("utf-8"))
    response = sock.recv(1024).decode("utf-8")
    main_logger.info("Server response for 'retry' action: {}".format(response))


def next_case(sock):
    sock.send("next_case".encode("utf-8"))
    response = sock.recv(1024).decode("utf-8")
    main_logger.info("Server response for 'next_case' action: {}".format(response))


def click_server(sock, action):
    sock.send(action.encode("utf-8"))


def start_test_actions_server(sock, action):
    sock.send(action.encode("utf-8"))


def do_test_actions(game_name):
    try:
        if game_name == "apexlegends":
            for i in range(40):
                pydirectinput.press("q")
                sleep(1)
        elif game_name == "valorant":
            for i in range(10):
                pydirectinput.press("x")
                sleep(1)
                pyautogui.click()
                sleep(3)
        elif game_name == "lol":
            center_x = win32api.GetSystemMetrics(0) / 2
            center_y = win32api.GetSystemMetrics(1) / 2

            for i in range(5):
                pydirectinput.press("e")
                sleep(0.1)
                pydirectinput.press("e")
                sleep(0.1)

                pydirectinput.press("r")
                sleep(0.1)
                pydirectinput.press("r")
                sleep(3)

                # get time to do server actions
                sleep(4)

    except Exception as e:
        main_logger.error("Failed to do test actions: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))


def start_client_side_tests(args, case, is_workable_condition, ip_address, communication_port, output_path, audio_device_name, current_try):
    screens_path = os.path.join(output_path, case["case"])
    archive_path = os.path.join(args.output, "gpuview")

    if not os.path.exists(archive_path):
        os.makedirs(archive_path)

    if current_try == 0:
        current_image_num = 1

    sock = socket.socket()

    game_name = args.game_name

    while True:
        try:
            sock.connect((ip_address, int(communication_port)))
            break
        except Exception:
            main_logger.info("Could not connect to server. Try it again")
            sleep(5)

    try:
        # try to communicate with server few times
        sock.send("ready".encode("utf-8"))
        response = sock.recv(1024).decode("utf-8")

        is_previous_command_done = True
        is_failed = False
        is_non_workable = False
        is_aborted = False
        is_finished = False
        commands_to_skip = 0

        if response == "ready":

            if not is_workable_condition():
                is_non_workable = True
                raise Exception("Client has non-workable state")

            actions_key = "{}_actions".format(game_name.lower())
            if actions_key in case:
                actions = case[actions_key]
            else:
                # use default list of actions if some specific list of actions doesn't exist
                with open(os.path.abspath(args.common_actions_path), "r", encoding="utf-8") as common_actions_file:
                    actions = json.load(common_actions_file)[actions_key]

            for action in actions:
                main_logger.info("Current action: {}".format(action))

                if commands_to_skip > 0:
                    commands_to_skip -= 1
                    continue

                parts = action.split(' ', 1)
                command = parts[0]
                if len(parts) > 1:
                    arguments = shlex.split(parts[1])
                else:
                    arguments = None

                if command == "execute_cmd":
                    execute_cmd(sock, action)
                elif command == "check_game" or command == "check_window":
                    check_window(sock, action)
                elif command == "make_screen":
                    if arguments is None:
                        make_screen(output_path)
                    else:
                        make_screen(screens_path, screen_name="{}".format(*arguments))
                elif command == "record_video":
                    record_video(output_path, audio_device_name, case["case"], *arguments)
                elif command == "move":
                    move(*arguments)
                elif command == "click":
                    click()
                elif command == "sleep":
                    do_sleep(*arguments)
                elif command == "press_keys":
                    press_keys(*arguments)
                elif command == "press_keys_server":
                    press_keys_server(sock, action)
                elif command == "click_server":
                    click_server(sock, action)
                elif command == "start_test_actions_server":
                    start_test_actions_server(sock, "start_test_actions")
                elif command == "start_test_actions_client":
                    gpu_view_thread = Thread(target=do_test_actions, args=(game_name.lower(),))
                    gpu_view_thread.daemon = True
                    gpu_view_thread.start()
                elif command == "sleep_and_screen":
                    sleep_and_screen(*arguments, sock, args.collect_traces, screens_path, archive_path, case["case"])
                elif command == "finish":
                    is_finished = True
                    finish(sock)
                elif command == "skip_if_done":
                    if is_previous_command_done:
                        commands_to_skip += int(arguments[0])
                else:
                    raise Exception("Unknown client command: {}".format(command))

                if command in SERVER_ACTIONS:
                    response = sock.recv(1024).decode("utf-8")

                    main_logger.info("Server answer for action '{}': {}".format(action, response))

                    if response == "done":
                        is_previous_command_done = True
                        pass
                    elif response == "failed":
                        is_previous_command_done = False

                        if command != "check_game" and command != "check_window":
                            raise Exception("Action failed on server side")
                    elif response == "abort":
                        is_aborted = True
                        raise Exception("Server sent abort status")
                    else:
                        raise Exception("Unknown server status: {}".format(response))

        elif response == "fail":
            is_non_workable = True
            raise Exception("Server has non-workable state")
        else:
            raise Exception("Unknown server answer: {}".format(response))
    except Exception as e:
        is_failed = True
        main_logger.error("Fatal error. Case will be aborted: {}".format(str(e)))
        main_logger.error("Traceback: {}".format(traceback.format_exc()))

        raise e
    finally:
        if is_failed:
            if is_non_workable:
                retry(sock)
            else:
                abort(sock)
        elif is_aborted:
            pass
        elif is_finished:
            pass
        else:
            next_case(sock)

        sock.close()
