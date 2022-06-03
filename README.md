# Pipethon
***Named pipe in Python3 for Linux, Windows and MacOS***

## Requirements:
- [pywin32](https://github.com/mhammond/pywin32): 
  - `$ pip install pywin32` — named pipes for Windows

## Docs
- class **`Pipe`**
  - static variables:
    - `NO_RESPONSE_MESSAGE = "No response from FIFO"`: string — returned when `Pipe.read_from_pipe()` doesn't read anything from FIFO
    - `NOT_FOUND_MESSAGE = "FIFO doesn't exist"`: string — used with `raise FileNotFoundError`
    - `MESSAGE_TO_IGNORE = "Ignore this message, just testing the pipe"` : string — sent to pipe if args is left empty, just to check whether the handler owns the pipe or not, or to kill processes stuck on listening. 
  - constructor args: 
    - `app_name`: string — used to generate FIFO name
    - `app_version`: string — used to generate FIFO name
    - `args`: list – `args` are passed to the process that listens to the pipe (if such one exists)
  - public parameters:
    - `path`: string — path of the FIFO
    - `is_pipe_owner`: bool — if `True`, there was no response from the FIFO reader, so the class assume it doesn't exist
  - public methods:
    - `send_to_pipe(self, message, timeout_secs = 1.5)`
      - `message`: string — data to send to pipe
      - `timeout_secs`: float (optional) — how many seconds should the sender wait before failing. 1.5 by default
      - returns bool — if `True`, sending data was successful
    - `read_from_pipe(self, timeout_secs = 1.5)` 
      - `timeout_secs`: float (optional) — how many seconds should the sender wait before failing. 1.5 by default
      - returns string: if it has read something, it returns the data received, otherwise `Pipe.NO_RESPONSE_MESSAGE`
  

## Purpose
The pipethon named pipes protocol was developed as the first stage of my [Google Summer of Code 2022 project](https://summerofcode.withgoogle.com/programs/2022/projects/ItQ0NNLd) for [(MusicBrainz Picard)](https://github.com/metabrainz/picard). 
