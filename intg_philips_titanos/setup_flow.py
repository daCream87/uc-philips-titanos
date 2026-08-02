from __future__ import annotations
import asyncio, inspect, re
from enum import IntEnum
from typing import Any
from haphilipsjs import PhilipsTV
from ucapi import AbortDriverSetup, DriverSetupRequest, RequestUserInput, SetupComplete, SetupError, UserDataResponse
from .config import ConfigStore, DeviceConfig

class Step(IntEnum): START=0; PIN=1

async def maybe_await(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value

class SetupFlow:
    def __init__(self, store: ConfigStore):
        self.store=store; self.step=Step.START; self.tv=None; self.pair_state=None; self.pending={}

    async def handler(self, msg: Any) -> Any:
        if isinstance(msg, AbortDriverSetup):
            self.__init__(self.store); return SetupError()
        if isinstance(msg, DriverSetupRequest):
            self.step=Step.START
            await asyncio.sleep(0.5)
            return RequestUserInput({"en":"Philips TV setup","de":"Philips-TV einrichten"},[
                {"id":"info","label":{"en":"Direct IP pairing","de":"Direkte IP-Kopplung"},"field":{"label":{"value":{"en":"Enter the TV IP address. The TV must be on and in the same network.","de":"IP-Adresse des eingeschalteten Fernsehers eingeben. TV und Remote müssen im gleichen Netzwerk sein."}}}},
                {"id":"host","label":{"en":"TV IP address","de":"TV-IP-Adresse"},"field":{"text":{"value":""}}},
                {"id":"mac","label":{"en":"MAC address (Wake-on-LAN)","de":"MAC-Adresse (Wake-on-LAN)"},"field":{"text":{"value":""}}},
                {"id":"name","label":{"en":"Name","de":"Name"},"field":{"text":{"value":"Philips TV"}}}
            ])
        if not isinstance(msg, UserDataResponse): return SetupError()
        if self.step==Step.START:
            host=str(msg.input_values.get("host","")).strip(); mac=str(msg.input_values.get("mac","")).strip(); name=str(msg.input_values.get("name","Philips TV")).strip() or "Philips TV"
            if not host: return SetupError()
            self.pending={"host":host,"mac":mac,"name":name}
            try:
                tv=PhilipsTV(host,6)
                await maybe_await(tv.getSystem())
                await maybe_await(tv.setTransport(secured_transport=True if getattr(tv,"secured_transport",None) is None else getattr(tv,"secured_transport")))
                try:
                    state=await maybe_await(tv.pairRequest("unfolded_circle","Unfolded Circle Remote 3","remote3","Linux","native"))
                except Exception:
                    await maybe_await(tv.setTransport(secured_transport=True))
                    state=await maybe_await(tv.pairRequest("unfolded_circle","Unfolded Circle Remote 3","remote3","Linux","native"))
                self.tv=tv; self.pair_state=state; self.step=Step.PIN
                return RequestUserInput({"en":"Enter TV PIN","de":"TV-PIN eingeben"},[
                    {"id":"pin","label":{"en":"PIN shown on TV","de":"PIN vom Fernseher"},"field":{"text":{"value":""}}}
                ])
            except Exception:
                return SetupError()
        if self.step==Step.PIN:
            pin=str(msg.input_values.get("pin","")).strip()
            if not re.fullmatch(r"\d{4,8}",pin) or self.tv is None: return SetupError()
            try:
                result=await maybe_await(self.tv.pairGrant(self.pair_state,pin))
                username,password=str(result[0]),str(result[1])
                host=self.pending["host"]
                device=DeviceConfig(id=f"philips-{host.replace('.','-')}", name=self.pending["name"], host=host, mac=self.pending["mac"], api_version=6, username=username, password=password, secured_transport=getattr(self.tv,"protocol","https")=="https")
                self.store.upsert(device)
                return SetupComplete()
            except Exception:
                return SetupError()
        return SetupError()
