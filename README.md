# Sandesh Music Bot

Sandesh is a feature-rich Discord music bot built with Python, `discord.py`, and `yt-dlp`. It allows users to play music from YouTube and Spotify in multiple servers simultaneously, manage queues, and enjoy a seamless music experience on Discord. The bot also includes a web-based dashboard to view usage statistics.

## Features

- **Multi-Server Support**: Sandesh can play music in multiple Discord servers at the same time without interference.
- **YouTube and Spotify Integration**: Play individual songs, playlists, or albums from both YouTube and Spotify.
- **Advanced Queue Management**: View, shuffle, remove, and move songs within the queue.
- **Playback Control**: Pause, resume, stop, and skip songs with simple commands.
- **Volume Control**: Adjust the playback volume for each server.
- **DJ Role System**: Restrict music control commands to users with a "DJ" role for better moderation.
- **Customizable Settings**: Set a custom command prefix and default volume for each server.
- **Song Lyrics**: Fetch lyrics for the currently playing song or any specified song.
- **Interactive Controls**: Use buttons on the "Now Playing" message to control playback easily.
- **Web Dashboard**: A Flask-based dashboard to view real-time statistics, including total songs played, current queues, and most played songs.
- **Error Logging**: Keeps a log of errors for easier debugging.

## Commands

Here is a list of available commands. Music control commands can be restricted to users with the "DJ" role.

| Command | Aliases | Description |
|---|---|---|
| `!join` | | Joins the voice channel you are currently in. |
| `!play <song or URL>` | `!p` | Plays a song from YouTube or a Spotify track/playlist/album URL. |
| `!pause` | | Pauses the current playback. |
| `!resume` | | Resumes the paused playback. |
| `!stop` | | Stops playback and clears the queue. |
| `!skip` | `!next` | Skips the current song and plays the next one in the queue. |
| `!queue` | `!q` | Displays the current song queue. |
| `!remove <number>` | | Removes a song from the queue at the specified position. |
| `!move <from> <to>` | | Moves a song from one position to another in the queue. |
| `!shuffle` | | Shuffles the songs in the queue. |
| `!repeat` | | Toggles repeating the current song. |
| `!volume <0.1-2.0>` | | Sets the playback volume. |
| `!lyrics [song name]` | | Fetches lyrics for the current or a specified song. |
| `!leave` | | Disconnects the bot from the voice channel. |
| `!find <query>` | `!search` | Searches for songs on YouTube and lets you choose from a list. |
| `!helpme` | | Shows the help message with all commands. |

### DJ-Only Commands
| Command | Description |
|---|---|
| `!setprefix <prefix>` | Sets a custom command prefix for the server. |
| `!setvolume <volume>` | Sets the default playback volume for the server. |

## Setup and Installation

### Prerequisites

- Python 3.8 or higher
- FFmpeg
- yt-dlp

#### Windows Installation

For Windows users, you can install `FFmpeg` and `yt-dlp` easily using `winget`. Open PowerShell or Command Prompt and run the following commands:

```sh
winget install --id=Gyan.FFmpeg -e
winget install --id=yt-dlp.yt-dlp -e
```

#### Other Operating Systems

Please refer to the official documentation for `FFmpeg` and `yt-dlp` to install them on your system.

### Bot Setup

1.  **Clone the repository:**
    ```sh
    git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
    cd sandesh-music-bot
    ```

2.  **Install Python dependencies:**
    ```sh
    pip install -r requirements.txt
    ```

3.  **Create a Discord Bot Application:**
    - Go to the [Discord Developer Portal](https://discord.com/developers/applications).
    - Create a new application and then create a bot for it.
    - Enable the `Message Content Intent` under the "Bot" tab.
    - Copy the bot's token.

4.  **Create a Spotify Application (Optional):**
    - If you want Spotify support, go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    - Create a new application and get the Client ID and Client Secret.

5.  **Configure Environment Variables:**
    - Create a file named `.env` in the project's root directory.
    - Add the following variables to the file:

    ```env
    DISCORD_TOKEN=your_discord_bot_token_here

    # Optional for Spotify support
    SPOTIPY_CLIENT_ID=your_spotify_client_id
    SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
    ```

6.  **Run the Bot:**
    ```sh
    python bot.py
    ```

7.  **Run the Dashboard (in a separate terminal):**
    ```sh
    python dashboard.py
    ```
    The dashboard will be available at `http://127.0.0.1:5000`.

## Inviting Your Bot

To add the bot to your server, you need to create an invitation link.

1.  Go back to the [Discord Developer Portal](https://discord.com/developers/applications) and select your application.
2.  Navigate to the **OAuth2** tab and then select **URL Generator**.
3.  In the "Scopes" section, check the box for `bot`.
4.  A new "Bot Permissions" section will appear below. Check the following permissions, which are required for the bot to function correctly:
    - **Send Messages**
    - **Embed Links**
    - **Read Message History**
    - **Connect**
    - **Speak**
5.  Scroll down and copy the **Generated URL**.
6.  Paste the URL into your web browser, select the server you want to add the bot to, and click "Authorize".

## Contributing

Contributions are welcome! If you have any ideas, suggestions, or find a bug, please open an issue or submit a pull request. 