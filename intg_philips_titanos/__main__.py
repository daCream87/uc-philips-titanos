#!/usr/bin/env python3
from __future__ import annotations
import asyncio, logging, os
from typing import Any
import ucapi
from ucapi import media_player, remote
from ucapi.remote import create_send_cmd
from ucapi.ui import Buttons, Size, UiPage, create_btn_mapping, create_ui_icon, create_ui_text
from .client import PhilipsJointSpaceClient
from .commands import KEY_MAP, SUPPORTED_COMMANDS
from .config import ConfigStore, DeviceConfig
from .setup_flow import SetupFlow

_LOG=logging.getLogger("philips_titan")
LOOP=asyncio.new_event_loop(); asyncio.set_event_loop(LOOP)
api=ucapi.IntegrationAPI(LOOP)
store: ConfigStore
clients: dict[str,PhilipsJointSpaceClient]={}
poll_tasks: dict[str,asyncio.Task]={}

async def blocking(fn,*args): return await asyncio.to_thread(fn,*args)

def remote_id(d): return f"remote.{d.id}"
def media_id(d): return f"media_player.{d.id}"

def mappings():
    return [create_btn_mapping(Buttons.POWER,None,None),create_btn_mapping(Buttons.HOME,"HOME"),create_btn_mapping(Buttons.BACK,"BACK"),create_btn_mapping(Buttons.DPAD_UP,"CURSOR_UP"),create_btn_mapping(Buttons.DPAD_DOWN,"CURSOR_DOWN"),create_btn_mapping(Buttons.DPAD_LEFT,"CURSOR_LEFT"),create_btn_mapping(Buttons.DPAD_RIGHT,"CURSOR_RIGHT"),create_btn_mapping(Buttons.DPAD_MIDDLE,"CURSOR_ENTER"),create_btn_mapping(Buttons.VOLUME_UP,"VOLUME_UP"),create_btn_mapping(Buttons.VOLUME_DOWN,"VOLUME_DOWN"),create_btn_mapping(Buttons.MUTE,"MUTE"),create_btn_mapping(Buttons.CHANNEL_UP,"CHANNEL_UP"),create_btn_mapping(Buttons.CHANNEL_DOWN,"CHANNEL_DOWN"),create_btn_mapping(Buttons.GREEN,"NETFLIX"),create_btn_mapping(Buttons.RED,"SOURCE"),create_btn_mapping(Buttons.YELLOW,"GUIDE"),create_btn_mapping(Buttons.BLUE,"SETTINGS")]

