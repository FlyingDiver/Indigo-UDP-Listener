#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import logging
import socket
import struct

kCurDevVersCount = 0        # current version of plugin devices
kAnyDevice      = "ANYDEVICE"
UDP_IP = ''  # All destination IP's

class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin methods
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        self.logLevel = int(self.pluginPrefs.get("logLevel", logging.INFO))
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(f"logLevel = {self.logLevel}")

        self.triggers = {}
        self.listeners = {}

    @staticmethod
    def startup():
        indigo.server.log("Starting UDP Listener")

    @staticmethod
    def shutdown():
        indigo.server.log("Shutting down UDP Listener")

    ####################

    def triggerStartProcessing(self, trigger):
        self.logger.debug(f"Adding Trigger {trigger.name} ({trigger.id}) - {trigger.pluginTypeId}")
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug(f"Removing Trigger {trigger.name} ({trigger.id})")
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self, device):
        for triggerId, trigger in sorted(self.triggers.items()):
            self.logger.debug(f"Checking Trigger {trigger.name} ({trigger.id}), Type: {trigger.pluginTypeId}")

            if trigger.pluginTypeId == 'messageReceived':
                if (trigger.pluginProps["udpDevice"] == str(device.id)) or (trigger.pluginProps["udpDevice"] == kAnyDevice):
                    indigo.trigger.execute(trigger)
                else:
                    self.logger.debug(f"\t\tSkipping Trigger {trigger.name} ({trigger.id}), wrong device: {device.id}")
            else:
                self.logger.debug(f"\tUnknown Trigger Type {trigger.name} ({trigger.id:d}), {trigger.pluginTypeId}")

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            self.logLevel = int(valuesDict.get("logLevel", logging.INFO))
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(f"logLevel = {self.logLevel}")

    ########################################

    def runConcurrentThread(self):

        try:
            while True:
            
                if len(self.listeners) == 0:  # if no listener devices, just sleep a bit
                    self.sleep(1)
                
                else:
                    for devID in list(self.listeners):
                        device = indigo.devices[devID]
                        sock = self.listeners[device.id]
                        try:
                            data, addr = sock.recvfrom(2048)
                        except socket.timeout as e:
                            continue
                        except socket.error as e:
                            self.logger.error(f"{device.name}: Socket Error: {e}")
                        else:
                            try:
                                message = data.decode('utf-8')
                            except (Exception, ):
                                message = ":".join(f"{ord(c):02x}" for c in data)
                            self.logger.debug(f"{device.name}: UDP msg from: {addr}, data: {message}")
                            
                            stateList = [
                                        {'key':'lastIP',        'value':addr[0]},
                                        {'key':'lastPort',      'value':addr[1]},
                                        {'key':'lastMessage',   'value':message}
                            ]
                            device.updateStatesOnServer(stateList)
                            self.triggerCheck(device)
                    self.sleep(0.01)

        except self.StopThread:
            pass

    ########################################
    # Called for each enabled Device belonging to plugin
    #
    def deviceStartComm(self, device):
        instanceVers = int(device.pluginProps.get('devVersCount', 0))
        self.logger.threaddebug(f"{device.name }: Device Current Version = {instanceVers}")

        if instanceVers >= kCurDevVersCount:
            self.logger.threaddebug(f'{device.name}: Device Version is up to date')

        elif instanceVers < kCurDevVersCount:
            newProps = device.pluginProps

        else:
            self.logger.warning(f"{device.name}: Unknown device version: ")

        if device.id not in self.listeners:
            self.logger.debug(f"{device.name}: Starting {device.deviceTypeId} device ({device.id})")

            if device.deviceTypeId == "udpListener":

                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                s.settimeout(0.1)
                s.bind((UDP_IP, int(device.pluginProps['udpPort'])))

                if len(device.pluginProps['multiGroup']) > 0:                       # multicast group specified
                    group = socket.inet_aton(device.pluginProps['multiGroup'])
                    mreq = struct.pack('4sL', group, socket.INADDR_ANY)
                    s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                
                self.listeners[device.id] = s
                
            else:
                self.logger.error(f"{device.name}: Unknown device type: {device.deviceTypeId}")
        else:
            self.logger.debug(f"{device.name}: Duplicate Device ID ({device.id})")

    ########################################
    # Terminate communication
    #
    def deviceStopComm(self, device):
        if device.id in self.listeners:
            self.logger.debug(f"{device.name}: Stopping {device.deviceTypeId} device ({device.id})")
            self.listeners[device.id].close()
            del self.listeners[device.id]
        else:
            self.logger.debug(f"{device.name}: Unknown Device ID: {device.id}")

    ########################################
    # Menu Methods
    ########################################
    
    def pickUDPDevice(self, filter=None, valuesDict=None, typeId=0, targetId=0):
        retList = [(kAnyDevice, "Any")]
        for dev in indigo.devices.iter("self"):
            if dev.deviceTypeId == "udpListener":
                retList.append((dev.id,dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList
