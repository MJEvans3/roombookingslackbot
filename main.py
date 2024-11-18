# main.py
from slack_integration.slack_bot import SlackBot
from bot.room_manager import RoomManager
from config.config import SLACK_APP_TOKEN
import signal
import sys
import time

def signal_handler(sig, frame):
    print("\nShutting down gracefully...")
    sys.exit(0)

def main():
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize RoomManager
    room_manager = RoomManager()
    
    # Initialize and start SlackBot with token from config
    bot = SlackBot(slack_token=SLACK_APP_TOKEN, room_manager=room_manager)
    bot.start()
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)

if __name__ == "__main__":
    main()
