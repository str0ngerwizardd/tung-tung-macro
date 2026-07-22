import os
import re
import time
import json
import webbrowser
import psutil
import discord_webhook
import configparser
import customtkinter
import logging
import sys
import ctypes
import tkinter as tk
from PIL import Image, ImageTk

logging.basicConfig(
    filename="crash.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger("mylogger")


def my_handler(types, value, tb):
    logger.exception("Uncaught exception: {0}".format(str(value)))
    ctypes.windll.user32.MessageBoxW(
        0, "Check crash.log for information on this crash.", "Crashed!", 0
    )
    sys.exit()


biome_durations = {
    "WINDY": 120,
    "RAINY": 120,
    "SNOWY": 120,
    "SAND STORM": 120,
    "HELL": 666,
    "STARFALL": 600,
    "CORRUPTION": 660,
    "NULL": 90,
    "GLITCHED": 164,
    "DREAMSPACE": 180,
    "CYBERSPACE": 180,
    "PUMPKIN MOON": 600,
    "GRAVEYARD": 600,
    "BLOOD RAIN": 600,
    "HEAVEN": 600,
    "SINGULARITY": 600,
}

# ---------- merchant detection ----------
# requires the "Merchant Fix" to already be applied
#
# the nerchant fix makes roblox log failed assetdelivery requests
# this macro does NOT change the hosts file itself, it only watches those logged failures
#
# rin is intentionally disabled until i find an asset i can use for rin

MERCHANT_ASSET_IDS = {
    # Mari
    "18128528705": "Mari",       # Mari's Backpack texture

    # Jester: either failed asset means Jester has spawned/loaded
    "17825974440": "Jester",     # Jester's Mask texture
    "17825977799": "Jester",     # Jester's Hat texture
}

# Embed thumbnails
BIOME_IMAGES = {
    "WINDY": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/WINDY.png",
    "SNOWY": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/SNOWY.png",
    "RAINY": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/RAINY.png",
    "SAND STORM": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/SAND_STORM.png",
    "HELL": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/HELL.png",
    "STARFALL": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/STARFALL.png",
    "CORRUPTION": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/CORRUPTION.png",
    "NULL": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/NULL.png",
    "GLITCHED": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/GLITCHED.png",
    "DREAMSPACE": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/DREAMSPACE.png",
    "CYBERSPACE": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/CYBERSPACE.png",
    "HEAVEN": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/HEAVEN.png",
    "SINGULARITY": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/SINGULARITY.png",
}

MERCHANT_IMAGES = {
    "Jester": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/JESTER.png",
    "Mari": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/MARI.png",
    "Rin": "https://raw.githubusercontent.com/str0ngerwizardd/images/refs/heads/main/RIN.png",
}

MERCHANT_COLORS = {
    "Jester": "A352FF",
    "Mari": "FF82AB",
    "Rin": "FF9F1C",
}

# Example target line:
# Asset (Image) "https://assetdelivery.roblox.com/v1/asset?id=18128528705"
# load failed in Workspace.Map.<random-id>.Mari's Backpack...
MERCHANT_ASSET_FAILURE_RE = re.compile(
    r'https://assetdelivery\.roblox\.com/v1/asset\?id=(?P<asset_id>\d+)',
    re.IGNORECASE,
)

# The blocked asset can retry several times. One notification per merchant
# every 3 minutes prevents Mari/Jester webhook spam.
MERCHANT_DEDUPE_SEC = 180
last_merchant_seen = {}  # {"Mari": unix_time, "Jester": unix_time}
sys.excepthook = my_handler

customtkinter.set_appearance_mode("dark")
customtkinter.set_default_color_theme("blue")

root = customtkinter.CTk()
root.title("Tung Tung Macro")
root.geometry("505x410")
root.resizable(False, False)

script_dir = os.path.dirname(os.path.abspath(__file__))
icon_path = os.path.join(script_dir, "icon.ico")
print("ICON PATH:", icon_path)
print("ICON EXISTS:", os.path.exists(icon_path))

try:
    root.iconbitmap(icon_path)
except Exception as e:
    print("main window icon failed:", e)

dirname = script_dir

TITLE_FONT = customtkinter.CTkFont(family="Segoe UI Semibold", size=24)
SECTION_FONT = customtkinter.CTkFont(family="Segoe UI Semibold", size=16)
TEXT_FONT = customtkinter.CTkFont(family="Segoe UI", size=14)
BUTTON_FONT = customtkinter.CTkFont(family="Segoe UI Semibold", size=15)

tabview = customtkinter.CTkTabview(
    root,
    width=505,
    height=318,
    corner_radius=16,
    fg_color="transparent",
    segmented_button_fg_color="#0c0e13",
    segmented_button_selected_color="#3b82f6",
    segmented_button_selected_hover_color="#2563eb",
    segmented_button_unselected_color="#0c0e13",
    segmented_button_unselected_hover_color="#1b2130",
    text_color="#e5e7eb",
)
tabview.grid(row=0, column=0, padx=0, pady=0, sticky="nw")
tabview.grid_propagate(False)
# ^^^^^^^^^^ fixed a bug that made the tab buttons misalign when going to the merchant tab



tabview.add("Webhook")
tabview.add("Macro")
tabview.add("Merchants")
tabview.add("Credits")
tabview._segmented_button.configure(font=BUTTON_FONT)

# ---------- config ----------
config_name = "config.ini"
config = configparser.ConfigParser()

if not os.path.exists(config_name):
    logger.info("Config file not found, creating one...")
    print("Config file not found, creating one...")
    config["Webhook"] = {
        "webhook_url": "",
        "private_server": "",
        "discord_user_id": "",
        "multi_webhook": "0",
        "multi_webhook_urls": "",
    }
    config["Macro"] = {
        "last_roblox_version": "",
        "roblox_username": "",
        "seen_notice": "0",
    }
    config["Biomes"] = {
        "windy": "Message",
        "snowy": "Message",
        "rainy": "Message",
        "sand_storm": "Message",
        "hell": "Message",
        "starfall": "Message",
        "corruption": "Message",
        "null": "Message",
        "pumpkin_moon": "Message",
        "graveyard": "Message",
        "heaven": "Message",
        "singularity": "Message",
        "glitched": "Message",
        "dreamspace": "Message",
        "cyberspace": "Message",
        "blood_rain": "Message",
    }
    config["Merchants"] = {
        "jester": "Ping",
        "mari": "Ping",
        "rin": "Nothing",
    }
    with open(config_name, "w") as conffile:
        config.write(conffile)

config.read(config_name)

# ensure sections/keys exist for older configs
if not config.has_section("Merchants"):
    config.add_section("Merchants")
for key, default in (("jester", "Ping"), ("mari", "Ping"), ("rin", "Ping")):
    if not config.has_option("Merchants", key):
        config.set("Merchants", key, default)

if not config.has_section("Biomes"):
    config.add_section("Biomes")
for key, default in (
    ("heaven", "Message"),
    ("singularity", "Message"),
    ("glitched", "Message"),
    ("dreamspace", "Message"),
    ("cyberspace", "Message"),
    ("blood_rain", "Message"),
    ("pumpkin_moon", "Message"),
    ("graveyard", "Message"),
):
    if not config.has_option("Biomes", key):
        config.set("Biomes", key, default)

with open(config_name, "w") as configfile:
    config.write(configfile)

webhookURL = customtkinter.StringVar(root, config["Webhook"]["webhook_url"])
psURL = customtkinter.StringVar(root, config["Webhook"]["private_server"])
discID = customtkinter.StringVar(root, config["Webhook"]["discord_user_id"])
multi_webhook = customtkinter.StringVar(root, config["Webhook"]["multi_webhook"])
if multi_webhook.get() != "1" and webhookURL.get() == "Multi-Webhook On":
    webhookURL.set("")
webhook_urls_string = customtkinter.StringVar(
    root, config["Webhook"]["multi_webhook_urls"]
)
webhook_urls = webhook_urls_string.get().split()
last_roblox_version = config["Macro"]["last_roblox_version"]
roblox_username = customtkinter.StringVar(root, config["Macro"]["roblox_username"])

try:
    seen_notice = customtkinter.StringVar(root, config["Macro"]["seen_notice"])
except Exception:
    seen_notice = customtkinter.StringVar(root, "0")
    config.set("Macro", "seen_notice", "0")
    with open(config_name, "w") as configfile:
        config.write(configfile)

if seen_notice.get() == "0":
    seen_notice.set("1")
    config.set("Macro", "seen_notice", "1")
    with open(config_name, "w") as configfile:
        config.write(configfile)
    ctypes.windll.user32.MessageBoxW(
        0, "Thanks for continuing to use my macro! If you wish to donate, you can donate using this link here to fund the project: https://ko-fi.com/str0ngerwizard", "Notice", 0
    )

# ---------- variables ----------
roblox_open = False
versions_directory = os.path.expandvars(r"%localappdata%\Roblox\Versions")
log_directory = os.path.expandvars(r"%localappdata%\Roblox\logs")
packages_path = os.path.expandvars(r"%localappdata%\Packages")
roblox_folder = None
roblox_log_path = None
roblox_version = None

biome_colors = {
    "NORMAL": "ffffff",
    "SAND STORM": "F4C27C",
    "HELL": "5C1219",
    "STARFALL": "6784E0",
    "CORRUPTION": "9042FF",
    "NULL": "000000",
    "GLITCHED": "65FF65",
    "WINDY": "91F7FF",
    "SNOWY": "C4F5F6",
    "RAINY": "4385FF",
    "DREAMSPACE": "ff7dff",
    "PUMPKIN MOON": "d55f09",
    "GRAVEYARD": "FFFFFF",
    "BLOOD RAIN": "ff0000",
    "CYBERSPACE": "2c53a7",
    "HEAVEN": "e8c49e",
    "SINGULARITY": "ffa375",
}

started = False
stopped = False
paused = False
destroyed = False
debug_window = False
tlw_open = False

windy = customtkinter.StringVar(root, config["Biomes"]["windy"])
snowy = customtkinter.StringVar(root, config["Biomes"]["snowy"])
rainy = customtkinter.StringVar(root, config["Biomes"]["rainy"])
sand_storm = customtkinter.StringVar(root, config["Biomes"]["sand_storm"])
hell = customtkinter.StringVar(root, config["Biomes"]["hell"])
starfall = customtkinter.StringVar(root, config["Biomes"]["starfall"])
corruption = customtkinter.StringVar(root, config["Biomes"]["corruption"])
null = customtkinter.StringVar(root, config["Biomes"]["null"])
glitched = customtkinter.StringVar(root, config["Biomes"].get("glitched", "Message"))
dreamspace = customtkinter.StringVar(root, config["Biomes"].get("dreamspace", "Message"))
cyberspace = customtkinter.StringVar(root, config["Biomes"].get("cyberspace", "Message"))
pumpkin_moon = customtkinter.StringVar(
    root, config["Biomes"].get("pumpkin_moon", "Message")
)
graveyard = customtkinter.StringVar(root, config["Biomes"].get("graveyard", "Message"))
heaven = customtkinter.StringVar(root, config["Biomes"].get("heaven", "Message"))
singularity = customtkinter.StringVar(
    root, config["Biomes"].get("singularity", "Message")
)
blood_rain = customtkinter.StringVar(root, config["Biomes"].get("blood_rain", "Message"))

jester = customtkinter.StringVar(root, config["Merchants"]["jester"])
mari = customtkinter.StringVar(root, config["Merchants"]["mari"])
rin = customtkinter.StringVar(root, config["Merchants"]["rin"])


def get_biome_color(biome):
    try:
        return biome_colors[biome]
    except Exception:
        return "ff69b4"


def get_biome_setting(biome_name):
    key = biome_name.replace(" ", "_").lower()
    var = globals().get(key)
    if var is None:
        return "Message"
    try:
        return var.get()
    except Exception:
        return "Message"


def get_merchant_setting(name):
    var = globals().get(name.lower())
    if var is None:
        return "Ping"
    try:
        return var.get()
    except Exception:
        return "Ping"


def save_config_value(section, key, value):
    config.set(section, key, value)
    with open(config_name, "w") as configfile:
        config.write(configfile)


def send_discord_embed(embed, content=None):
    """Send one embed through the single webhook or every multi-webhook."""
    if multi_webhook.get() != "1":
        url = webhookURL.get().strip()
        if "discord" not in url or "https://" not in url:
            print("Invalid or missing Discord webhook URL.")
            return False

        webhook = discord_webhook.DiscordWebhook(url=url, content=content)
        webhook.add_embed(embed)
        webhook.execute()
        return True

    if not webhook_urls:
        print("Multi-webhook is enabled but no webhook URLs were supplied.")
        return False

    for url in webhook_urls:
        url = url.strip()
        if not url:
            continue

        webhook = discord_webhook.DiscordWebhook(url=url, content=content)
        webhook.add_embed(embed)
        webhook.execute()

    return True


def send_merchant_webhook(who):
    setting = get_merchant_setting(who)

    if setting == "Nothing":
        return

    print(time.strftime("%H:%M:%S"), f"Merchant Arrived - {who}")

    embed = discord_webhook.DiscordEmbed(
        description=(
            f"[{time.strftime('%H:%M:%S')}]\n"
            f"## {who} Has Arrived!"
        ),
        color=MERCHANT_COLORS.get(who, 0x7289DA),
    )

    # Top-right merchant image
    thumbnail_url = MERCHANT_IMAGES.get(who)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if psURL.get():
        embed.add_embed_field(
            name="Private Server Link",
            value=psURL.get(),
            inline=False,
        )

    embed.add_embed_field(
        name="Join Discord",
        value="[Click here to join the Discord](https://discord.gg/AEj3rB9ANQ)",
        inline=False,
    )

    embed.set_footer(
        text="Tung Tung Macro | v1.2",
        icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
    )

    content = None
    if setting == "Ping" and discID.get().isnumeric():
        content = f"<@{discID.get()}>"

    send_discord_embed(embed, content=content)

def handle_merchant_line(line):
    """
    Detect Mari/Jester from MultiScope Merchant Fix assetdelivery failure logs.

    Requires BOTH:
      - assetdelivery.roblox.com
      - load failed
      - a known Mari/Jester texture asset ID
    """
    if not line:
        return

    lower = line.lower()

    if "assetdelivery.roblox.com" not in lower:
        return

    if "load failed" not in lower:
        return

    match = MERCHANT_ASSET_FAILURE_RE.search(line)
    if not match:
        return

    asset_id = match.group("asset_id")
    who = MERCHANT_ASSET_IDS.get(asset_id)

    if who is None:
        return

    now = time.time()
    previous_alert = last_merchant_seen.get(who, 0)

    if now - previous_alert < MERCHANT_DEDUPE_SEC:
        # there was something like this for debug here but it's useless now
        # idk why i'm keeping this tbh i should prob delete this
        '''
        print(
            f"{time.strftime('%H:%M:%S')}: "
            f"{who} asset {asset_id} ignored (duplicate cooldown)."
        )
        '''
        return

    last_merchant_seen[who] = now
    # same thing here
    '''
        print(
            f"{time.strftime('%H:%M:%S')}: "
            f"Merchant asset failure detected: {asset_id} -> {who}"
        )
    '''
    send_merchant_webhook(who)

def stop():
    global stopped
    config.set("Webhook", "webhook_url", webhookURL.get())
    config.set("Webhook", "private_server", psURL.get())
    config.set("Webhook", "discord_user_id", discID.get())
    with open(config_name, "w") as configfile:
        config.write(configfile)

    if started and not stopped:
        ending_embed = discord_webhook.DiscordEmbed(
            description="[" + time.strftime("%H:%M:%S") + "]: Macro stopped."
        )
        ending_embed.set_footer(
            text="Tung Tung Macro | v1.2",
            icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
        )
        if multi_webhook.get() != "1":
            if "discord" in webhookURL.get() and "https://" in webhookURL.get():
                ending_webhook = discord_webhook.DiscordWebhook(url=webhookURL.get())
                ending_webhook.add_embed(ending_embed)
                ending_webhook.execute()
        else:
            for url in webhook_urls:
                ending_webhook = discord_webhook.DiscordWebhook(url=url)
                ending_webhook.add_embed(ending_embed)
                ending_webhook.execute()
    else:
        sys.exit()
    stopped = True


def pause():
    global paused
    paused = not paused
    if paused:
        root.title("Tung Tung Macro - Paused")
    else:
        root.title("Tung Tung Macro - Running")


if multi_webhook.get() == "1":
    if len(webhook_urls) < 2:
        ctypes.windll.user32.MessageBoxW(
            0,
            "there's no reason to use multi-webhook... without multiple webhooks??",
            "bruh are you serious",
            0,
        )
        stop()
    elif len(webhook_urls) > 14:
        if len(webhook_urls) > 49:
            ctypes.windll.user32.MessageBoxW(
                0,
                "you've gotta be doing this on purpose now... you don't need this many webhooks",
                "this is ridiculous",
                0,
            )
        else:
            ctypes.windll.user32.MessageBoxW(
                0, "bro you do not need this many webhooks", "okay dude wtf", 0
            )
        stop()


def x_stop():
    global destroyed
    destroyed = True
    stop()


def detect_roblox_version():
    global roblox_log_path, roblox_version, roblox_folder
    for proc in psutil.process_iter(["name"]):
        name = proc.info.get("name") or ""
        if "RobloxPlayerBeta.exe" in name:
            if roblox_version != "player":
                roblox_version = "player"
                roblox_log_path = log_directory
            return "player"
        elif "Windows10Universal.exe" in name:
            if roblox_version != "store":
                roblox_version = "store"
                for folder in os.listdir(packages_path):
                    if folder.startswith("ROBLOXCORPORATION.ROBLOX"):
                        roblox_folder = folder
                        roblox_log_path = os.path.join(
                            packages_path, roblox_folder, "LocalState", "logs"
                        )
            return "store"
    return None


def get_latest_log_file():
    if roblox_log_path and os.path.isdir(roblox_log_path):
        files = [
            f
            for f in os.listdir(roblox_log_path)
            if f.endswith(".log") and "Installer" not in f
        ]
        if not files:
            return None
        latest_file = max(
            files, key=lambda f: os.path.getctime(os.path.join(roblox_log_path, f))
        )
        return os.path.join(roblox_log_path, latest_file)
    return None


def is_roblox_running():
    return detect_roblox_version() is not None


def send_biome_ended(last_event):
    setting = get_biome_setting(last_event)
    if setting == "Nothing":
        return
    embed = discord_webhook.DiscordEmbed(
        title="",
        color=get_biome_color(last_event),
        description=f"""[{time.strftime('%H:%M:%S')}]

# Biome Ended - {last_event}""",
    )
    embed.set_footer(
        text="Tung Tung Macro | v1.2",
        icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
    )
    embed.set_thumbnail(
        url="https://maxstellar.github.io/biome_thumb/"
        + last_event.replace(" ", "_")
        + ".png"
    )
    send_discord_embed(embed, content=None)


def send_biome_started(event):
    setting = get_biome_setting(event)

    if setting == "Nothing":
        return

    biome_duration = biome_durations.get(event, 0)
    end_unix = int(time.time()) + biome_duration if biome_duration else 0
    ends_line = f"Ends: <t:{end_unix}:R>" if end_unix else ""

    print(time.strftime("%H:%M:%S"), f"Biome Started - {event}")

    embed = discord_webhook.DiscordEmbed(
        description=(
            f"[{time.strftime('%H:%M:%S')}]\n"
            f"## {event} Has Started!"
            + (f"\n{ends_line}" if ends_line else "")
        ),
        color=get_biome_color(event),
    )

    # Top-right biome image
    thumbnail_url = BIOME_IMAGES.get(event)
    if thumbnail_url:
        embed.set_thumbnail(url=thumbnail_url)

    if psURL.get():
        embed.add_embed_field(
            name="Private Server Link",
            value=psURL.get(),
            inline=False,
        )

    embed.add_embed_field(
        name="Join Discord",
        value="[Click here to join the Discord](https://discord.gg/AEj3rB9ANQ)",
        inline=False,
    )

    embed.set_footer(
        text="Tung Tung Macro | v1.2",
        icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
    )

    content = None
    if event in ["GLITCHED", "DREAMSPACE", "CYBERSPACE"]:
        content = "@everyone"
    elif setting == "Ping" and discID.get().isnumeric():
        content = f"<@{discID.get()}>"

    send_discord_embed(embed, content=content)

def check_for_hover_text(file):
    global roblox_version, roblox_username
    last_event = None
    file.seek(0, 2)  # tail only - skip history

    while True:
        if not stopped:
            root.update()
        else:
            if not destroyed:
                root.destroy()
            sys.exit()

        check = is_roblox_running()
        if check:
            line = file.readline()
            if line and not paused:
                # --- merchants ---
                try:
                    handle_merchant_line(line)
                except Exception as e:
                    print(f"Merchant parse error: {e}")

                # --- biomes ---
                if '"command":"SetRichPresence"' in line:
                    try:
                        json_data_start = line.find('{"command":"SetRichPresence"')
                        if json_data_start != -1:
                            json_data = json.loads(line[json_data_start:])
                            event = (
                                json_data.get("data", {})
                                .get("largeImage", {})
                                .get("hoverText", "")
                            )
                            if event and event != last_event:
                                if multi_webhook.get() != "1":
                                    if (
                                        "discord" not in webhookURL.get()
                                        or "https://" not in webhookURL.get()
                                    ):
                                        ctypes.windll.user32.MessageBoxW(
                                            0,
                                            "Invalid or missing webhook link.",
                                            "Error",
                                            0,
                                        )
                                        stop()
                                        return

                                if event == "NORMAL":
                                    if last_event is not None:
                                        print(
                                            time.strftime("%H:%M:%S")
                                            + f": Biome Ended - "
                                            + last_event
                                        )
                                        try:
                                            send_biome_ended(last_event)
                                        except Exception:
                                            pass
                                else:
                                    print(
                                        time.strftime("%H:%M:%S")
                                        + f": Biome Started - {event}"
                                    )
                                    try:
                                        send_biome_started(event)
                                    except Exception:
                                        pass
                                last_event = event
                    except json.JSONDecodeError:
                        print("Error decoding JSON")
            else:
                time.sleep(0.1)
        else:
            print("Roblox is closed, waiting for Roblox to start...")
            close_embed = discord_webhook.DiscordEmbed(
                description="["
                + time.strftime("%H:%M:%S")
                + "]: Roblox was closed/crashed."
            )
            close_embed.set_footer(
                text="Tung Tung Macro | v1.2",
                icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
            )
            try:
                send_discord_embed(close_embed)
            except Exception:
                pass

            root.title("Tung Tung Macro - No Roblox Detected")
            while True:
                if not stopped:
                    root.update()
                else:
                    if not destroyed:
                        root.destroy()
                    sys.exit()
                if is_roblox_running():
                    break
                time.sleep(0.1)

            if roblox_version == "player":
                logger.info("Detected Roblox Player.")
                print("Detected Roblox Player.")
                time.sleep(5)
            else:
                logger.info("Detected Roblox Microsoft Store.")
                print("Detected Roblox Microsoft Store.")
                time.sleep(5)

            latest_log = get_latest_log_file()
            if not latest_log:
                logger.info("No log files found.")
                print("No log files found.")
                return
            # reopen new log and continue tailing
            try:
                file.close()
            except Exception:
                pass
            file = open(latest_log, "r", encoding="utf-8", errors="ignore")
            print(f"Using log file: {latest_log}")
            print()
            logger.info(f"Using log file: {latest_log}")
            root.title("Tung Tung Macro - Running")
            last_event = None
            last_merchant_seen.clear()
            file.seek(0, 2)


def open_url(url):
    webbrowser.open(url, new=2, autoraise=True)


def set_windy(new_val):
    save_config_value("Biomes", "windy", new_val)


def set_snowy(new_val):
    save_config_value("Biomes", "snowy", new_val)


def set_rainy(new_val):
    save_config_value("Biomes", "rainy", new_val)


def set_sand_storm(new_val):
    save_config_value("Biomes", "sand_storm", new_val)


def set_hell(new_val):
    save_config_value("Biomes", "hell", new_val)


def set_starfall(new_val):
    save_config_value("Biomes", "starfall", new_val)


def set_corruption(new_val):
    save_config_value("Biomes", "corruption", new_val)


def set_null(new_val):
    save_config_value("Biomes", "null", new_val)


def set_pumpkin_moon(new_val):
    save_config_value("Biomes", "pumpkin_moon", new_val)


def set_graveyard(new_val):
    save_config_value("Biomes", "graveyard", new_val)


def set_glitched(new_val):
    save_config_value("Biomes", "glitched", new_val)


def set_dreamspace(new_val):
    save_config_value("Biomes", "dreamspace", new_val)


def set_cyberspace(new_val):
    save_config_value("Biomes", "cyberspace", new_val)


def set_heaven(new_val):
    save_config_value("Biomes", "heaven", new_val)


def set_singularity(new_val):
    save_config_value("Biomes", "singularity", new_val)


def set_blood_rain(new_val):
    save_config_value("Biomes", "blood_rain", new_val)


def set_jester(new_val):
    save_config_value("Merchants", "jester", new_val)


def set_mari(new_val):
    save_config_value("Merchants", "mari", new_val)


def set_rin(new_val):
    save_config_value("Merchants", "rin", new_val)

# ---------- V2-style Merchant Fix (hosts file) ----------
HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
MERCHANT_FIX_MARKER = "# TungTungMacro-MerchantFix"
MERCHANT_FIX_LINE = "0.0.0.0 assetdelivery.roblox.com"

def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False

def read_hosts_text():
    try:
        with open(HOSTS_PATH, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception as e:
        print(f"Failed to read hosts file: {e}")
        return None

def is_merchant_fix_applied():
    text = read_hosts_text()
    if text is None:
        return False

    for raw_line in text.splitlines():
        line = raw_line.strip().lower()
        if not line or line.startswith("#"):
            continue
        if "assetdelivery.roblox.com" in line:
            return True
    return False

def write_hosts_text(text):
    with open(HOSTS_PATH, "w", encoding="utf-8", errors="ignore") as f:
        f.write(text)

def apply_merchant_fix():
    """
    Apply the same style of fix V2 uses:
    block assetdelivery.roblox.com in the Windows hosts file so merchant
    textures fail to load and appear in the Roblox log.
    """
    if not is_admin():
        ctypes.windll.user32.MessageBoxW(
            0,
            "Applying the Merchant Fix requires Administrator permissions.\n\n"
            "Close this macro, right-click it, choose Run as administrator, "
            "then press Apply Merchant Fix again.",
            "Admin Required",
            0x30,
        )
        return False

    text = read_hosts_text()
    if text is None:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Could not read the Windows hosts file.",
            "Merchant Fix Error",
            0x10,
        )
        return False

    if is_merchant_fix_applied():
        ctypes.windll.user32.MessageBoxW(
            0,
            "Merchant Fix is already applied.",
            "Merchant Fix",
            0x40,
        )
        refresh_merchant_fix_ui()
        return True

    # Keep a clean trailing newline, then append our block.
    cleaned = text.rstrip("\n")
    block = (
        f"\n\n{MERCHANT_FIX_MARKER}\n"
        f"{MERCHANT_FIX_LINE}\n"
        f"{MERCHANT_FIX_MARKER}-END\n"
    )

    try:
        write_hosts_text(cleaned + block)
    except PermissionError:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Permission denied while writing hosts.\n"
            "Run the macro as Administrator and try again.",
            "Merchant Fix Error",
            0x10,
        )
        return False
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Failed to apply Merchant Fix:\n{e}",
            "Merchant Fix Error",
            0x10,
        )
        return False

    ctypes.windll.user32.MessageBoxW(
        0,
        "Merchant Fix applied.\n\n"
        "Restart Roblox completely, then start the macro.\n"
        "Merchant textures will fail to load and get logged.",
        "Merchant Fix Applied",
        0x40,
    )
    refresh_merchant_fix_ui()
    return True

