import asyncio
import datetime
import json
import time
import traceback

import aiohttp
from interactions import (
    Extension,
    component_callback,
    ComponentContext,
    File,
    ShortText,
    Modal,
    StringSelectMenu,
    StringSelectOption,
    ActionRow,
    Button,
    ButtonStyle,
)
from interactions.ext.paginators import Paginator

from .Colors import *


class Buttons(Extension):
    def __init__(
        self,
        *_,
        mcLib,
        messageLib,
        playerLib,
        logger,
        databaseLib,
        serverLib,
        twitchLib,
        Scanner,
        textLib,
        cstats,
        azure_client_id,
        azure_redirect_uri,
        **kwargs,
    ):
        super().__init__()

        self.mcLib = mcLib
        self.messageLib = messageLib
        self.playerLib = playerLib
        self.logger = logger
        self.databaseLib = databaseLib
        self.serverLib = serverLib
        self.twitchLib = twitchLib
        self.Scanner = Scanner
        self.textLib = textLib
        self.cstats = cstats
        self.azure_client_id = azure_client_id
        self.azure_redirect_uri = azure_redirect_uri

    # button to get the next page of servers
    @component_callback("next")
    async def next_page(self, ctx: ComponentContext):
        msg = None
        try:
            org = ctx.message

            index, pipeline = await self.messageLib.get_pipe(org)

            await ctx.defer(edit_origin=True)

            self.logger.print(f"next page called")

            msg = await ctx.edit_origin(
                embed=self.messageLib.standard_embed(
                    title="Loading...",
                    description="Loading...",
                    color=BLUE,
                ),
                components=self.messageLib.buttons(),
                file=File(file="assets/loading.png", file_name="favicon.png"),
            )

            # get the pipeline and index from the message
            total = self.databaseLib.count(pipeline)
            if index + 1 >= total:
                index = 0
            else:
                index += 1

            msg = await msg.edit(
                embed=self.messageLib.standard_embed(
                    title="Loading...",
                    description=f"Loading server {index + 1} of {total}",
                    color=BLUE,
                ),
                components=self.messageLib.buttons(),
                file=None,
            )

            await self.messageLib.async_load_server(
                index=index,
                pipeline=pipeline,
                msg=msg,
            )
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.delete(message=msg)
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to get the next page of servers",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to get the previous page of servers
    @component_callback("previous")
    async def previous_page(self, ctx: ComponentContext):
        msg = None
        try:
            org = ctx.message
            index, pipeline = await self.messageLib.get_pipe(org)
            await ctx.defer(edit_origin=True)

            self.logger.print(f"previous page called")

            msg = await ctx.edit_origin(
                embed=self.messageLib.standard_embed(
                    title="Loading...",
                    description="Loading...",
                    color=BLUE,
                ),
                components=self.messageLib.buttons(),
                file=File(file="assets/loading.png", file_name="favicon.png"),
            )

            # get the pipeline and index from the message
            total = self.databaseLib.count(pipeline)
            if index - 1 >= 0:
                index -= 1
            else:
                index = total - 1

            msg = await msg.edit(
                embed=self.messageLib.standard_embed(
                    title="Loading...",
                    description=f"Loading server {index + 1} of {total}",
                    color=BLUE,
                ),
                components=self.messageLib.buttons(),
                file=None,
            )

            await self.messageLib.async_load_server(
                index=index,
                pipeline=pipeline,
                msg=msg,
            )
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.delete(message=msg)
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to get the previous page of servers",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to send the players that are online
    @component_callback("players")
    async def players(self, ctx: ComponentContext):
        try:
            org = ctx.message
            host, port = org.embeds[0].title.split(" ")[1].split(":")
            await ctx.defer(ephemeral=True)

            self.logger.print(f"players called")

            player_list = await self.playerLib.async_player_list(host, port)

            if player_list is None:
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="An error occurred while trying to get the players (server offline?)",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            # remove players that have duplicate names
            for player in player_list:
                if player_list.count(player) > 1:
                    player_list.remove(player)

            self.logger.print(f"Found {len(player_list)} players")

            # create a list of player lists that are 25 players long
            player_list_list = [
                player_list[i : i + 25] for i in range(0, len(player_list), 25)
            ]
            pages = []

            for player_list in player_list_list:
                embed = self.messageLib.standard_embed(
                    title=f"Players on {host}",
                    description=f"Found {len(player_list)} players",
                    color=BLUE,
                )
                for player in player_list:
                    online = "🟢" if player["online"] else "🔴"
                    if "lastSeen" in str(player):
                        time_ago = self.textLib.time_ago(
                            datetime.datetime.utcfromtimestamp(player["lastSeen"])
                        )
                    else:
                        time_ago = "Unknown"
                    embed.add_field(
                        name=f'{online} `{player["name"]}`',
                        value=f'`{player["id"]}` | Last Online: {time_ago}',
                        inline=True,
                    )

                pages.append(embed)

            pag = Paginator.create_from_embeds(ctx.bot, *pages, timeout=60)
            await pag.send(ctx)
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="An error occurred",
                        description="Wrong channel for this bot",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to get the players",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to jump to a specific index
    @component_callback("jump")
    async def jump(self, ctx: ComponentContext):
        org = None
        # when pressed should spawn a modal with a text input and then edit the message with the new index
        try:
            org = ctx.message

            self.logger.print(f"jump called")
            # get the files attached to the message
            index, pipeline = await self.messageLib.get_pipe(org)

            # get the total number of servers
            total = self.databaseLib.count(pipeline)

            # create the text input
            text_input = ShortText(
                label="Jump to index",
                placeholder=f"Enter a number between 1 and {total}",
                min_length=1,
                max_length=len(str(total)),
                custom_id="jump",
                required=True,
            )

            # create a modal
            modal = Modal(
                text_input,
                title="Jump",
            )

            # send the modal
            await ctx.send_modal(modal)

            try:
                # wait for the response
                modal_ctx = await ctx.bot.wait_for_modal(modal=modal, timeout=60)

                # get the response
                index = int(modal_ctx.responses["jump"])

                # check if the index is valid
                if index < 1 or index > total or not str(index).isnumeric():
                    self.logger.warning(f"Invalid index: {index}")
                    await ctx.send(
                        embed=self.messageLib.standard_embed(
                            title="Error",
                            description=f"Invalid index, must be between 1 and {total}",
                            color=RED,
                        ),
                        ephemeral=True,
                    )
                    return
                else:
                    await modal_ctx.send(
                        embed=self.messageLib.standard_embed(
                            title="Success",
                            description=f"Jumping to index {index}",
                            color=GREEN,
                        ),
                        ephemeral=True,
                    )

                # edit the message
                await self.messageLib.async_load_server(
                    index=index - 1,
                    pipeline=pipeline,
                    msg=org,
                )
            except asyncio.TimeoutError:
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="Timed out",
                        color=RED,
                    ),
                    ephemeral=True,
                )
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.delete(
                    message=org,
                )
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")
            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to jump to a specific index",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to change the sort method
    @component_callback("sort")
    async def sort(self, ctx: ComponentContext):
        try:
            org = ctx.message

            index, pipeline = await self.messageLib.get_pipe(org)

            self.logger.print(f"sort called")

            # get the pipeline
            self.logger.print(f"pipeline: {pipeline}")

            # send a message with a string menu that express after 60s
            string_menu = StringSelectMenu(
                StringSelectOption(
                    label="Player Count",
                    value="players",
                ),
                StringSelectOption(
                    label="Sample Count",
                    value="sample",
                ),
                StringSelectOption(
                    label="Player Limit",
                    value="limit",
                ),
                StringSelectOption(
                    label="Server Version ID",
                    value="version",
                ),
                StringSelectOption(
                    label="Last scan",
                    value="last_scan",
                ),
                StringSelectOption(
                    label="Random",
                    value="random",
                ),
                placeholder="Sort the servers by...",
                custom_id="sort_method",
                min_values=1,
                max_values=1,
                disabled=False,
            )

            msg = await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Sort",
                    description="Sort the servers by...",
                    color=BLUE,
                ),
                components=[
                    ActionRow(
                        string_menu,
                    ),
                ],
                ephemeral=True,
            )

            try:
                # wait for the response
                menu = await ctx.bot.wait_for_component(
                    timeout=60, components=string_menu
                )
            except asyncio.TimeoutError:
                await msg.delete(context=ctx)
                return
            else:
                # get the value
                value = menu.ctx.values[0]
                self.logger.print(f"sort method: {value}")
                sort_method = {}

                match value:
                    case "players":
                        sort_method = {"$sort": {"players.online": -1}}
                    case "sample":
                        sort_method = {"$sort": {"players.sample": -1}}
                    case "version":
                        sort_method = {"$sort": {"version": -1}}
                    case "last_scan":
                        sort_method = {"$sort": {"lastSeen": -1}}
                    case "random":
                        sort_method = {"$sample": {"size": 1000}}
                    case _:
                        await ctx.send(
                            embed=self.messageLib.standard_embed(
                                title="Error",
                                description="Invalid sort method",
                                color=RED,
                            ),
                            ephemeral=True,
                        )

                await msg.delete(context=ctx)
                msg = await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Success",
                        description=f"Sorting by `{value}`",
                        color=GREEN,
                    ),
                    ephemeral=True,
                )

                # loop through the pipeline and replace the sort method
                for i in range(len(pipeline)):
                    if "$sort" in pipeline[i] or "$sample" in pipeline[i]:
                        pipeline[i] = sort_method
                        break
                else:
                    pipeline.append(sort_method)

                # loop through the pipeline and remove the limit
                for i in range(len(pipeline)):
                    if "$limit" in pipeline[i]:
                        pipeline.pop(i)
                        break

                # limit to 1k servers
                pipeline.append({"$limit": 1000})

                # edit the message
                await self.messageLib.async_load_server(
                    index=0,
                    pipeline=pipeline,
                    msg=org,
                )

                await msg.delete(context=ctx)
        except AttributeError:
            self.logger.print(f"AttributeError")
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="An error occurred",
                        description="Wrong channel for this bot",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return
            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")
            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to sort the servers",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to update the message
    @component_callback("update")
    async def update_command(self, ctx: ComponentContext):
        await ctx.send(
            embed=self.messageLib.standard_embed(
                title="Updating...",
                description="Updating...",
                color=BLUE,
            ),
            ephemeral=True,
            delete_after=2,
        )
        await self.messageLib.update(ctx)

    # button to show mods
    @component_callback("mods")
    async def mods(self, ctx: ComponentContext):
        try:
            org = ctx.message

            index, pipeline = await self.messageLib.get_pipe(org)

            self.logger.print(f"mods called")

            await ctx.defer(ephemeral=True)

            # get the pipeline
            self.logger.print(f"pipeline: {pipeline}")

            host = self.databaseLib.get_doc_at_index(pipeline, index)

            if "mods" not in host.keys():
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="No mods found",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            mod_list = host["mods"]

            # create a paginator
            pages = []
            for mod in mod_list:
                self.logger.print(mod)
                embed = self.messageLib.standard_embed(
                    title=mod["name"],
                    description=f"Version: {mod['version']}\nModID: {mod['id']}\nRequired: {mod['required']}",
                    color=BLUE,
                )
                pages.append(embed)

            if pages:
                pag = Paginator.create_from_embeds(ctx.bot, *pages, timeout=60)
                await pag.send(ctx)
            else:
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="No mods found",
                        color=RED,
                    ),
                    ephemeral=True,
                )
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="An error occurred",
                        description="Wrong channel for this bot",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to get the players",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to try and join the server
    @component_callback("join")
    async def join(self, ctx: ComponentContext):
        # get the user tag
        user_id = ctx.author.id
        user = await ctx.bot.fetch_user(user_id)

        self.logger.print(f"join called by {[user]}.")

        # 504758496370360330
        if user.id != 504758496370360330:
            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="You are not allowed to use this feature, as it is in alpha testing.",
                    color=RED,
                ),
                ephemeral=True,
            )
            return
        try:
            # step one get the server info
            org = ctx.message
            org_file = org.attachments[0]
            with open("pipeline.ason", "w") as f:
                async with aiohttp.ClientSession() as session, session.get(
                    org_file.url
                ) as resp:
                    pipeline = await resp.text()
                f.write(pipeline)

            index, pipeline = await self.messageLib.get_pipe(org)

            self.logger.print(f"join called")

            await ctx.defer(ephemeral=True)

            # get the pipeline
            self.logger.print(f"pipeline: {pipeline}")

            host = self.databaseLib.get_doc_at_index(pipeline, index)

            # step two is the server online
            host = self.serverLib.update(host=host["ip"], fast=False, port=host["port"])

            if host["lastSeen"] < time.time() - 60:
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="Server is offline",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            # step three it's joining time
            # get the activation code url
            url, vCode = self.mcLib.get_activation_code_url(
                clientID=self.azure_client_id, redirect_uri=self.azure_redirect_uri
            )

            # send the url
            embed = self.messageLib.standard_embed(
                title="Sign in to Microsoft to join",
                description=f"Open [this link]({url}) to sign in to Microsoft and join the server, then click the `Submit` button below and paste the provided code",
                color=BLUE,
            )
            embed.set_footer(text=f"org_id {str(org.id)} vCode {vCode}")
            await ctx.send(
                embed=embed,
                components=[
                    Button(
                        label="Submit",
                        custom_id="submit",
                        style=ButtonStyle.DANGER,
                    )
                ],
                ephemeral=True,
            )
        except Exception as err:
            if "403|Forbidden" in str(err):
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="An error occurred",
                        description="Wrong channel for this bot",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to get the players",
                    color=RED,
                ),
                ephemeral=True,
            )

    # button to try and join the server for realziez
    @component_callback("submit")
    async def submit(self, ctx: ComponentContext):
        try:
            org = ctx.message
            org_org_id = org.embeds[0].footer.text.split(" ")[1]
            vCode = org.embeds[0].footer.text.split(" ")[3]
            org = ctx.channel.get_message(org_org_id)
            self.logger.print(f"org: {org}")

            self.logger.print(f"submit called")
            # get the files attached to the message
            index, pipeline = await self.messageLib.get_pipe(org)

            # create the text input
            text_input = ShortText(
                label="Activation Code",
                placeholder="A.A0_AA0.0.aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
                min_length=40,
                max_length=55,
                custom_id="code",
                required=True,
            )

            # create a modal
            modal = Modal(
                text_input,
                title="Activation Code",
            )

            # send the modal
            await ctx.send_modal(modal)

            # wait for the modal to be submitted
            try:
                # wait for the response
                modal_ctx = await ctx.bot.wait_for_modal(modal=modal, timeout=60)

                # get the response
                code = modal_ctx.responses["code"]
            except asyncio.TimeoutError:
                await ctx.edit_origin(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="Timed out",
                        color=RED,
                    ),
                    components=[],
                )
                return
            else:
                await modal_ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Success",
                        description="Code received",
                        color=GREEN,
                    ),
                    ephemeral=True,
                )

            # try and get the minecraft token
            try:
                # res = await mcLib.get_minecraft_token_async(
                res = self.mcLib.get_minecraft_token(
                    clientID=self.azure_client_id,
                    redirect_uri=self.azure_redirect_uri,
                    act_code=code,
                    verify_code=vCode,
                )

                if res["type"] == "error":
                    self.logger.error(res["error"])
                    await ctx.send(
                        embed=self.messageLib.standard_embed(
                            title="Error",
                            description="An error occurred while trying to get the token",
                            color=RED,
                        ),
                        ephemeral=True,
                    )
                    return
                else:
                    uuid = res["uuid"]
                    name = res["name"]
                    token = res["minecraft_token"]

                # try and delete the original message
                try:
                    await org.delete(context=ctx)
                except Exception:
                    pass

                mod_msg = await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Joining...",
                        description=f"Joining the server with the player:\nName: {name}\nUUID: {uuid}",
                        color=BLUE,
                    ),
                    ephemeral=True,
                )
            except Exception as err:
                self.logger.error(err)
                await ctx.send(
                    embed=self.messageLib.standard_embed(
                        title="Error",
                        description="An error occurred while trying to get the token",
                        color=RED,
                    ),
                    ephemeral=True,
                )
                return

            # try and join the server
            host = self.databaseLib.get_doc_at_index(pipeline, index)
            res = await self.mcLib.join(
                ip=host["ip"],
                port=host["port"],
                player_username=name,
                version=host["version"]["protocol"],
                mine_token=token,
            )

            # try and delete the original message
            try:
                await mod_msg.delete(context=ctx)
            except Exception:
                pass

            # send the res as a json file after removing the favicon if it's there
            if "favicon" in res:
                del res["favicon"]

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Joining...",
                    description=f"Joining the server with the player:\nName: {name}\nUUID: {uuid}",
                    color=BLUE,
                ),
                file=File(json.dumps(res, indent=4), "join.json"),
                ephemeral=True,
            )
        except Exception as err:
            self.logger.error(err)
            self.logger.print(f"Full traceback: {traceback.format_exc()}")

            await ctx.send(
                embed=self.messageLib.standard_embed(
                    title="Error",
                    description="An error occurred while trying to join the server",
                    color=RED,
                ),
                components=[],
            )
