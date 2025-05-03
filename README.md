# Discord-Music-Player

A Discord bot that plays music from YouTube and Spotify using `discord.py`, `yt-dlp`, and `spotipy`.

## Features

- Play music from YouTube and Spotify using URLs
- Queue management (add, remove, clear, shuffle)
- Repeat modes (queue and song)
- Basic playback controls (play, pause, resume, stop, skip)
- Voice channel management (join, leave)
- Auto-disconnect from empty channels

## Requirements

- Python 3.8+
- `discord.py`
- `yt-dlp`
- `asyncio`
- `spotipy`

## Installation

1. Clone the repository:
   ```sh
   git clone https://github.com/yourusername/discord-music-player.git
   cd discord-music-player
   ```

2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Configure `settings.json`:
   ```json
   {
     "token": "YOUR_DISCORD_BOT_TOKEN",
     "ffmpeg_path": "PATH_TO_FFMPEG",
     "spotify_client_id": "YOUR_SPOTIFY_CLIENT_ID",
     "spotify_client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
     "ENABLE_SPOTIFY": true,
     "ENABLE_YOUTUBE": true,
     "BUTTON_TIMEOUT": 600
   }
   ```
   Note: 
   - For Spotify, create a [Spotify Developer](https://developer.spotify.com/dashboard/applications) account or set `ENABLE_SPOTIFY` to `false`.
   - Get your [Discord bot token](https://discord.com/developers/applications).
   - `ffmpeg_path` should be the absolute path to `ffmpeg.exe`.

## Usage

1. Start the bot:
   ```sh
   python main.py
   ```
   Or use VSCode's "Run and Debug" feature.

2. Available commands:

   | Command | Description |
   |---------|-------------|
   | `?join` | Join user's voice channel |
   | `?leave` | Leave current voice channel |
   | `?play <url>` | Play or queue a song |
   | `?pause` | Pause current song |
   | `?skip` | Skip current song |
   | `?queue` | Show music queue |
   | `?clear` | Clear music queue |
   | `?repeatqueue` | Toggle repeat queue mode |
   | `?repeatsong` | Toggle repeat song mode |
   | `?shuffle` | Shuffle current queue |
   | `?ping` | Check bot responsiveness |

## Notes

- Ensure FFmpeg is installed and correctly configured in `settings.json`.
- The bot automatically deletes `.mp3` files in its directory on startup.

## TODO
- When playing two different songs with same name, it will cover the previous song.
- Not supported to play a YouTube or a Spotify playlist
- yt_dlp may not work as expected.

## License

This project is licensed under the MIT License.