def remove_merchant_fix():
    """Remove only the Merchant Fix hosts entries this macro added/recognizes."""
    if not is_admin():
        ctypes.windll.user32.MessageBoxW(
            0,
            "Removing the Merchant Fix requires Administrator permissions.\n\n"
            "Close this macro, right-click it, choose Run as administrator, "
            "then press Remove Merchant Fix again.",
            "Admin Required",
            0x30,
        )
        return False

    text = read_hosts_text()
    if text is None:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Could not read the Windows hosts file.",
            "Merchant Fix Error",
            0x10,
        )
        return False

    lines = text.splitlines()
    kept = []
    removed_any = False
    skipping_block = False

    for line in lines:
        stripped = line.strip()

        # Remove our marked block cleanly.
        if stripped == MERCHANT_FIX_MARKER:
            skipping_block = True
            removed_any = True
            continue
        if stripped == f"{MERCHANT_FIX_MARKER}-END":
            skipping_block = False
            removed_any = True
            continue
        if skipping_block:
            removed_any = True
            continue

        # Also strip any standalone assetdelivery block line.
        lower = stripped.lower()
        if lower and not lower.startswith("#") and "assetdelivery.roblox.com" in lower:
            removed_any = True
            continue

        kept.append(line)

    if not removed_any:
        ctypes.windll.user32.MessageBoxW(
            0,
            "No Merchant Fix entry was found in the hosts file.",
            "Merchant Fix",
            0x40,
        )
        refresh_merchant_fix_ui()
        return True

    new_text = "\n".join(kept).rstrip("\n") + "\n"

    try:
        write_hosts_text(new_text)
    except PermissionError:
        ctypes.windll.user32.MessageBoxW(
            0,
            "Permission denied while writing hosts.\n"
            "Run the macro as Administrator and try again.",
            "Merchant Fix Error",
            0x10,
        )
        return False
    except Exception as e:
        ctypes.windll.user32.MessageBoxW(
            0,
            f"Failed to remove Merchant Fix:\n{e}",
            "Merchant Fix Error",
            0x10,
        )
        return False

    ctypes.windll.user32.MessageBoxW(
        0,
        "Merchant Fix removed.\n\nRestart Roblox completely for assets to load normally again.",
        "Merchant Fix Removed",
        0x40,
    )
    refresh_merchant_fix_ui()
    return True

