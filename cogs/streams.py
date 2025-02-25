import asyncio
import os
import re
from collections import defaultdict
from random import choice
from string import ascii_letters

import aiohttp
import discord
from discord.ext import commands, tasks
from loguru import logger

from .utils.chat_formatting import escape_mass_mentions
from .utils.dataIO import dataIO


class StreamsError(Exception):
    pass


class StreamNotFound(StreamsError):
    pass


class APIError(StreamsError):
    pass


class InvalidCredentials(StreamsError):
    pass


class OfflineStream(StreamsError):
    pass


class Streams(commands.Cog):
    """Streams
    Alerts for a variety of streaming services"""

    async def cog_before_invoke(self, ctx):
        if not os.path.exists("data/streams"):
            print("Creating data/streams folder...")
            os.makedirs("data/streams")
        stream_files = (
            "twitch.json",
            "beam.json"
        )
        for filename in stream_files:
            if not dataIO.is_valid_json("data/streams/" + filename):
                logger.debug("Creating empty {}...".format(filename))
                dataIO.save_json("data/streams/" + filename, [])
        f = "data/streams/settings.json"
        if not dataIO.is_valid_json(f):
            logger.debug("Creating empty settings.json...")
            dataIO.save_json(f, {})

    def __init__(self, bot):
        self.bot = bot
        self.stream_checker.start()
        self.twitch_streams = dataIO.load_json("data/streams/twitch.json")
        self.mixer_streams = dataIO.load_json("data/streams/beam.json")
        settings = dataIO.load_json("data/streams/settings.json")
        self.settings = defaultdict(dict, settings)
        self.messages_cache = defaultdict(list)

    @commands.command()
    async def twitch(self, ctx, stream: str):
        """Checks if twitch stream is online"""
        stream = escape_mass_mentions(stream)
        regex = r'^(https?\:\/\/)?(www\.)?(twitch\.tv\/)'
        stream = re.sub(regex, '', stream)
        try:
            data = await self.fetch_twitch_ids(stream, raise_if_none=True)
            embed = await self.twitch_online(data[0]["_id"])
        except OfflineStream:
            await ctx.send(stream + " is offline.")
        except StreamNotFound:
            await ctx.send("That stream doesn't exist.")
        except APIError:
            await ctx.send("Error contacting the API.")
        except InvalidCredentials:
            await ctx.send("Owner: Client-ID is invalid or not set. "
                           "See `{}streamset twitchtoken`"
                           "".format(ctx.prefix))
        else:
            await ctx.send(embed=embed)

    @commands.command()
    async def mixer(self, ctx, stream: str):
        """Checks if mixer stream is online"""
        stream = escape_mass_mentions(stream)
        regex = r'^(https?\:\/\/)?(www\.)?(mixer\.com\/)'
        stream = re.sub(regex, '', stream)
        try:
            embed = await self.mixer_online(stream)
        except OfflineStream:
            await ctx.send(stream + " is offline.")
        except StreamNotFound:
            await ctx.send("That stream doesn't exist.")
        except APIError:
            await ctx.send("Error contacting the API.")
        else:
            await ctx.send(embed=embed)

    @commands.group(no_pm=True)
    async def streamalert(self, ctx):
        """Adds/removes stream alerts from the current channel"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @streamalert.command(name="twitch")
    async def twitch_alert(self, ctx, stream: str):
        """Adds/removes twitch alerts from the current channel"""
        stream = escape_mass_mentions(stream)
        regex = r'^(https?\:\/\/)?(www\.)?(twitch\.tv\/)'
        stream = re.sub(regex, '', stream)
        channel = ctx.channel
        try:
            data = await self.fetch_twitch_ids(stream, raise_if_none=True)
        except StreamNotFound:
            await ctx.send("That stream doesn't exist.")
            return
        except APIError:
            await ctx.send("Error contacting the API.")
            return
        except InvalidCredentials:
            await ctx.send("Owner: Client-ID is invalid or not set. "
                           "See `{}streamset twitchtoken`"
                           "".format(ctx.prefix))
            return

        enabled = self.enable_or_disable_if_active(self.twitch_streams,
                                                   stream,
                                                   channel,
                                                   _id=data[0]["_id"])

        if enabled:
            await ctx.send("Alert activated. I will notify this channel "
                           "when {} is live.".format(stream))
        else:
            await ctx.send("Alert has been removed from this channel.")

        dataIO.save_json("data/streams/twitch.json", self.twitch_streams)

    @streamalert.command(name="mixer")
    async def mixer_alert(self, ctx, stream: str):
        """Adds/removes mixer alerts from the current channel"""
        stream = escape_mass_mentions(stream)
        regex = r'^(https?\:\/\/)?(www\.)?(mixer\.com\/)'
        stream = re.sub(regex, '', stream)
        channel = ctx.channel
        try:
            await self.mixer_online(stream)
        except StreamNotFound:
            await ctx.send("That stream doesn't exist.")
            return
        except APIError:
            await ctx.send("Error contacting the API.")
            return
        except OfflineStream:
            pass

        enabled = self.enable_or_disable_if_active(self.mixer_streams,
                                                   stream,
                                                   channel)

        if enabled:
            await ctx.send("Alert activated. I will notify this channel "
                           "when {} is live.".format(stream))
        else:
            await ctx.send("Alert has been removed from this channel.")

        dataIO.save_json("data/streams/beam.json", self.mixer_streams)

    @streamalert.command(name="stop", )
    async def stop_alert(self, ctx):
        """Stops all streams alerts in the current channel"""
        channel = ctx.channel

        streams = (
            self.twitch_streams,
            self.mixer_streams
        )

        for stream_type in streams:
            to_delete = []

            for s in stream_type:
                if channel.id in s["CHANNELS"]:
                    s["CHANNELS"].remove(channel.id)
                    if not s["CHANNELS"]:
                        to_delete.append(s)

            for s in to_delete:
                stream_type.remove(s)

        dataIO.save_json("data/streams/twitch.json", self.twitch_streams)
        dataIO.save_json("data/streams/beam.json", self.mixer_streams)

        await ctx.send("There will be no more stream alerts in this "
                       "channel.")

    @commands.group()
    async def streamset(self, ctx):
        """Stream settings"""
        if ctx.invoked_subcommand is None:
            await self.bot.send_cmd_help(ctx)

    @streamset.command()
    @commands.has_permissions(administrator=True)
    async def twitchtoken(self, ctx, token: str):
        """Sets the Client ID for twitch
        To do this, follow these steps:
          1. Go to this page: https://dev.twitch.tv/dashboard/apps.
          2. Click 'Register Your Application'
          3. Enter a name, set the OAuth Redirect URI to 'http://localhost', and
             select an Application Category of your choosing.
          4. Click 'Register', and on the following page, copy the Client ID.
          5. Paste the Client ID into this command. Done!
        """
        self.settings["TWITCH_TOKEN"] = token
        dataIO.save_json("data/streams/settings.json", self.settings)
        await ctx.send('Twitch Client-ID set.')

    @streamset.command(no_pm=True)
    async def mention(self, ctx, *, mention_type: str):
        """Sets mentions for stream alerts
        Types: everyone, here, none"""
        guild = ctx.guild
        mention_type = mention_type.lower()

        if mention_type in ("everyone", "here"):
            self.settings[guild.id]["MENTION"] = "@" + mention_type
            await ctx.send("When a stream is online @\u200b{} will be "
                           "mentioned.".format(mention_type))
        elif mention_type == "none":
            self.settings[guild.id]["MENTION"] = ""
            await ctx.send("Mentions disabled.")
        else:
            await self.bot.send_cmd_help(ctx)

        dataIO.save_json("data/streams/settings.json", self.settings)

    @streamset.command(no_pm=True)
    async def autodelete(self, ctx):
        """Toggles automatic notification deletion for streams that go offline"""
        guild = ctx.guild
        settings = self.settings[guild.id]
        current = settings.get("AUTODELETE", True)
        settings["AUTODELETE"] = not current
        if settings["AUTODELETE"]:
            await ctx.send("Notifications will be automatically deleted "
                           "once the stream goes offline.")

        else:
            await ctx.send("Notifications won't be deleted anymore.")

        dataIO.save_json("data/streams/settings.json", self.settings)

    async def twitch_online(self, stream):
        session = aiohttp.ClientSession()
        url = "https://api.twitch.tv/kraken/streams/" + stream
        header = {
            'Client-ID': self.settings.get("TWITCH_TOKEN", ""),
            'Accept': 'application/vnd.twitchtv.v5+json'
        }

        async with session.get(url, headers=header) as r:
            data = await r.json(encoding='utf-8')
        await session.close()
        if r.status == 200:
            if data["stream"] is None:
                raise OfflineStream()
            return self.twitch_embed(data)
        elif r.status == 400:
            raise InvalidCredentials()
        elif r.status == 404:
            raise StreamNotFound()
        else:
            raise APIError()

    async def mixer_online(self, stream):
        url = "https://mixer.com/api/v1/channels/" + stream

        async with aiohttp.get(url) as r:
            data = await r.json(encoding='utf-8')
        if r.status == 200:
            if data["online"] is True:
                return self.mixer_embed(data)
            else:
                raise OfflineStream()
        elif r.status == 404:
            raise StreamNotFound()
        else:
            raise APIError()

    async def fetch_twitch_ids(self, *streams, raise_if_none=False):
        def chunks(l):
            for i in range(0, len(l), 100):
                yield l[i:i + 100]

        base_url = "https://api.twitch.tv/kraken/users?login="
        header = {
            'Client-ID': self.settings.get("TWITCH_TOKEN", ""),
            'Accept': 'application/vnd.twitchtv.v5+json'
        }
        results = []

        for streams_list in chunks(streams):
            session = aiohttp.ClientSession()
            url = base_url + ",".join(streams_list)
            async with session.get(url, headers=header) as r:
                data = await r.json(encoding='utf-8')
            if r.status == 200:
                results.extend(data["users"])
            elif r.status == 400:
                raise InvalidCredentials()
            else:
                raise APIError()
            await session.close()

        if not results and raise_if_none:
            raise StreamNotFound()

        return results

    def twitch_embed(self, data):
        channel = data["stream"]["channel"]
        url = channel["url"]
        logo = channel["logo"]
        if logo is None:
            logo = "https://static-cdn.jtvnw.net/jtv_user_pictures/xarth/404_user_70x70.png"
        status = channel["status"]
        if not status:
            status = "Untitled broadcast"
        embed = discord.Embed(title=status, url=url, color=0x6441A4)
        embed.set_author(name=channel["display_name"])
        embed.add_field(name="Followers", value=channel["followers"])
        embed.add_field(name="Total views", value=channel["views"])
        embed.set_thumbnail(url=logo)
        if data["stream"]["preview"]["medium"]:
            embed.set_image(url=data["stream"]["preview"]["medium"] + self.rnd_attr())
        if channel["game"]:
            embed.set_footer(text="Playing: " + channel["game"])
        return embed

    def mixer_embed(self, data):
        default_avatar = ("https://mixer.com/_latest/assets/images/main/"
                          "avatars/default.jpg")
        user = data["user"]
        url = "https://mixer.com/" + data["token"]
        embed = discord.Embed(title=data["name"], url=url, color=0x4C90F3)
        embed.set_author(name=user["username"])
        embed.add_field(name="Followers", value=data["numFollowers"])
        embed.add_field(name="Total views", value=data["viewersTotal"])
        if user["avatarUrl"]:
            embed.set_thumbnail(url=user["avatarUrl"])
        else:
            embed.set_thumbnail(url=default_avatar)
        if data["thumbnail"]:
            embed.set_image(url=data["thumbnail"]["url"] + self.rnd_attr())
        if data["type"] is not None:
            embed.set_footer(text="Playing: " + data["type"]["name"])
        return embed

    def enable_or_disable_if_active(self, streams, stream, channel, _id=None):
        """Returns True if enabled or False if disabled"""
        for i, s in enumerate(streams):
            stream_id = s.get("ID")
            if stream_id and _id:  # ID is available, matching by ID is
                if stream_id != _id:  # preferable
                    continue
            else:  # ID unavailable, matching by name
                if s["NAME"] != stream:
                    continue
            if channel.id in s["CHANNELS"]:
                streams[i]["CHANNELS"].remove(channel.id)
                if not s["CHANNELS"]:
                    streams.remove(s)
                return False
            else:
                streams[i]["CHANNELS"].append(channel.id)
                return True

        data = {"CHANNELS": [channel.id],
                "NAME": stream,
                "ALREADY_ONLINE": False}

        if _id:
            data["ID"] = _id

        streams.append(data)

        return True

    @tasks.loop(seconds=5.0)
    async def stream_checker(self):
        await self.bot.wait_until_ready()
        CHECK_DELAY = 60
        try:
            await self._migration_twitch_v5()
        except InvalidCredentials:
            print("Error during conversion of twitch usernames to IDs: "
                  "invalid token")
        except Exception as e:
            print("Error during conversion of twitch usernames to IDs: "
                  "{}".format(e))
        save = False
        streams = ((self.twitch_streams, self.twitch_online),
                   (self.mixer_streams, self.mixer_online))

        for streams_list, parser in streams:
            if parser == self.twitch_online:
                _type = "ID"
            else:
                _type = "NAME"
            for stream in streams_list:
                if _type not in stream:
                    continue
                key = (parser, stream[_type])
                try:
                    embed = await parser(stream[_type])
                except OfflineStream:
                    if stream["ALREADY_ONLINE"]:
                        stream["ALREADY_ONLINE"] = False
                        save = True
                        await self.delete_old_notifications(key)
                except:  # We don't want our task to die
                    continue
                else:
                    if stream["ALREADY_ONLINE"]:
                        continue
                    save = True
                    stream["ALREADY_ONLINE"] = True
                    messages_sent = []
                    for channel_id in stream["CHANNELS"]:
                        channel = self.bot.get_channel(channel_id)
                        if channel is None:
                            continue
                        mention = self.settings.get(channel.guild.id, {}).get("MENTION", "")
                        can_speak = channel.permissions_for(channel.guild.me).send_messages
                        message = mention + " {} is live!".format(stream["NAME"])
                        if channel and can_speak:
                            m = await channel.send(message, embed=embed)
                            messages_sent.append(m)
                    self.messages_cache[key] = messages_sent

            if save:
                dataIO.save_json("data/streams/twitch.json", self.twitch_streams)
                dataIO.save_json("data/streams/beam.json", self.mixer_streams)

            await asyncio.sleep(CHECK_DELAY)

    @commands.has_permissions(manage_messages=True)
    async def delete_old_notifications(self, key):
        for message in self.messages_cache[key]:
            guild = message.guild
            settings = self.settings.get(guild.id, {})
            is_enabled = settings.get("AUTODELETE", True)
            try:
                if is_enabled:
                    await self.bot.delete_message(message)
            except:
                pass

        del self.messages_cache[key]

    def rnd_attr(self):
        """Avoids Discord's caching"""
        return "?rnd=" + "".join([choice(ascii_letters) for i in range(6)])

    async def _migration_twitch_v5(self):
        #  Migration of old twitch streams to API v5
        to_convert = []
        for stream in self.twitch_streams:
            if "ID" not in stream:
                to_convert.append(stream["NAME"])

        if not to_convert:
            return

        results = await self.fetch_twitch_ids(*to_convert)

        for stream in self.twitch_streams:
            for result in results:
                if stream["NAME"].lower() == result["name"].lower():
                    stream["ID"] = result["_id"]

        # We might as well delete the invalid / renamed ones
        self.twitch_streams = [s for s in self.twitch_streams if "ID" in s]

        dataIO.save_json("data/streams/twitch.json", self.twitch_streams)


def setup(bot):
    n = Streams(bot)
    loop = asyncio.get_event_loop()
    loop.create_task(n.stream_checker())
    bot.add_cog(n)
