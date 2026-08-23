import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    logger.info("Worker started")
    while True:
        # your task processing logic goes here
        time.sleep(5)


if __name__ == "__main__":
    main()