def refresh_merchant_fix_ui():
    """Update the Merchants-tab status label + button text."""
    try:
        applied = is_merchant_fix_applied()
        if applied:
            merchant_fix_status.configure(
                text="Status: APPLIED  (assetdelivery.roblox.com is blocked)",
                text_color="#4ade80",
            )
            merchant_fix_button.configure(
                text="Remove Merchant Fix",
                fg_color="#ef4444",
                hover_color="#dc2626",
                command=remove_merchant_fix,
            )
        else:
            merchant_fix_status.configure(
                text="Status: NOT APPLIED  (click below to enable detection)",
                text_color="#fbbf24",
            )
            merchant_fix_button.configure(
                text="Apply Merchant Fix",
                fg_color="#3b82f6",
                hover_color="#2563eb",
                command=apply_merchant_fix,
            )
    except Exception as e:
        print(f"Merchant fix UI refresh failed: {e}")

def manage_tlw():
    global tlw_open, dirname
    if tlw_open:
        return

    tlw_open = True
    tlw = customtkinter.CTkToplevel()
    tlw.bind("<Destroy>", lambda e: globals().__setitem__("tlw_open", False))
    tlw.title("Configure Pings")

    font20 = customtkinter.CTkFont(family="Segoe UI", size=18)
    opts = ["Message", "Ping", "Nothing"]

    tlw_label = customtkinter.CTkLabel(
        tlw, text="Biomes & Merchants", font=customtkinter.CTkFont(family="Segoe UI", size=20)
    )
    tlw_label.grid(row=0, column=0, columnspan=4, pady=10, padx=10)

    # biomes column 0-1
    biome_rows = [
        ("Windy", windy, set_windy),
        ("Snowy", snowy, set_snowy),
        ("Rainy", rainy, set_rainy),
        ("Sand Storm", sand_storm, set_sand_storm),
        ("Hell", hell, set_hell),
        ("Starfall", starfall, set_starfall),
        ("Corruption", corruption, set_corruption),
        ("Null", null, set_null),
    ]
    for i, (label, var, cmd) in enumerate(biome_rows):
        row = 1 + i
        customtkinter.CTkLabel(tlw, text=label, font=font20).grid(
            column=0, row=row, padx=(10, 0), pady=6, sticky="w"
        )
        customtkinter.CTkOptionMenu(
            tlw, values=opts, font=font20, variable=var, command=cmd, width=120
        ).grid(row=row, column=1, sticky="w", padx=10, pady=6)

    # biomes column 2-3
    biome_rows2 = [
        ("Glitched", glitched, set_glitched),
        ("Dreamspace", dreamspace, set_dreamspace),
        ("Cyberspace", cyberspace, set_cyberspace),
        ("Pumpkin Moon", pumpkin_moon, set_pumpkin_moon),
        ("Graveyard", graveyard, set_graveyard),
        ("Heaven", heaven, set_heaven),
        ("Singularity", singularity, set_singularity),
        ("Blood Rain", blood_rain, set_blood_rain),
    ]
    for i, (label, var, cmd) in enumerate(biome_rows2):
        row = 1 + i
        customtkinter.CTkLabel(tlw, text=label, font=font20).grid(
            column=2, row=row, padx=(10, 0), pady=6, sticky="w"
        )
        customtkinter.CTkOptionMenu(
            tlw, values=opts, font=font20, variable=var, command=cmd, width=120
        ).grid(row=row, column=3, sticky="w", padx=10, pady=6)

    # merchants
    merch_label = customtkinter.CTkLabel(
        tlw, text="Merchants", font=customtkinter.CTkFont(family="Segoe UI", size=20)
    )
    merch_label.grid(row=9, column=0, columnspan=4, pady=(14, 6), padx=10)

    merch_rows = [
        ("Jester", jester, set_jester),
        ("Mari", mari, set_mari),
        ("Rin", rin, set_rin),
    ]
    for i, (label, var, cmd) in enumerate(merch_rows):
        col_label = i * 1
        # layout: Jester | Mari | Rin across bottom
        customtkinter.CTkLabel(tlw, text=label, font=font20).grid(
            column=i if i < 2 else 2,
            row=10,
            padx=(10, 0),
            pady=6,
            sticky="w",
        )
        customtkinter.CTkOptionMenu(
            tlw, values=opts, font=font20, variable=var, command=cmd, width=120
        ).grid(
            row=10,
            column=(1 if i == 0 else (1 if i == 1 else 3)),
            sticky="w",
            padx=10,
            pady=6,
        )

    # cleaner merchant row
    for w in tlw.grid_slaves(row=10):
        w.grid_forget()

    customtkinter.CTkLabel(tlw, text="Jester", font=font20).grid(
        column=0, row=10, padx=(10, 0), pady=6, sticky="w"
    )
    customtkinter.CTkOptionMenu(
        tlw, values=opts, font=font20, variable=jester, command=set_jester, width=120
    ).grid(row=10, column=1, sticky="w", padx=10, pady=6)

    customtkinter.CTkLabel(tlw, text="Mari", font=font20).grid(
        column=2, row=10, padx=(10, 0), pady=6, sticky="w"
    )
    customtkinter.CTkOptionMenu(
        tlw, values=opts, font=font20, variable=mari, command=set_mari, width=120
    ).grid(row=10, column=3, sticky="w", padx=10, pady=6)

    customtkinter.CTkLabel(tlw, text="Rin", font=font20).grid(
        column=0, row=11, padx=(10, 0), pady=6, sticky="w"
    )
    customtkinter.CTkOptionMenu(
        tlw, values=opts, font=font20, variable=rin, command=set_rin, width=120
    ).grid(row=11, column=1, sticky="w", padx=10, pady=6)

    tlw.after(0, tlw.focus)
    tlw.after(100, lambda: tlw.resizable(False, False))
    tlw.after(
        250, lambda: tlw.iconbitmap(icon_path) if os.path.exists(icon_path) else None
    )

