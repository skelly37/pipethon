from pipethon import Pipe
import concurrent.futures

ARGS = ["test", "test2", "test3", "quit"]
RESPONSES = []


class Reader:
    def __init__(self, pipe):
        self.pipe = pipe

    def read(self):
        response = ""
        while len(response)==0:
            response = self.pipe.read_from_pipe()
            print(RESPONSES)
            if response != "quit":
                RESPONSES.append(response)
                return True
            return False

class Writer:
    def __init__(self, pipe):
        self.pipe = pipe

    def write(self):
        if len(ARGS)>0:
            if self.pipe.send_to_pipe(ARGS[0]):
                del ARGS[0]
                return True
        return False


pipe = Pipe(app_name="test", app_version="1-0-0", args=ARGS)

if pipe.is_pipe_owner:
    writer = Writer(pipe)
    reader = Reader(pipe)

    result = True
    while result:
        __pool = concurrent.futures.ThreadPoolExecutor()
        pwriter = __pool.submit(writer.write)
        preader = __pool.submit(reader.read)

        if preader.result(timeout=1.5):
            pass
        else:
            break

    print(f"FINAL RESULT: {RESPONSES}")