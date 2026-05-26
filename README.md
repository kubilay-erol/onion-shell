# onion-shell

A lightweight remote shell for accessing your own machine over Tor. No port forwarding, no VPN, no exposing your IP — just a `.onion` address and a persistent connection.

I built this to remotely access my Raspberry Pi from anywhere without touching my router config or relying on a third-party service. The only thing standing between the outside world and my machine is the Tor hidden service itself.

---

## What it does

- Persistent shell session over a Tor hidden service
- File upload and download with progress bars
- `cd` that actually persists across commands (per-session working directory)
- Automatic reconnect on the client side if the connection drops

---

## How it works

The server runs on your machine (in my case a Pi) and listens on localhost. Tor forwards incoming `.onion` connections to that local port. The client connects through SOCKS5 to your local Tor process, which routes everything through the onion network.

Every message — commands, responses, and file data — uses the same length-prefixed framing protocol: a 4-byte big-endian integer followed by that many bytes of payload. This means there's no ambiguity about where one message ends and the next begins, and file transfers don't need separate size negotiation.

```
Client                          Tor Network                     Server
  |                                  |                              |
  |-- SOCKS5 connect to .onion:80 -->|-- forward to 127.0.0.1:PORT->|
  |                                  |                              |
  |<---------- persistent framed TCP session ---------------------->|
```

---

## Project structure

```
onion-shell/
├── client-shell.py      # Run this on your local machine
├── server-daemon.py     # Run this on the remote machine (your Pi)
├── bootstrap.py         # Starts tor.exe with your torrc (Windows)
└── torrc                # Your Tor hidden service config (you provide this)
```

---

## Setup

### Server side (the Pi or whatever machine you're accessing)

**1. Install dependencies**

```bash
pip install PySocks
```

**2. Configure Tor**

Create a `torrc` file. At minimum:

```
HiddenServiceDir /var/lib/tor/onion-shell/
HiddenServicePort 80 127.0.0.1:6781
```

Start Tor:

```bash
tor -f torrc
```

After first run, Tor generates your `.onion` address. Find it:

```bash
cat /var/lib/tor/onion-shell/hostname
```

**3. Start the server**

```bash
python server-daemon.py
```

It listens on `127.0.0.1:6781` by default. Change `HOST` and `PORT` at the top of the file if needed.

### Client side (your laptop, wherever you are)

**1. Install dependencies**

```bash
pip install PySocks
```

**2. Make sure Tor is running locally**

On Linux:
```bash
tor
```

On Windows, use `bootstrap.py` which starts `tor.exe` silently:
```bash
python bootstrap.py
```

This expects `tor.exe` and `torrc` in the same directory. A minimal Windows `torrc` just needs:

```
SocksPort 9050
```

**3. Set your onion address**

Open `client-shell.py` and set `ONION_ADDRESS` to whatever your server generated:

```python
ONION_ADDRESS = "youronionaddresshere.onion"
```

Also check `PROXY_PORT` matches your local Tor SOCKS port (default `9050`).

**4. Connect**

```bash
python client-shell.py
```

---

## Usage

```
Shell> ls
Shell> cd /home/pi/projects
Shell> cat notes.txt
Shell> upload localfile.txt
Shell> download remotefile.bin
Shell> exit
```

Upload looks for files relative to the directory where `client-shell.py` lives. Downloaded files are saved there too, prefixed with `dl_`.

---

## Design notes

**Why framing instead of relying on TCP boundaries?**

TCP is a stream protocol — `recv()` doesn't guarantee you get exactly one message per call. Earlier versions of this used a new socket per command and relied on connection close to signal end-of-response. That worked but was slow (Tor circuit setup takes a few seconds each time) and made persistent state like `cd` impossible. Length-prefixed framing solves both problems cleanly.

**Why SOCKS5 with `rdns=True`?**

Setting `rdns=True` means the `.onion` hostname gets resolved inside the Tor network, not locally. Without it, your system's DNS resolver would try to look up the `.onion` address and fail — or worse, leak the hostname to your DNS provider.

**Why not just use SSH?**

You could, and for most cases you probably should. This was a learning project. Building the framing protocol and working out the Tor integration was the point.

---

## Known limitations

- **No authentication beyond the onion address** — whoever knows your `.onion` gets a shell. Keep that address private.
- **Single-client design** — the server handles multiple connections via threads, but `os.chdir()` is process-global, so concurrent `cd` commands from different clients would interfere with each other.
- **`shell=True` in subprocess** — fine for personal use since you control what you type, but worth knowing if you ever adapt this.

---

## Requirements

- Python 3.x
- [PySocks](https://github.com/Anorov/PySocks) (`pip install PySocks`)
- Tor Expert Bundle (any platform)

---

## License

MIT
