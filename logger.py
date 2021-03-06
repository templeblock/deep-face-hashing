import os
from time import time, strftime
from datetime import datetime
from utils import *

class Logger(object):
    '''
    Convenience class for logging metrics to a file.
    '''
    def __init__(self, **kwargs):
        self.print_to_stdout = kwargs.get("print_to_std", True)
        self._write_to_file = kwargs.get("write_to_file", False)
        current_dir = os.getcwd()
        file_name = kwargs.get("file_name", self._get_time())
        self.output_path = kwargs.get("output_path",
                                      current_dir + "/logs/{}.txt"
                                        .format(file_name))
        if self._write_to_file:
            mkdir(current_dir + "/logs")

    def __enter__(self):
        if self._write_to_file:
            self.file = open(self.output_path, "a+") # create and append
            self.file.write("{}: Logger initialized\n".format(self._get_time()))
        return self

    def __exit__(self, type, value, traceback):
        if self._write_to_file:
            self.file.write("{}: Logger closing\n\n\n".format(self._get_time()))
            self.file.close()

    def write(self, message):
        if self.print_to_stdout: print(message)
        if self._write_to_file:
            self.file.write("{}: {}\n".format(self._get_time(), message))

    def _get_time(self):
        return datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