def pages():
    p=UiPage("main","TV")
    for label,x,cmd in [("Source",0,"SOURCE"),("Guide",1,"GUIDE"),("Settings",2,"SETTINGS"),("Info",3,"INFO")]: p.add(create_ui_text(label,x,0,cmd=cmd))
    p.add(create_ui_icon("uc:up-arrow-bold",1,2,cmd="CURSOR_UP")); p.add(create_ui_icon("uc:left-arrow",0,3,cmd="CURSOR_LEFT")); p.add(create_ui_text("OK",1,3,cmd="CURSOR_ENTER")); p.add(create_ui_icon("uc:right-arrow",2,3,cmd="CURSOR_RIGHT")); p.add(create_ui_icon("uc:down-arrow-bold",1,4,cmd="CURSOR_DOWN")); p.add(create_ui_text("Back",3,3,cmd="BACK")); p.add(create_ui_text("Home",3,4,cmd="HOME"))
    c=UiPage("control","Bedienung")
    entries=[("Vol +",0,0,"VOLUME_UP"),("Mute",1,0,"MUTE"),("CH +",2,0,"CHANNEL_UP"),("Vol -",0,1,"VOLUME_DOWN"),("TV / Exit",1,1,"TV_EXIT"),("CH -",2,1,"CHANNEL_DOWN"),("Options",0,2,"OPTIONS"),("Subtitle",1,2,"SUBTITLE"),("Ambilight",2,2,"AMBILIGHT"),("Play/Pause",0,3,"PLAY_PAUSE"),("Stop",2,3,"STOP"),("<<",0,4,"REWIND"),(">>",1,4,"FAST_FORWARD")]
    for label,x,y,cmd in entries: c.add(create_ui_text(label,x,y,cmd=cmd))
    a=UiPage("apps","Apps")
    for label,x,y,cmd in [("Netflix",0,0,"NETFLIX"),("Prime Video",2,0,"PRIME_VIDEO"),("Disney+",0,1,"DISNEY_PLUS"),("YouTube",2,1,"YOUTUBE"),("Channels",0,2,"CHANNELS_APP"),("Joyn",2,2,"JOYN")]: a.add(create_ui_text(label,x,y,size=Size(2,1),cmd=cmd))
    n=UiPage("numbers","Ziffern")
    for i,d in enumerate("123456789"): n.add(create_ui_text(d,i%3,i//3,cmd=f"DIGIT_{d}"))
    n.add(create_ui_text("0",1,3,cmd="DIGIT_0")); n.add(create_ui_text("Rot",0,4,cmd="RED")); n.add(create_ui_text("Grün",1,4,cmd="GREEN")); n.add(create_ui_text("Gelb",2,4,cmd="YELLOW")); n.add(create_ui_text("Blau",3,4,cmd="BLUE"))
    return [p,c,a,n]

async def execute(d:DeviceConfig,cmd_id:str,params:dict[str,Any]|None):
    client=clients[d.id]; params=params or {}
    try:
        if cmd_id in (remote.Commands.ON,media_player.Commands.ON):
            if not d.mac: return ucapi.StatusCodes.BAD_REQUEST
            await blocking(client.wake_on_lan,d.mac); return ucapi.StatusCodes.OK
        if cmd_id in (remote.Commands.OFF,media_player.Commands.OFF): await blocking(client.send_key,"Standby"); return ucapi.StatusCodes.OK
        if cmd_id in (media_player.Commands.VOLUME_UP,): await blocking(client.send_key,"VolumeUp"); return ucapi.StatusCodes.OK
        if cmd_id in (media_player.Commands.VOLUME_DOWN,): await blocking(client.send_key,"VolumeDown"); return ucapi.StatusCodes.OK
        if cmd_id in (media_player.Commands.MUTE_TOGGLE,media_player.Commands.MUTE): await blocking(client.send_key,"Mute"); return ucapi.StatusCodes.OK
        if cmd_id==media_player.Commands.VOLUME: await blocking(client.set_volume,int(params.get("volume",0)),False); return ucapi.StatusCodes.OK
        if cmd_id==remote.Commands.SEND_CMD:
            key=KEY_MAP.get(str(params.get("command",""))); 
            if not key: return ucapi.StatusCodes.BAD_REQUEST
            for _ in range(max(1,int(params.get("repeat",1)))): await blocking(client.send_key,key)
            return ucapi.StatusCodes.OK
        if cmd_id==remote.Commands.SEND_CMD_SEQUENCE:
            for command in params.get("sequence",[]):
                key=KEY_MAP.get(str(command));
                if not key: return ucapi.StatusCodes.BAD_REQUEST
                await blocking(client.send_key,key); await asyncio.sleep(max(0,int(params.get("delay",150)))/1000)
            return ucapi.StatusCodes.OK
        mapping={media_player.Commands.HOME:"Home",media_player.Commands.PLAY_PAUSE:"PlayPause",media_player.Commands.STOP:"Stop",media_player.Commands.NEXT:"Next",media_player.Commands.PREVIOUS:"Previous"}
        if cmd_id in mapping: await blocking(client.send_key,mapping[cmd_id]); return ucapi.StatusCodes.OK
    except Exception: _LOG.exception("Command failed"); return ucapi.StatusCodes.SERVER_ERROR
    return ucapi.StatusCodes.NOT_IMPLEMENTED

def configure(d:DeviceConfig):
    client=PhilipsJointSpaceClient(d.host,d.api_version,d.username,d.password,d.verify_tls,secured_transport=d.secured_transport); clients[d.id]=client
    async def rcmd(entity,cmd_id,params,websocket): del entity,websocket; return await execute(d,cmd_id,params)
    r=ucapi.Remote(remote_id(d),{"en":f"{d.name} Remote","de":f"{d.name} Fernbedienung"},[remote.Features.SEND_CMD,remote.Features.ON_OFF],{remote.Attributes.STATE:remote.States.UNKNOWN},simple_commands=SUPPORTED_COMMANDS,button_mapping=mappings(),ui_pages=pages(),cmd_handler=rcmd)
    async def mcmd(entity_id,cmd_id,params=None,websocket=None): del entity_id,websocket; return await execute(d,cmd_id,params)
    m=ucapi.MediaPlayer(media_id(d),d.name,[media_player.Features.ON_OFF,media_player.Features.VOLUME,media_player.Features.VOLUME_UP_DOWN,media_player.Features.MUTE_TOGGLE,media_player.Features.HOME,media_player.Features.PLAY_PAUSE,media_player.Features.STOP],{media_player.Attributes.STATE:media_player.States.UNKNOWN,media_player.Attributes.VOLUME:0,media_player.Attributes.MUTED:False},device_class=media_player.DeviceClasses.TV,cmd_handler=mcmd)
    api.available_entities.add(r); api.available_entities.add(m)
    if d.id not in poll_tasks: poll_tasks[d.id]=asyncio.create_task(poll(d,r,m,client))

async def poll(d,r,m,client):
    while True:
        try:
            s=await blocking(client.read_state); on=s.online and s.power!="STANDBY"
            api.configured_entities.update_attributes(r.id,{remote.Attributes.STATE:remote.States.ON if on else remote.States.OFF})
            ma={media_player.Attributes.STATE:media_player.States.ON if on else media_player.States.OFF}
            if s.volume is not None: ma[media_player.Attributes.VOLUME]=s.volume
            if s.muted is not None: ma[media_player.Attributes.MUTED]=s.muted
            api.configured_entities.update_attributes(m.id,ma)
        except Exception: _LOG.debug("Poll failed for %s",d.host,exc_info=True)
        await asyncio.sleep(d.poll_interval)

def reload_devices():
    for d in store.devices:
        if d.id not in clients: configure(d)

async def main():
    global store
    logging.basicConfig(level=os.getenv("UC_LOG_LEVEL","INFO"),format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    store=ConfigStore(api.config_dir_path,reload_devices)
    setup=SetupFlow(store)
    await api.init("driver.json",setup.handler)
    reload_devices()

if __name__=="__main__": LOOP.run_until_complete(main()); LOOP.run_forever()
