# Developed by skelly37 under MIT License (2022)

import concurrent.futures
import os
from sys import platform as PLATFORM


if PLATFORM == "win32" or PLATFORM == "cygwin":
    import win32pipe
    import win32file
    from pywintypes import error as WinApiError

    PLATFORM = "windows"


class Pipe:
    NO_RESPONSE_MESSAGE = "No response from FIFO"
    NOT_FOUND_MESSAGE = "FIFO doesn't exist"
    TEST_MESSAGE_TO_IGNORE = "Ignore this message, just testing the pipe"

    def __init__(self, app_name: str, app_version: str, args=[]):
        self.__app_name: str = app_name
        self.__app_version: str = app_version
        self.__platform: str = PLATFORM

        self.path: str = self.__generate_filename()

        self.is_pipe_owner: bool = False

        #test if pipe is listened to even if no args provided
        if len(args) == 0:
            args.append(self.TEST_MESSAGE_TO_IGNORE)

        if self.__platform == "windows":
            for arg in args:
                if not self.send_to_pipe(arg):
                    self.is_pipe_owner = True
                    break
        else:
            if self.__pipe_exists():
                for arg in args:
                    if not self.send_to_pipe(arg):
                        os.unlink(self.path)
                        self.__create_unix_pipe()
                        break
            else:
                self.__create_unix_pipe()

    def __pipe_exists(self) -> bool:
        return os.path.exists(self.path)

    def __generate_filename(self) -> str:
        prefix: str = ""
        username: str = os.getlogin()
        if self.__platform == "windows":
            prefix = "\\\\.\\pipe\\"
        else:
            prefix = "/tmp/"

        return f"{prefix}{self.__app_name}_v{self.__app_version}_{username}_pipe_file"

    def __create_unix_pipe(self) -> None:
        os.mkfifo(self.path)
        self.is_pipe_owner = True

    def __win_sender(self, message: str) -> bool:
        pipe = win32pipe.CreateNamedPipe(
            self.path,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
            1, 65536, 65536,
            300,
            None)
        try:
            win32pipe.ConnectNamedPipe(pipe, None)
            win32file.WriteFile(pipe, str.encode(message))
        finally:
            win32file.CloseHandle(pipe)

        return True

    def __unix_sender(self, message: str) -> bool:
        with open(self.path, 'a') as fifo:
            fifo.write(message)
        return True

    def send_to_pipe(self, message: str, timeout_secs: float = 1.5) -> bool:
        __pool = concurrent.futures.ThreadPoolExecutor()
        sender = None
        if self.__platform == "windows":
            sender = __pool.submit(self.__win_sender, message)
        else:
            sender = __pool.submit(self.__unix_sender, message)

        try:
            if sender.result(timeout=timeout_secs):
                return True
        except concurrent.futures._base.TimeoutError:
            # hacky way to kill the sender
            self.read_from_pipe()

        return False

    def read_from_pipe(self, timeout_secs: float = 1.5) -> str:
        if self.__platform == "windows":
            return str(self.__read_from_win_pipe(timeout_secs))
        else:
            return self.__read_from_unix_pipe(timeout_secs)

    def __win_reader(self) -> str:
        response: str = ""

        try:
            pipe = win32file.CreateFile(
                self.path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None
            )
            while len(response) == 0:
                response = win32file.ReadFile(pipe, 64 * 1024)

        except WinApiError as err:
            if err.args[0] == 2:
                raise FileNotFoundError(Pipe.NOT_FOUND_MESSAGE)
            elif err.args[0] == 109:
                raise FileNotFoundError("Pipe is broken")
            else:
                raise FileNotFoundError(f"{err.args[0]}; {err.args[1]}; {err.args[2]}")

        if len(response) > 0:
            if response[0] == 0:
                return response[1].decode("utf-8")
            else:
                raise ValueError(f"INVALID RESPONSE: {response[1].decode('utf-8')}")
        else:
            return Pipe.NO_RESPONSE_MESSAGE

    def __read_from_win_pipe(self, timeout_secs: float) -> str:
        __pool = concurrent.futures.ThreadPoolExecutor()
        reader = __pool.submit(self.__win_reader)

        try:
            if reader.result(timeout=timeout_secs):
                res = reader.result()
                if res != self.TEST_MESSAGE_TO_IGNORE:
                    return res
        except concurrent.futures._base.TimeoutError:
            # hacky way to kill the file-opening loop
            self.send_to_pipe("kill the reader\n")

        return Pipe.NO_RESPONSE_MESSAGE

    def __unix_reader(self) -> str:
        response: str = ""
        while len(response) == 0:
            try:
                fifo = open(self.path, 'r')
                response = fifo.read().strip()
            except FileNotFoundError:
                raise FileNotFoundError(Pipe.NOT_FOUND_MESSAGE)

        if len(response) > 0:
            return response
        else:
            return Pipe.NO_RESPONSE_MESSAGE

    def __read_from_unix_pipe(self, timeout_secs: float) -> str:
        __pool = concurrent.futures.ThreadPoolExecutor()
        reader = __pool.submit(self.__unix_reader)

        try:
            if reader.result(timeout=timeout_secs):
                res = reader.result()
                if res != self.TEST_MESSAGE_TO_IGNORE:
                    return res
        except concurrent.futures._base.TimeoutError:
            # hacky way to kill the file-opening loop
            self.send_to_pipe("kill the reader\n")

        return Pipe.NO_RESPONSE_MESSAGE
