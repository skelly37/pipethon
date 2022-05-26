import os
from sys import argv, platform as PLATFORM
import concurrent.futures

if PLATFORM == "win32" or PLATFORM == "cygwin":
	import win32pipe, win32file
	PLATFORM = "windows"

#sample values to be replaced
APP_NAME: str = "Pipethon"
VERSION: str = "1-0-0"

class Pipe:
	NO_RESPONSE_MESSAGE = "No response from FIFO"
	NOT_FOUND_MESSAGE = "FIFO doesn't exist"

	def __init__(self, app_name: str, app_version: str, args):
		self.__app_name: str = app_name
		self.__app_version: str = app_version
		self.__platform: str = PLATFORM

		self.path: str = self.__generate_filename()

		self.is_pipe_owner: bool = False

		if self.__pipe_exists():
			for arg in args:
				if not self.send_to_pipe(arg):
					os.unlink(self.path)
					self.__create_pipe()
		else:
			self.__create_pipe()

		if self.__platform == "windows" and self.is_pipe_owner:
			pass
			#TODO windows pipe handle needed


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

	def __create_pipe(self) -> None:
		if self.__platform == "windows":
			self.__create_win_pipe()
		else:
			self.__create_unix_pipe()

		self.is_pipe_owner = True

	def __create_win_pipe(self) -> None:
		self.__windows_writer_handler = win32pipe.CreateNamedPipe(self.path,
									  win32pipe.PIPE_ACCESS_DUPLEX,
									  win32pipe.PIPE_TYPE_MESSAGE | win32pipe.PIPE_WAIT,
									  1, 65536, 65536, 300, None)

	def __create_unix_pipe(self) -> None:
		os.mkfifo(self.path)


	def send_to_pipe(self, message: str, timeout_secs: float = 1.5) -> bool:
		if self.__platform == "windows":
			return self.__send_to_win_pipe(message, timeout_secs)
		else:
			return self.__send_to_unix_pipe(message, timeout_secs)

	def __send_to_win_pipe(self, message: str, timeout_secs: float) -> bool:
		pass
		#TODO

	def __unix_sender(self, message: str) -> bool:
		with open(self.path, 'a') as fifo:
			fifo.write(message)
		return True

	def __send_to_unix_pipe(self, message: str, timeout_secs: float) -> bool:
		__pool = concurrent.futures.ThreadPoolExecutor()
		sender = __pool.submit(self.__unix_sender, message)

		try:
			if sender.result(timeout=timeout_secs):
				return True
		except concurrent.futures._base.TimeoutError:
			#hacky way to kill the sender
			with open(self.path, 'r') as fifo:
				fifo.read()

		return False


	def read_from_pipe(self, timeout_secs: float = 1.5) -> str:
		if self.__platform == "windows":
			return self.__read_from_win_pipe(timeout_secs)
		else:
			return self.__read_from_unix_pipe(timeout_secs)

	def __read_from_win_pipe(self, timeout_secs: float) -> str:
		pass
		#TODO

	def __unix_reader(self) -> str:
		response: str = ""
		while len(response)==0:
			try:
				fifo = open(self.path, 'r')
				response = fifo.read().strip()
			except FileNotFoundError:
				raise FileNotFoundError(Pipe.NOT_FOUND_MESSAGE)

		if len(response)>0:
			return response
		else:
			return Pipe.NO_RESPONSE_MESSAGE

	def __read_from_unix_pipe(self, timeout_secs: float) -> str:
		__pool = concurrent.futures.ThreadPoolExecutor()
		reader = __pool.submit(self.__unix_reader)

		try:
			if reader.result(timeout=timeout_secs):
				return reader.result()
		except concurrent.futures._base.TimeoutError:
			#hacky way to kill the file-opening loop
			with open(self.path, 'a') as fifo:
				fifo.write("kill the reader\n")

		return Pipe.NO_RESPONSE_MESSAGE

#TODO create win pipe (and import its module)
p = Pipe(APP_NAME, VERSION, argv[1:])
print(p.read_from_pipe())
print(p.is_pipe_owner)
print(p.send_to_pipe("anything"))