def init():
    global roblox_open, started, paused, roblox_username

    if roblox_username.get().strip() == "":
        ctypes.windll.user32.MessageBoxW(
            0,
            "hey so it looks like your roblox username field was left empty, i'm only putting this message here because i have to put something here but please put your username in the field thanks",
            "Warning",
            0,
        )

    if paused:
        paused = False
        root.title("Tung Tung Macro - Running")

    if started:
        return

    webhook_field.configure(state="disabled", text_color="gray")
    ps_field.configure(state="disabled", text_color="gray")
    discid_field.configure(state="disabled", text_color="gray")
    username_field.configure(state="disabled", text_color="gray")

    config.set("Webhook", "webhook_url", webhookURL.get())
    config.set("Webhook", "private_server", psURL.get())
    config.set("Webhook", "discord_user_id", discID.get())

    with open(config_name, "w") as configfile:
        config.write(configfile)

    starting_embed = discord_webhook.DiscordEmbed(
        description="[" + time.strftime("%H:%M:%S") + "]: Macro started!"
    )
    starting_embed.set_footer(
        text="Tung Tung Macro | v1.2",
        icon_url="https://i.ibb.co/VpM5CC6D/download-1.png",
    )

    if multi_webhook.get() != "1":
        if "discord" not in webhookURL.get() or "https://" not in webhookURL.get():
            ctypes.windll.user32.MessageBoxW(
                0, "Invalid or missing webhook link.", "Error", 0
            )
            stop()
            return
        starting_webhook = discord_webhook.DiscordWebhook(url=webhookURL.get())
        starting_webhook.add_embed(starting_embed)
        starting_webhook.execute()
    else:
        for url in webhook_urls:
            starting_webhook = discord_webhook.DiscordWebhook(url=url)
            starting_webhook.add_embed(starting_embed)
            starting_webhook.execute()

    if discID.get() and not discID.get().isnumeric():
        ctypes.windll.user32.MessageBoxW(
            0,
            "Discord User ID should only be a number.\nIf it is something else, such as @everyone, or your username, that is not your Discord User ID.",
            "Error",
            0,
        )
        stop()
        return

    started = True

    if is_roblox_running():
        roblox_open = True
        logger.info("Roblox is open.")
        print("Roblox is open.")
        root.title("Tung Tung Macro - Running")
    else:
        logger.info("Roblox is closed, waiting for Roblox to start...")
        print("Roblox is closed, waiting for Roblox to start...")
        root.title("Tung Tung Macro - No Roblox Detected")
        while True:
            if not stopped:
                root.update()
            else:
                if not destroyed:
                    root.destroy()
                sys.exit()
            if is_roblox_running():
                break
            time.sleep(0.1)

    if not roblox_open:
        if roblox_version == "player":
            logger.info("Detected Roblox Player.")
            print("Detected Roblox Player.")
            time.sleep(1.5)
        else:
            logger.info("Detected Roblox Microsoft Store.")
            print("Detected Roblox Microsoft Store.")
            time.sleep(3.5)

    latest_log = get_latest_log_file()
    if not latest_log:
        logger.info("No log files found.")
        print("No log files found.")
        return

    with open(latest_log, "r", encoding="utf-8", errors="ignore") as file:
        print(f"Using log file: {latest_log}")
        print()
        logger.info(f"Using log file: {latest_log}")
        root.title("Tung Tung Macro - Running")
        check_for_hover_text(file)


