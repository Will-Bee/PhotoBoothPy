# log.py

import datetime

class log:
    BLUE, GREEN, YELLOW, RED, PURPLE, GRAY, RESET = (
        "\033[94m", "\033[92m", "\033[93m", "\033[91m", "\033[95m", "\033[37m", "\033[0m"
    )
    CYAN = "\033[96m"
    WHITE = "\033[97m"


    def _print_log(tag, color, msg):
        # Fetch the current time and format it as HH:MM:SS
        current_time = datetime.datetime.now().strftime("%H:%M:%S")
        
        # Terminal output: [Time in Cyan] [Tag in Color] Message in White
        print(f"{log.CYAN}[{current_time}]{log.RESET} {color}[{tag}]{log.RESET} {log.WHITE}{msg}{log.RESET}")
    
        # File output: Plain text with the timestamp included
        with open("log.txt", "a", encoding="utf-8") as file:
            file.write(f"[{current_time}] [{tag}] {msg}\n")

    @staticmethod
    def info(msg): log._print_log("INFO", log.BLUE, msg)
    @staticmethod
    def ok(msg):   log._print_log(" OK ", log.GREEN, msg)
    @staticmethod
    def warn(msg): log._print_log("WARN", log.YELLOW, msg)
    @staticmethod
    def error(msg): log._print_log("ERRO", log.RED, msg)
    @staticmethod
    def prnt(msg): log._print_log("PRNT", log.PURPLE, msg)
    @staticmethod
    def idle(msg): log._print_log("IDLE", log.GRAY, msg)