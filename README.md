# Discord-Music-Player

This is a Discord bot that plays music from YouTube and Spotify. It uses the `discord.py` library along with `yt-dlp` and `spotipy` to download and play music. The bot supports various commands to control music playback, manage queues, and more.

## Features
- Play music from YouTube and Spotify with **music's url**
- Queue management
- Repeat queue and repeat song modes
- Shuffle queue and Clear queue
- Basic playback controls (play, pause, resume, stop, skip)
- Join and leave voice channels
- Automatically disconnects from empty voice channels

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

2. Install the required packages:
    ```sh
    pip install -r requirements.txt
    ```

3. Set up your `settings.json` file with your Discord bot token, FFmpeg path, and Spotify credentials:
    ```json
    {
        "token": "YOUR_DISCORD_BOT_TOKEN",
        "ffmpeg_path": "PATH_TO_FFMPEG",
        "spotify_client_id": "YOUR_SPOTIFY_CLIENT_ID",
        "spotify_client_secret": "YOUR_SPOTIFY_CLIENT_SECRET",
        "ENABLE_SPOTIFY": true,
        "ENABLE_YOUTUBE": true
    }
    ```
    Note: If you want to use Spotify, you need to create a (Spotify Developer)[https://developer.spotify.com/dashboard/applications] account and get your client ID and client secret, or set **ENABLE_SPOTIFY** to **false**.
    **ffmpeg_path** is the **Absolute path** to your ffmpeg.exe file.


## Usage

1. Run the bot:
    If you are using VSCode, use **Run and Debug** to run the bot without using terminal.
    ```sh
    python main.py
    ```

2. Use the following commands in your Discord server:

### Commands

- `?join`: Joins the voice channel you are in.
- `?leave`: Leaves the current voice channel.
- `?play <url>`: Plays a song from the given URL or adds it to the queue.
- `?pause`: Pauses the currently playing song.
- `?resume`: Resumes the paused song.
- `?stop`: Stops the currently playing song.
- `?skip`: Skips the current song.
- `?queue`: Shows the current music queue.
- `?clear`: Clears the current music queue.
- `?repeatqueue`: Toggles repeat queue mode.
- `?repeatsong`: Toggles repeat song mode.
- `?shuffle`: Shuffles the current queue.
- `?ping`: Tests the bot's responsiveness and checks the latency.

## Notes

- Ensure FFmpeg is installed and the path is correctly set in `settings.json`.
- The bot will automatically delete all `.mp3` files in the current directory on startup to avoid clutter.

## License

This project is licensed under the MIT License.