# ---------- UI ----------
tabview.set("Webhook")
root.geometry("505x410")
tabview.configure(width=505, height=318)
tabview.grid(row=0, column=0, padx=0, pady=0, sticky="nw")
tabview.grid_propagate(False)

try:
    tabview._segmented_button.configure(
        font=customtkinter.CTkFont(family="Segoe UI", size=15, weight="bold"),
        fg_color="#0b1020",
        selected_color="#3b82f6",
        selected_hover_color="#2563eb",
        unselected_color="#0b1020",
        unselected_hover_color="#182033",
    )
except Exception:
    pass

LABEL_FONT = customtkinter.CTkFont(family="Segoe UI Semibold", size=14)
ENTRY_FONT = customtkinter.CTkFont(family="Segoe UI", size=15)
BUTTON_FONT = customtkinter.CTkFont(family="Segoe UI", size=16, weight="bold")
CHECKBOX_FONT = customtkinter.CTkFont(family="Segoe UI", size=15, weight="bold")
CREDITS_FONT = customtkinter.CTkFont(family="Segoe UI", size=15, weight="bold")

webhook_tab = tabview.tab("Webhook")
macro_tab = tabview.tab("Macro")
merchants_tab = tabview.tab("Merchants")
credits_tab = tabview.tab("Credits")
# heheheha

