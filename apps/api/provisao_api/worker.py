"""Worker entrypoint. Production job consumers are deliberately separate from HTTP requests."""
import time
from .config import settings
def main() -> None:
    while True: time.sleep(30)
if __name__ == "__main__": main()
