# developed by skelly37 under MIT license, 2022

import concurrent.futures
import os
from sys import platform
from typing import Optional

IS_WIN: bool = platform == "win32"
IS_MACOS: bool = platform == "darwin"

if IS_WIN:
    import win32pipe  # type: ignore
    import win32file  # type: ignore
    from pywintypes import error as WinApiError  # type: ignore


class Pipe:
    NO_RESPONSE_MESSAGE: str = "No response from FIFO"
    NOT_FOUND_MESSAGE: str = "FIFO doesn't exist"
    MESSAGE_TO_IGNORE: str = "Ignore this message, just testing the pipe"
    TIMEOUT_SECS: float = 1.5

    def __init__(self, app_name: str, app_version: str, args=None):
        if args is None:
            args = []

        self.__app_name: str = app_name
        self.__app_version: str = app_version
        self.__is_mac: bool = IS_MACOS
        self.__is_win: bool = IS_WIN

        # named pipe values needed by windows API
        if self.__is_win:
            self.__app_version = self.__app_version.replace(".", "-")

            # win32pipe.CreateNamedPipe
            # more about the arguments: https://docs.microsoft.com/en-us/windows/win32/api/winbase/nf-winbase-createnamedpipea
            self.__MAX_INSTANCES: int = 1
            self.__BUFFER_SIZE: int = 65536
            # timeout doesn't really matter, concurrent.futures ensures that connections are closed in declared time
            # the value is in milliseconds
            self.__DEFAULT_TIMEOUT: int = 300

            # win32file.CreateFile
            # more about the arguments: http://timgolden.me.uk/pywin32-docs/win32file__CreateFile_meth.html
            self.__SHARE_MODE: int = 0
            self.__FLAGS_AND_ATTRIBUTES: int = 0

            # pywintypes.error error codes
            # more about the error codes: https://docs.microsoft.com/en-us/openspecs/windows_protocols/ms-erref/18d8fbe8-a967-4f1c-ae50-99ca8e491d2d
            self.__FILE_NOT_FOUND_ERROR_CODE: int = 2
            self.__BROKEN_PIPE_ERROR_CODE: int = 109

        self.path: str = self.__generate_filename()

        self.is_pipe_owner: bool = False
        self.permission_error_happened: bool = False

        # test if pipe is listened to even if no args provided
        if isinstance(args, list):
            if not args:
                args.append(self.MESSAGE_TO_IGNORE)
        else:
            raise ValueError("args argument MUST be a list")

        if self.__is_win:
            for arg in args:
                if not self.send_to_pipe(arg):
                    self.is_pipe_owner = True
                    break
        else:
            try:
                self.__create_unix_pipe()
            except FileExistsError:
                for arg in args:
                    if not self.send_to_pipe(arg):
                        self.__create_unix_pipe()
                        break

    def __generate_filename(self) -> str:
        if self.__is_win:
            prefix = "\\\\.\\pipe\\"
        elif self.__is_mac:
            prefix = os.path.expanduser("~/Library/Application Support/MusicBrainz/Picard/pipes/")
        else:
            prefix = f"{os.getenv('XDG_RUNTIME_DIR')}/"
            # just in case the $XDG_RUNTIME_DIR is not declared, fallback dir
            if not prefix:
                prefix = os.path.expanduser("~/.config/MusicBrainz/Picard/pipes/")

        return f"{prefix}{self.__app_name}_v{self.__app_version}_pipe_file"

    def __create_unix_pipe(self) -> None:
        try:
            try:
                # just to be sure that there's no broken pipe left
                os.unlink(self.path)
            except FileNotFoundError:
                pass
            try:
                os.mkfifo(self.path)
            # no parent dirs detected, need to create them
            except FileNotFoundError:
                dirs = self.path.split("/")
                # we have to remove pipe name while creating dirs not to make it a dir
                # also, the first index is "", because we're on *nix
                dirs.pop(-1)
                dirs.pop(0)
                path = "/"
                for d in dirs:
                    path += d + "/"
                    if not os.path.exists(path):
                        os.mkdir(path)
                os.mkfifo(self.path)
        except PermissionError:
            self.permission_error_happened = True
        self.is_pipe_owner = True

    def __win_sender(self, message: str) -> bool:
        pipe = win32pipe.CreateNamedPipe(
            self.path,
            win32pipe.PIPE_ACCESS_DUPLEX,
            win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
            self.__MAX_INSTANCES,
            self.__BUFFER_SIZE,
            self.__BUFFER_SIZE,
            self.__DEFAULT_TIMEOUT,
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

    def send_to_pipe(self, message: str, timeout_secs: Optional[float] = None) -> bool:
        if timeout_secs is None:
            timeout_secs = self.TIMEOUT_SECS

        __pool = concurrent.futures.ThreadPoolExecutor()

        if self.__is_win:
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

    def read_from_pipe(self, timeout_secs: Optional[float] = None) -> str:
        if timeout_secs is None:
            timeout_secs = self.TIMEOUT_SECS

        __pool = concurrent.futures.ThreadPoolExecutor()

        if self.__is_win:
            reader = __pool.submit(self.__win_reader)
        else:
            reader = __pool.submit(self.__unix_reader)

        try:
            if reader.result(timeout=timeout_secs):
                res: str = reader.result()
                if res != self.MESSAGE_TO_IGNORE:
                    return res
        except concurrent.futures._base.TimeoutError:
            # hacky way to kill the file-opening loop
            self.send_to_pipe(self.MESSAGE_TO_IGNORE)

        return Pipe.NO_RESPONSE_MESSAGE

    def __win_reader(self) -> str:
        response = ""  # type: ignore

        try:
            pipe = win32file.CreateFile(
                self.path,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                self.__SHARE_MODE,
                None,
                win32file.OPEN_EXISTING,
                self.__FLAGS_AND_ATTRIBUTES,
                None
            )
            while not response:
                response = win32file.ReadFile(pipe, self.__BUFFER_SIZE)

        except WinApiError as err:
            if err.winerror == self.__FILE_NOT_FOUND_ERROR_CODE:
                raise FileNotFoundError(Pipe.NOT_FOUND_MESSAGE)
            elif err.winerror == self.__BROKEN_PIPE_ERROR_CODE:
                raise FileNotFoundError("Pipe is broken")
            else:
                raise FileNotFoundError(f"{err.winerror}; {err.funcname}; {err.strerror}")

        # response[0] stores an exit code while response[1] an actual response
        if response:
            if response[0] == 0:
                return str(response[1].decode("utf-8"))  # type: ignore
            else:
                raise ValueError(f"INVALID RESPONSE: {response[1].decode('utf-8')}")  # type: ignore
        else:
            return Pipe.NO_RESPONSE_MESSAGE

    def __unix_reader(self) -> str:
        response: str = ""
        while not response:
            try:
                with open(self.path, 'r') as fifo:
                    response = fifo.read().strip()
            except FileNotFoundError:
                raise FileNotFoundError(Pipe.NOT_FOUND_MESSAGE)

        if response:
            return response
        else:
            return Pipe.NO_RESPONSE_MESSAGE