webhook_label = customtkinter.CTkLabel(
    webhook_tab, text="Webhook URL", font=LABEL_FONT, text_color="#cbd5e1"
)
webhook_label.grid(row=0, column=0, padx=(12, 0), pady=(12, 0), sticky="w")

webhook_field = customtkinter.CTkEntry(
    webhook_tab,
    width=255,
    height=34,
    corner_radius=9,
    border_width=1,
    fg_color="#151823",
    border_color="#2e3447",
    text_color="#f1f5f9",
    placeholder_text_color="#7c8599",
    font=ENTRY_FONT,
    textvariable=webhookURL,
)
webhook_field.grid(row=0, column=1, padx=(12, 0), pady=(10, 0), sticky="w")

if multi_webhook.get() == "1":
    webhook_field.configure(state="disabled", text_color="gray")
    webhookURL.set("Multi-Webhook On")

ps_label = customtkinter.CTkLabel(
    webhook_tab, text="Private Server URL", font=LABEL_FONT, text_color="#cbd5e1"
)
ps_label.grid(row=1, column=0, padx=(12, 0), pady=(12, 0), sticky="w")

ps_field = customtkinter.CTkEntry(
    webhook_tab,
    width=255,
    height=34,
    corner_radius=9,
    border_width=1,
    fg_color="#151823",
    border_color="#2e3447",
    text_color="#f1f5f9",
    placeholder_text_color="#7c8599",
    font=ENTRY_FONT,
    textvariable=psURL,
)
ps_field.grid(row=1, column=1, padx=(12, 0), pady=(10, 0), sticky="w")

