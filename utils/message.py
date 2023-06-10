"""Useful functions for sending messages to the user."""
import base64
import datetime
import time
import traceback
from typing import List, Optional

import interactions
from interactions import ActionRow

from .database import Database
from .logger import Logger
from .server import Server
from .text import Text
from .twitch import Twitch


class Message:
    def __init__(
            self,
            logger: "Logger",
            db: "Database",
            text: "Text",
            server: "Server",
            twitch: "Twitch",
    ):
        self.logger = logger
        self.db = db
        self.text = text
        self.server = server
        self.twitch = twitch

        self.RED = 0xFF0000  # error
        self.GREEN = 0x00FF00  # success
        self.YELLOW = 0xFFFF00  # warning
        self.BLUE = 0x0000FF  # info
        self.PINK = 0xFFC0CB  # offline

    @staticmethod
    def buttons(*args: bool | str) -> List[ActionRow]:
        """Return disabled buttons (True = disabled)

        Args:
            *args (bool | str): The buttons to disable and the link to MCStatus.io
                order: next, previous, jump, update, players, sort, join

        Returns:
            [
                interactions.ActionRow(): Next, Previous, Jump to, Update
                interactions.ActionRow(): Show Players
                interactions.StringSelectMenu(): Sort
                interactions.Button(): Join
            ]
        """
        if len(args) != 7:
            disabled = [
                True,
                True,
                True,
                True,
                True,
                True,
                True,
            ]
        else:
            disabled = list(args)

        # button: Next, Previous, Show Players
        rows = [
            interactions.ActionRow(
                interactions.Button(
                    style=interactions.ButtonStyle.PRIMARY,
                    emoji="⬅️",
                    custom_id="previous",
                    disabled=disabled[1],
                ),
                interactions.Button(
                    style=interactions.ButtonStyle.PRIMARY,
                    emoji="➡️",
                    custom_id="next",
                    disabled=disabled[0],
                ),
                interactions.Button(
                    style=interactions.ButtonStyle.PRIMARY,
                    label="Jump",
                    custom_id="jump",
                    disabled=disabled[2],
                ),
            ),
            interactions.ActionRow(
                interactions.Button(
                    style=interactions.ButtonStyle.SECONDARY,
                    label="Players",
                    custom_id="players",
                    disabled=disabled[4],
                ),
                interactions.Button(
                    style=interactions.ButtonStyle.SECONDARY,
                    emoji="🔄",
                    custom_id="update",
                    disabled=disabled[3],
                ),
                interactions.Button(
                    style=interactions.ButtonStyle.DANGER,
                    label="Sort",
                    custom_id="sort",
                    disabled=disabled[5],
                ),
            ),
        ]

        return rows

    async def async_embed(
            self,
            pipeline: list | dict,
            index: int,
            fast=True,
    ) -> Optional[dict]:
        """Return an embed

        Args:
            pipeline (list): The pipeline to use, or the server data
            index (int): The index of the embed
            fast (bool): Whether to return just the database values

        Returns:
            {
                "embed": interactions.Embed, # The embed
                "components": [interactions.ActionRow], # The buttons
            }
        """
        try:
            if type(pipeline) is dict:
                self.logger.print("[message.asyncEmbed] Server data provided")
                # server is not in db, and we got the server data
                data = pipeline
                pipeline = {
                    "your mother": "large",
                }
                total_servers = 1

                if data is None or data == {}:
                    return {
                        "embed": self.standard_embed(
                            title="Error",
                            description="No server found",
                            color=self.YELLOW,
                        ),
                        "components": self.buttons(),
                    }
            else:
                # server is in db
                total_servers = self.db.count(pipeline)

                if total_servers == 0:
                    self.logger.print("[message.asyncEmbed] No servers found")
                    return {
                        "embed": self.standard_embed(
                            title="Error",
                            description="No servers found",
                            color=self.YELLOW,
                        ),
                        "components": self.buttons(),
                    }

                if index >= total_servers:
                    index = 0

                data = self.db.get_doc_at_index(pipeline, index)

                if data is None:
                    self.logger.print(
                        "[message.asyncEmbed] No server found in db")
                    return {
                        "embed": self.standard_embed(
                            title="Error",
                            description="No server found",
                            color=self.YELLOW,
                        ),
                        "components": self.buttons(),
                    }

                if index >= total_servers:
                    index = 0

                data = self.db.get_doc_at_index(pipeline, index)

            # get the server status
            is_online = "🔴"
            data["cracked"] = None
            streams = []
            if type(pipeline) is dict and fast:
                # set all values to default
                data["description"] = {"text": "..."}
                data["players"] = {"online": 0, "max": 0}
                data["version"] = {"name": "...", "protocol": 0}
                data["favicon"] = None
                data["cracked"] = None
                data["hasForgeData"] = False
                data["lastSeen"] = 0
            elif not fast:
                try:
                    status = self.server.update(
                        host=data["ip"], port=data["port"]
                    )

                    if status is None:
                        # server is offline
                        data["cracked"] = None
                        data["description"] = self.text.motd_parse(
                            data["description"])
                    else:
                        # server is online
                        data.update(status)

                    # mark online if the server was lastSeen within 5 minutes
                    if data["lastSeen"] > time.time() - 300:
                        is_online = "🟢"
                except Exception as e:
                    self.logger.error("[message.asyncEmbed] Error: " + str(e))
                    self.logger.print(
                        f"[message.asyncEmbed] Full traceback: {traceback.format_exc()}"
                    )

                # try and see if any of the players are live-streaming
                if "sample" in data["players"]:
                    for player in data["players"]["sample"]:
                        stream = await self.twitch.get_stream(
                            user=player["name"].lower()
                        )
                        if stream != {}:
                            streams.append(stream)
            else:
                # isonline is yellow
                is_online = "🟡"
                data["description"] = self.text.motd_parse(data["description"])

            # get the server icon
            if is_online == "🟢" and "favicon" in data.keys():
                bits = (
                    data["favicon"].split(",")[1]
                    if "," in data["favicon"]
                    else data["favicon"]
                )
                with open("assets/favicon.png", "wb") as f:
                    f.write(base64.b64decode(bits))
            else:
                # copy the bytes from 'DefFavicon.png' to 'favicon.png'
                with open("assets/DefFavicon.png", "rb") as f, open(
                        "assets/favicon.png", "wb"
                ) as f2:
                    f2.write(f.read())

            # create the embed
            data["description"] = self.text.motd_parse(data["description"])
            domain = ""
            if "hostname" in data:
                domain = f"**Hostname:** `{data['hostname']}`\n"
            embed = self.standard_embed(
                title=f"{is_online} {data['ip']}:{data['port']}",
                description=f"{domain}```ansi\n{self.text.color_ansi(str(data['description']['text']))}\n```",
                color=(self.GREEN if is_online == "🟢" else self.PINK)
                if is_online != "🟡"
                else None,
            ).set_image(url="attachment://favicon.png")

            # set the footer to say the index, pipeline, and total servers
            embed.set_footer(
                f"Showing {index + 1} of {total_servers} servers",
            )
            embed.timestamp = self.text.time_now()
            with open("pipeline.ason", "w") as f:
                f.write(self.text.convert_json_to_string(pipeline))

            # add the version
            embed.add_field(
                name="Version",
                value=f"{self.text.c_filter(data['version']['name'])} ({data['version']['protocol']})",
                inline=True,
            )

            # add the player count
            embed.add_field(
                name="Players",
                value=f"{data['players']['online']}/{data['players']['max']}",
                inline=True,
            )

            # is cracked
            embed.add_field(
                name="Cracked",
                value="Yes" if data["cracked"] else "No",
                inline=True,
            )

            # is modded
            embed.add_field(
                name="Modded",
                value="Yes"
                if data["hasForgeData"] or "modpackData" in data.keys()
                else "No",
                inline=True,
            )

            # last online
            stamp: datetime.datetime = datetime.datetime.utcfromtimestamp(
                data["lastSeen"]
            )
            embed.add_field(
                name="Time since last scan",
                value=self.text.time_ago(stamp),
                inline=True,
            )

            # geolocation
            if "geo" in data:
                if ("country", "city") in data["geo"]:
                    embed.add_field(
                        name="Location",
                        value=f":flag_{data['geo']['country'].lower()}: {data['geo']['city']}",
                        inline=True,
                    )

            # add the streams
            if len(streams) > 0:
                embed.add_field(
                    name="Streams",
                    value="\n".join(
                        [f"[{stream['title']}]({stream['url']})" for stream in streams]
                    ),
                    inline=False,
                )

            return {
                "embed": embed,
                "components": self.buttons(
                    index + 1 >= total_servers,  # next
                    index <= 0,  # previous
                    total_servers <= 1,  # jump
                    type(pipeline) is dict,  # update
                    "sample" not in data["players"]
                    or type(pipeline) is dict,  # players
                    total_servers <= 1,  # sort
                    True,  # join
                )
                if not fast
                else self.buttons(
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                    True,
                ),
            }
        except Exception as e:
            self.logger.error(f"[message.asyncEmbed] {e}")
            self.logger.print(
                f"[message.asyncEmbed] Full traceback: {traceback.format_exc()}"
            )
            return None

    def standard_embed(
            self,
            title: str,
            description: str,
            color: int,
    ) -> interactions.Embed:
        """Return a standard embed

        Args:
            title (str): The title of the embed
            description (str): The description of the embed
            color (int): The color of the embed(
                RED: error
                GREEN: success
                YELLOW: warning
                BLUE: info
                PINK: offline
            )

        Returns:
            interactions.Embed: The embed
        """
        try:
            return interactions.Embed(
                title=title,
                description=description,
                color=color,
                timestamp=self.text.time_now(),
            )
        except Exception as e:
            self.logger.error(f"[message.standardEmbed] {e}")
            self.logger.print(
                f"[message.standardEmbed] Full traceback: {traceback.format_exc()}"
            )
            return interactions.Embed(
                title=title,
                description=description,
                timestamp=self.text.time_now(),
            )

    async def async_load_server(
            self,
            index: int,
            pipeline: dict | list,
            msg: interactions.Message,
    ) -> None:
        # first call the asyncEmbed function with fast
        stuff = await self.async_embed(pipeline=pipeline, index=index, fast=True)
        if stuff is None:
            await msg.edit(
                embed=self.standard_embed(
                    title="Error",
                    description="There was an error loading the server",
                    color=self.RED,
                ),
                file=None,
            )
            return

        # then send the embed
        await msg.edit(
            embed=stuff["embed"],
            components=stuff["components"],
            files=[
                interactions.File("assets/favicon.png"),
                interactions.File("pipeline.ason"),
            ],
        )

        # then call the asyncEmbed function again with slow
        stuff = await self.async_embed(pipeline=pipeline, index=index, fast=False)
        if stuff is None:
            await msg.edit(
                embed=self.standard_embed(
                    title="Error",
                    description="There was an error loading the server",
                    color=self.RED,
                ),
                file=None,
            )
            return

        # then send the embed
        await msg.edit(
            embed=stuff["embed"],
            components=stuff["components"],
            files=[
                interactions.File("assets/favicon.png"),
                interactions.File("pipeline.ason"),
            ],
        )
