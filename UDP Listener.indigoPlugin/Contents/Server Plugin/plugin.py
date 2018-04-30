#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################

import logging
import socket

kCurDevVersCount = 0        # current version of plugin devices
kAnyDevice      = "ANYDEVICE"
UDP_IP = '' ## All destination IP's

class Plugin(indigo.PluginBase):

    ########################################
    # Main Plugin methods
    ########################################
    def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
        indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)

        pfmt = logging.Formatter('%(asctime)s.%(msecs)03d\t[%(levelname)8s] %(name)20s.%(funcName)-25s%(msg)s', datefmt='%Y-%m-%d %H:%M:%S')
        self.plugin_file_handler.setFormatter(pfmt)

        try:
            self.logLevel = int(self.pluginPrefs[u"logLevel"])
        except:
            self.logLevel = logging.INFO
        self.indigo_log_handler.setLevel(self.logLevel)
        self.logger.debug(u"logLevel = " + str(self.logLevel))


    def startup(self):
        indigo.server.log(u"Starting UDP Listener")
        
        self.triggers = {}
        self.listenerDict = dict()

    def shutdown(self):
        indigo.server.log(u"Shutting down UDP Listener")


    ####################

    def triggerStartProcessing(self, trigger):
        self.logger.debug("Adding Trigger %s (%d) - %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
        assert trigger.id not in self.triggers
        self.triggers[trigger.id] = trigger

    def triggerStopProcessing(self, trigger):
        self.logger.debug("Removing Trigger %s (%d)" % (trigger.name, trigger.id))
        assert trigger.id in self.triggers
        del self.triggers[trigger.id]

    def triggerCheck(self):
        for triggerId, trigger in sorted(self.triggers.iteritems()):
            self.logger.debug("Checking Trigger %s (%s), Type: %s" % (trigger.name, trigger.id, trigger.pluginTypeId))
            if trigger.pluginTypeId == 'requestReceived':
                indigo.trigger.execute(trigger)


    ####################
    def validatePrefsConfigUi(self, valuesDict):
        self.logger.debug(u"validatePrefsConfigUi called")
        errorDict = indigo.Dict()

        if len(errorDict) > 0:
            return (False, valuesDict, errorDict)
        return (True, valuesDict)

    ########################################
    def closedPrefsConfigUi(self, valuesDict, userCancelled):
        if not userCancelled:
            try:
                self.logLevel = int(valuesDict[u"logLevel"])
            except:
                self.logLevel = logging.INFO
            self.indigo_log_handler.setLevel(self.logLevel)
            self.logger.debug(u"logLevel = " + str(self.logLevel))

    ########################################

    def runConcurrentThread(self):

        try:
            while True:
            
                if len(self.listenerDict) == 0: # if no listener devices, just sleep a bit
                    self.sleep(1)
                
                else:
                    for devID, sock in self.listenerDict.items():
                        device = indigo.devices[devID]
                        try:
                            data, addr = sock.recvfrom(1024)
                        except socket.timeout, e:
                            self.logger.threaddebug(u"{}: UDP timeout".format(device.name))
                        except socket.error, e:
                            self.logger.error(u"{}: Socket Error: {}".format(device.name, e))
                        else:
                            self.logger.debug(u"{}: UDP msg from: {}, data: {}".format(device.name, addr, data))
                            stateList = [
                                        {'key':'lastIP',        'value':addr[0]},
                                        {'key':'lastPort',      'value':addr[1]},
                                        {'key':'lastMessage',   'value':data}
                            ]
                            device.updateStatesOnServer(stateList)
    

        except self.StopThread:
            pass

    ########################################
    # Called for each enabled Device belonging to plugin
    #
    def deviceStartComm(self, device):
        self.logger.debug(u'Called deviceStartComm(self, device): %s (%s)' % (device.name, device.id))

        instanceVers = int(device.pluginProps.get('devVersCount', 0))
        self.logger.debug(device.name + u": Device Current Version = " + str(instanceVers))

        if instanceVers >= kCurDevVersCount:
            self.logger.debug(device.name + u": Device Version is up to date")

        elif instanceVers < kCurDevVersCount:
            newProps = device.pluginProps

        else:
            self.logger.warning(u"Unknown device version: " + str(instanceVers) + " for device " + device.name)

        if device.id not in self.listenerDict:
            self.logger.debug(u"{}: Starting device ({})".format(device.name, device.deviceTypeId))

            if device.deviceTypeId == "udpListener":

                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((UDP_IP, int(device.pluginProps['udpPort'])))
                s.settimeout(0.1)

                self.listenerDict[device.id] = s
                
            else:
                self.logger.error(u"{}: Unknown device type: {}".format(device.name, device.deviceTypeId))
        else:
            self.logger.debug(device.name + u": Duplicate Device ID")


    ########################################
    # Terminate communication with servers
    #
    def deviceStopComm(self, device):

        if device.id in self.listenerDict:
            self.logger.debug(u"{}: Stopping device".format(device.name))
            self.listenerDict[device.id].close()
            del self.listenerDict[device.id]
        else:
            self.logger.debug(u"{}: Unknown Device ID: {}".format(device.name, device.id))
        

    ########################################
    def validateDeviceConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    ########################################
    def validateActionConfigUi(self, valuesDict, typeId, devId):
        errorsDict = indigo.Dict()
        try:
            pass
        except:
            pass
        if len(errorsDict) > 0:
            return (False, valuesDict, errorsDict)
        return (True, valuesDict)

    ########################################
    # Menu Methods
    ########################################
    
    def pickUDPDevice(self, filter=None, valuesDict=None, typeId=0, targetId=0):
        retList =[(kAnyDevice, "Any")]
        for dev in indigo.devices.iter("self"):
            if (dev.deviceTypeId == "udpDevice"):
                retList.append((dev.id,dev.name))
        retList.sort(key=lambda tup: tup[1])
        return retList