discid_label = customtkinter.CTkLabel(
    webhook_tab, text="Discord User ID", font=LABEL_FONT, text_color="#cbd5e1"
)
discid_label.grid(row=2, column=0, padx=(12, 0), pady=(12, 0), sticky="w")

discid_field = customtkinter.CTkEntry(
    webhook_tab,
    width=255,
    height=34,
    corner_radius=9,
    border_width=1,
    fg_color="#151823",
    border_color="#2e3447",
    text_color="#f1f5f9",
    placeholder_text_color="#7c8599",
    font=ENTRY_FONT,
    textvariable=discID,
)
discid_field.grid(row=2, column=1, padx=(12, 0), pady=(10, 0), sticky="w")

username_label = customtkinter.CTkLabel(
    macro_tab, text="Roblox Username", font=LABEL_FONT, text_color="#cbd5e1"
)
username_label.grid(row=0, column=0, padx=(12, 0), pady=(12, 0), sticky="w")

username_field = customtkinter.CTkEntry(
    macro_tab,
    width=255,
    height=34,
    corner_radius=9,
    border_width=1,
    fg_color="#151823",
    border_color="#2e3447",
    text_color="#f1f5f9",
    placeholder_text_color="#7c8599",
    font=ENTRY_FONT,
    textvariable=roblox_username,
)
username_field.grid(row=0, column=1, padx=(12, 0), pady=(10, 0), sticky="w")

biome_button = customtkinter.CTkButton(
    macro_tab,
    text="Configure Pings",
    font=BUTTON_FONT,
    width=165,
    height=34,
    corner_radius=9,
    fg_color="#3b82f6",
    hover_color="#2563eb",
    text_color="white",
    command=manage_tlw,
)
biome_button.grid(
    row=3, column=0, columnspan=2, padx=(12, 0), pady=(14, 0), sticky="w"
)

# ---------- Merchants tab ----------
merchants_tab.grid_columnconfigure(0, weight=1)

merch_title = customtkinter.CTkLabel(
    merchants_tab,
    text="Merchant Alerts",
    font=LABEL_FONT,
    text_color="#cbd5e1",
)
merch_title.grid(row=0, column=0, columnspan=2, padx=(12, 0), pady=(8, 0), sticky="w")

merch_hint = customtkinter.CTkLabel(
    merchants_tab,
    text="Message = webhook  |  Ping = ping you  |  Nothing = off",
    font=customtkinter.CTkFont(family="Segoe UI", size=11),
    text_color="#7c8599",
)
merch_hint.grid(row=1, column=0, columnspan=2, padx=(12, 0), pady=(2, 4), sticky="w")

