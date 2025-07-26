# Stranger Bot

A Telegram bot system with multi-bot management, payment integration, and subscription-based access control.

## Features

- **Multi-Bot Management**

  - Add and manage multiple bot instances
  - Enable/disable bots dynamically
  - Automatic channel verification
  - Individual bot status tracking

- **Payment Integration**

  - Paytm payment gateway integration
  - Order management system
  - Retry mechanism for failed payments
  - Subscription plan management

- **Bot Core Features**
  - Force subscription channels support
  - Database channels integration
  - Helper bot functionality
  - Extensive error handling

## Requirements

- Python 3.10+
- MongoDB
- Telegram Bot Tokens
- Paytm API Key
- Required Python packages in requirements.txt

## Environment Setup

Copy `sample.env` to `.env` and configure:

### API Configuration

- API_ID & API_HASH (Two sets needed)
- BOT_TOKEN & BOT_TOKEN2
- OWNER_ID
- DATABASE_URL & DATABASE_NAME

### Channel IDs

- BCAST_CHANNEL
- LOGS_CHANNEL_1 & LOGS_CHANNEL_2
- USELESS_CHANNEL

### Payment & Links

- PAYTM_API_KEY
- SHORTLINK_URL
- SHORTLINK_API

### Sessions

- STRING_SESSION
- STRING_SESSION2

## Installation

1. Clone the repository
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Set up environment variables
4. Run the bot:

```bash
python -m Stranger
```

## Project Structure

```
project/
├── __pycache__/
├── assets/
│   ├── base_pic.jpg
│   ├── base.gif.mp4
│   ├── download_audio.ogg
│   ├── info_pic.jpg
│   ├── join_image.jpg
│   ├── leave_voice.ogg
│   ├── SendRequest.ogg
│   ├── START_IMG.jpg
│   ├── start.gif.mp4
│   ├── subscription.jpg
│   └── warning_audio.ogg
├── Stranger/
│   ├── __init__.py
│   ├── __main__.py
│   ├── logger.py
│   ├── misc.py
│   ├── core/
│   │   ├── bot.py
│   │   ├── cache_config.py
│   │   ├── mongo.py
│   │   ├── paytm.py
│   │   └── userbot.py
│   ├── plugins/
│   │   ├── start.py
│   │   ├── useless.py
│   │   ├── bot/
│   │   │   ├── addbot.py
│   │   │   └── settings.py
│   │   ├── misc/
│   │   │   └── expire.py
│   │   ├── tools/
│   │   │   ├── accept_request.py
│   │   │   ├── reaction_post.py
│   │   │   └── search.py
│   │   └── sudo/
│   │       ├── broadcast.py
│   │       ├── gen_links.py
│   │       ├── info.py
│   │       ├── privileges.py
│   │       ├── reset.py
│   │       ├── stats.py
│   │       └── sudoers.py
│   ├── plugins2/
│   │   ├── start.py
│   │   ├── useless.py
│   │   └── welcome.py
│   ├── plugins3/
│   │   ├── start.py
│   │   ├── payment_check.py
│   │   └── useless.py
│   └── utils/
│       ├── helper.py
│       ├── inline/
│       │   ├── __init__.py
│       │   ├── privileges.py
│       │   └── settings.py
│       └── database/
│           ├── __init__.py
│           └── mongodatabase.py
├── config.py
├── requirements.txt
├── strings.py
├── .env
├── sample.env
├── README.md
├── LICENSE
└── .gitignore
```

### Key Components

- **bot.py**: Core bot implementation including handlers and client setup
- **config.py**: Environment variables and configuration management
- **database.py**: MongoDB connection and data operations
- **decorators.py**: Command handlers and middleware decorators
- **helpers.py**: Common utility functions and shared tools
- **main.py**: Application initialization and entry point
- **messages.py**: Response templates and string constants
- **utils/**: Additional utility modules
  - `payment.py`: Payment gateway integration
  - `validation.py`: Input validation and verification

## Features Documentation

### Payment System

- Supports order creation and tracking
- Automatic payment verification
- Retry mechanism with cooldown
- Order status management

### Bot Management

- Dynamic bot token validation
- Channel access verification
- Automatic bot startup/shutdown
- Status tracking and updates

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
