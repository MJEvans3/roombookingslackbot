# Floor 10 Room Booking Slack Bot

A Slack bot that helps manage meeting room bookings for Floor 10. The bot allows users to book rooms, check availability, and manage their bookings directly through Slack.

## Features

- **Book Rooms**: Book any available room with specific date, time, and duration
- **List Rooms**: View all available rooms and their capacities
- **Check Availability**: Check room availability for specific dates
- **Cancel Bookings**: Cancel your existing room bookings
- **Smart Suggestions**: Get alternative room/time suggestions when your preferred slot is unavailable

## Available Rooms

- **The Nest** (Capacity: 30)
- **The Treehouse** (Capacity: 15)
- **The Lighthouse** (Capacity: 15)
- **Raven** (Capacity: 8)
- **Hummingbird** (Capacity: 8)

## Commands

- `@floor10roombooking book a room` - Shows booking format
- `@floor10roombooking book [room], [date], [time], [duration], [event details], [internal/client], [Full Contact Name]`
- `@floor10roombooking list rooms` - Shows all available rooms
- `@floor10roombooking list available rooms for [date]` - Shows available rooms for a specific date
- `@floor10roombooking cancel booking` - Starts booking cancellation process

Example booking command:
`@floor10roombooking book nest, tomorrow, 2pm, 2 hours, Team Meeting, internal, John Smith`

## Installation

1. Clone the repository:

    ```bash
    git clone https://github.com/yourusername/floor10-room-booking.git
    cd floor10-room-booking
    ```

2. Install required packages:

    ```bash
    pip install -r requirements.txt
    ```


3. Set up your Slack App:
   - Create a new Slack App in your workspace
   - Enable Socket Mode
   - Add bot token scopes:
     - `chat:write`
     - `app_mentions:read`
     - `channels:read`
   - Install the app to your workspace
   - Copy your Bot Token and App Token

4. Configure the bot:
   - Create your config file by copying the template:
     ```bash
     cp config/config_template.py config/config.py
     ```
   - Edit the new `config/config.py` file and replace the placeholder values with your tokens:
     ```python
     SLACK_BOT_TOKEN = "your-bot-token"  # Replace with your actual bot token
     SLACK_APP_TOKEN = "your-app-token"  # Replace with your actual app token
     ```
   Note: Leave `config_template.py` unchanged. The copy you created (`config.py`) will be automatically ignored by git to protect your tokens.


5. Run the bot:

    ```bash
    python main.py
    ```


## Project Structure

```
floor10-room-booking/
├── bot/
│ ├── message_handler.py
│ └── room_manager.py
├── config/
│ └── config.py
├── data/
│ └── rooms.json
├── slack_integration/
│ └── slack_bot.py
├── utils/
│ └── date_utils.py
├── main.py
├── requirements.txt
└── README.md
```




## Dependencies

- Python 3.8+
- slack-sdk>=3.19.5
- python-dotenv>=0.19.2

## Security Note

⚠️ Never commit your actual Slack tokens to GitHub. The tokens in this repository are examples and should be replaced with your own tokens.

## Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support, please open an issue in the GitHub repository or contact the maintainers.