jester_label = customtkinter.CTkLabel(
    merchants_tab, text="Jester", font=LABEL_FONT, text_color="#cbd5e1"
)
jester_label.grid(row=2, column=0, padx=(12, 0), pady=(4, 0), sticky="w")
jester_menu = customtkinter.CTkOptionMenu(
    merchants_tab,
    values=["Message", "Ping", "Nothing"],
    variable=jester,
    command=set_jester,
    width=160,
    height=30,
    font=ENTRY_FONT,
)
jester_menu.grid(row=2, column=1, padx=(12, 0), pady=(4, 0), sticky="w")

mari_label = customtkinter.CTkLabel(
    merchants_tab, text="Mari", font=LABEL_FONT, text_color="#cbd5e1"
)
mari_label.grid(row=3, column=0, padx=(12, 0), pady=(4, 0), sticky="w")
mari_menu = customtkinter.CTkOptionMenu(
    merchants_tab,
    values=["Message", "Ping", "Nothing"],
    variable=mari,
    command=set_mari,
    width=160,
    height=30,
    font=ENTRY_FONT,
)
mari_menu.grid(row=3, column=1, padx=(12, 0), pady=(4, 0), sticky="w")

rin_label = customtkinter.CTkLabel(
    merchants_tab, text="Rin (broken)", font=LABEL_FONT, text_color="#cbd5e1"
)
rin_label.grid(row=4, column=0, padx=(12, 0), pady=(4, 0), sticky="w")
rin_menu = customtkinter.CTkOptionMenu(
    merchants_tab,
    values=["Message", "Ping", "Nothing"],
    variable=rin,
    command=set_rin,
    width=160,
    height=30,
    font=ENTRY_FONT,
)
rin_menu.grid(row=4, column=1, padx=(12, 0), pady=(4, 0), sticky="w")

merchant_fix_status = customtkinter.CTkLabel(
    merchants_tab,
    text="Status: checking...",
    font=customtkinter.CTkFont(family="Segoe UI", size=11),
    text_color="#94a3b8",
)
merchant_fix_status.grid(
    row=5,
    column=1,
    padx=(12, 0),
    pady=(10, 0),
    sticky="w",
)

merchant_fix_button = customtkinter.CTkButton(
    merchants_tab,
    text="Apply Merchant Fix",
    font=customtkinter.CTkFont(family="Segoe UI Semibold", size=13),
    width=160,
    height=30,
    corner_radius=8,
    fg_color="#3b82f6",
    hover_color="#2563eb",
    text_color="#ffffff",
    command=apply_merchant_fix,
)
merchant_fix_button.grid(
    row=6,
    column=1,
    padx=(12, 0),
    pady=(6, 0),
    sticky="w",
)

merchant_fix_note = customtkinter.CTkLabel(
    merchants_tab,
    text="Admin required. Restart Roblox after apply/remove.",
    font=customtkinter.CTkFont(family="Segoe UI", size=10),
    text_color="#7c8599",
    wraplength=180,
    justify="left",
)
merchant_fix_note.grid(
    row=7,
    column=1,
    padx=(12, 0),
    pady=(4, 0),
    sticky="w",
)

# Set correct button/status on startup
refresh_merchant_fix_ui()

pfp_path = os.path.join(dirname, "str0ngerwizard.png")
if os.path.exists(pfp_path):
    max_pfp = customtkinter.CTkImage(dark_image=Image.open(pfp_path), size=(70, 70))
    max_pfp_label = customtkinter.CTkLabel(credits_tab, image=max_pfp, text="")
    max_pfp_label.grid(row=0, column=0, padx=(18, 0), pady=(28, 0), sticky="w")

credits_frame = customtkinter.CTkFrame(credits_tab, fg_color="transparent")
credits_frame.grid(row=0, column=1, padx=(8, 0), pady=(44, 0), sticky="w")

max_label = customtkinter.CTkLabel(
    credits_frame,
    text="Str0ngerWizard - Creator",
    font=CREDITS_FONT,
    text_color="#e5e7eb",
)
max_label.grid(row=0, column=0, padx=0, pady=0, sticky="w")

# ---------- Ko-fi donation link ----------
KOFI_URL = "https://ko-fi.com/str0ngerwizard"
kofi_icon_path = os.path.join(dirname, "kofi.png")
kofi_icon = None

# Put a 24x24 Ko-fi PNG named "kofi.png" next to this Python script.
# If it is missing, the donation button still works; it just shows no icon.
if os.path.exists(kofi_icon_path):
    try:
        kofi_icon = customtkinter.CTkImage(
            light_image=Image.open(kofi_icon_path).convert("RGBA"),
            dark_image=Image.open(kofi_icon_path).convert("RGBA"),
            size=(22, 22),
        )
    except Exception as e:
        print(f"Ko-fi icon failed to load: {e}")

donate_button = customtkinter.CTkButton(
    credits_frame,
    text="Donate here: https://ko-fi.com/str0ngerwizard",
    image=kofi_icon,
    compound="left",
    anchor="w",
    command=lambda: open_url(KOFI_URL),
    font=customtkinter.CTkFont(family="Segoe UI", size=12),
    text_color="#9bbcff",
    fg_color="transparent",
    hover_color="#20283a",
    corner_radius=7,
    height=30,
    width=350,
)

donate_button.grid(
    row=1,
    column=0,
    padx=(0, 0),
    pady=(8, 0),
    sticky="w",
)

button_frame = customtkinter.CTkFrame(root, fg_color="transparent")
button_frame.place(x=8, y=372)

start_button = customtkinter.CTkButton(
    button_frame,
    text="Start",
    font=BUTTON_FONT,
    width=88,
    height=30,
    corner_radius=8,
    fg_color="#22c55e",
    hover_color="#16a34a",
    text_color="white",
    command=init,
)
start_button.grid(row=0, column=0, padx=(0, 3), pady=0)

pause_button = customtkinter.CTkButton(
    button_frame,
    text="Pause",
    font=BUTTON_FONT,
    width=88,
    height=30,
    corner_radius=8,
    fg_color="#f59e0b",
    hover_color="#d97706",
    text_color="white",
    command=pause,
)
pause_button.grid(row=0, column=1, padx=3, pady=0)

stop_button = customtkinter.CTkButton(
    button_frame,
    text="Stop",
    font=BUTTON_FONT,
    width=88,
    height=30,
    corner_radius=8,
    fg_color="#ef4444",
    hover_color="#dc2626",
    text_color="white",
    command=stop,
)
stop_button.grid(row=0, column=2, padx=(3, 0), pady=0)

root.bind("<Destroy>", lambda event: x_stop())
root.bind("<Button-1>", lambda e: e.widget.focus_set())

tabview.lift()
button_frame.lift()
root.mainloop()
