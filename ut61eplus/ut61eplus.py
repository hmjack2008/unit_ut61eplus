# -*- coding: utf-8 -*-

#
#
# Use UT-D09A cable to communicate with UT61E+ in Windows
#
# source from :
#  https://github.com/ljakob/unit_ut61eplus
#  https://github.com/Aleks-nik-a/unit_ut61eplus
#
#
# reference :
#  https://github.com/LordRafa/UT61E-_Communication_Protocol
#
#
# pywinusb
#  https://blog.csdn.net/lilijianqun/article/details/80547514
#  https://github.com/rene-aguirre/pywinusb
#  https://github.com/raknahs2/Python_USB_HID/blob/master/hid_write_raw.py
#
#
# USB debug tools（python2.7 + Tkinter + pyusb/pywinusb）
#  https://www.cnblogs.com/jakeyChen/p/4463530.html
#  https://gitee.com/jakey.chen/USB-HID-TEST
#
#
# CH9329 Chipset
#  https://www.wch.cn/products/CH9329.html
#  https://www.wch.cn/bbs/thread-92138-1.html
#
#
# UNI-TREND TECHNOLOGY (CHINA) CO., LTD.
#  https://meters.uni-trend.com/product/ut-d-series-2/#Features
#  https://meters.uni-trend.com/product/ut61plus-series/#Docs
#
#

import time
import decimal
import binascii
import logging

##import hid # https://github.com/trezor/cython-hidapi https://trezor.github.io/cython-hidapi/api.html
import pywinusb.hid as hid


log = logging.getLogger(__name__)

"""
protocol of UT61+

parts from an USB trace, parts from experimenting myself, parts from https://github.com/gulux/Uni-T-CP2110
and many 'inspirations' form the decompiled bluetooth app

example response in mV AC

ab . => header
cd . => header
10   => number of bytes that follow including 'checksum'
01   => mode
30 0 => range (character starting at '0')
20   => digit MSB (can be ' ' or '-') ! number can also be ' OL.  '
20   => digit
35 5 => digit
33 3 => digit
2e . => digit
35 5 => digit
34 4 => digit LSB
01   => progress1
00   => progress2 => progress = progress1*10 + progress2 - meaning is not clear yet
30 0 => Bitmask: Max,Min,Hold,Rel
34 4 => Bitmask: !Auto,Battery,HvWarning
30 0 => Bitmask: !DC,PeakMax,PeakMin,BarPol
03   => sum over all - MSB - sum from 0xab to 0x30
8d . => sum over all - LSB

"""


class Measurement:

    # decoded modes
    _MODE = ['ACV', 'ACmV', 'DCV', 'DCmV', 'Hz', '%', 'OHM', 'CONT', 'DIDOE', 'CAP', '°C', '°F', 'DCuA', 'ACuA', 'DCmA', 'ACmA',
             'DCA', 'ACA', 'HFE', 'Live', 'NCV', 'LozV', 'ACA', 'DCA', 'LPF', 'AC/DC', 'LPF', 'AC+DC', 'LPF', 'AC+DC2', 'INRUSH']

    # units based on mode and range
    _UNITS = {'%': {'0': '%'},
              'AC+DC': {'1': 'A'},
              'AC+DC2': {'1': 'A'},
              'AC/DC': {'0': 'V', '1': 'V', '2': 'V', '3': 'V'},
              'ACA': {'1': 'A'},
              'ACV': {'0': 'V', '1': 'V', '2': 'V', '3': 'V'},
              'ACmA': {'0': 'mA', '1': 'mA'},
              'ACmV': {'0': 'mV'},
              'ACuA': {'0': 'uA', '1': 'uA'},
              'CAP': {'0': 'nF',
                      '1': 'nF',
                      '2': 'uF',
                      '3': 'uF',
                      '4': 'uF',
                      '5': 'mF',
                      '6': 'mF',
                      '7': 'mF'},
              'CONT': {'0': 'Ω'},
              'DCA': {'1': 'A'},
              'DCV': {'0': 'V', '1': 'V', '2': 'V', '3': 'V'},
              'DCmA': {'0': 'mA', '1': 'mA'},
              'DCmV': {'0': 'mV'},
              'DCuA': {'0': 'uA', '1': 'uA'},
              'DIDOE': {'0': 'V'},
              'Hz': {'0': 'Hz',
                     '1': 'Hz',
                     '2': 'kHz',
                     '3': 'kHz',
                     '4': 'kHz',
                     '5': 'MHz',
                     '6': 'MHz',
                     '7': 'MHz'},
              'LPF': {'0': 'V', '1': 'V', '2': 'V', '3': 'V'},
              'LozV': {'0': 'V', '1': 'V', '2': 'V', '3': 'V'},
              'OHM': {'0': 'Ω',
                      '1': 'kΩ',
                      '2': 'kΩ',
                      '3': 'kΩ',
                      '4': 'MΩ',
                      '5': 'MΩ',
                      '6': 'MΩ'},
              '°C': {'0': '°C', '1': '°C'},
              '°F': {'0': '°F', '1': '°F'},
              'HFE': {'0': 'B'},
              'NCV': {'0': 'NCV'}}

    # strings that could mean overload - taken from android app
    _OVERLOAD = set(['.OL', 'O.L', 'OL.', 'OL', '-.OL', '-O.L', '-OL.', '-OL'])
    
    # strings that Indicate level of voltage detected >=50Vrms (50-60Hz)
    _NCV = set(['EF','-','--','---','----','-----'])
    
    # unit exponents
    _EXPONENTS = {
        'M':  6, # mega
        'k':  3, # kilo
        'm': -3, # milli
        'u': -6, # mirco
        'n': -9,  # nano
    }

    @property
    def binary(self)->bytes:
        """ original binary data from DMM """
        return self._data['binary']

    @property
    def mode(self)->str:
        """ mode """
        return self._data['mode']

    @property
    def range(self)->str:
        """ range - internal to device """
        return self._data['range']

    @property
    def display(self)->str:
        """displayed number as string """
        return self._data['display']

    @property
    def overload(self)->bool:
        """ device is in overload condition - like measuring resistance on open leads """
        return self._data['overload']

    @property
    def display_decimal(self)->decimal:
        """ displayed number as decimal - may be decimal.Overflow() in overload condition """
        return self._data['display_decimal']

    @property
    def display_unit(self)->str:
        """ displayed unit including exponent - e.g. mV """
        return self._data['display_unit']

    @property
    def unit(self)->str:
        """ physical unit of the measurement - e.g. V """
        return self._data['display_unit']

    @property
    def value(self)->decimal:
        """ decimal representation - e.g. 200mV => 0.2V """
        return self._data['decimal']
    
    @property
    def progress(self)->int:
        """ some progress indicator - unknown meaning """
        return self._data['progres']

    @property
    def isMax(self)->bool:
        """ value is max value """
        return self._data['max']

    @property
    def isMin(self)->bool:
        """ value is min value """
        return self._data['min']

    @property
    def isHold(self)->bool:
        """ DMM is in hold mode """
        return self._data['hold']

    @property
    def isRel(self)->bool:
        """ DMM is in REL mode """
        return self._data['rel']

    @property
    def isAuto(self)->bool:
        """ auto ranging active """
        return self._data['auto']

    @property
    def hasBatteryWarning(self)->bool:
        """ battery warning """
        return self._data['battery']

    @property
    def hasHVWarning(self)->bool:
        """ high voltage warning - > 30 V """
        return self._data['hvwarning']

    @property
    def isDC(self)->bool:
        """ displayed value is DC """
        return self._data['dc']

    @property
    def isMaxPeak(self)->bool:
        """ value is max peak """
        return self._data['peak_max']

    @property
    def isMinPeak(self)->bool:
        """ value is min peak """
        return self._data['peak_min']

    @property
    def isBarPol(self)->bool:
        """ unknown """
        return self._data['bar_pol']  # meaning not clear


    def __init__(self, b: bytes):
        self._data = {}
        self._data['binary'] = b
        self._data['mode'] = self._MODE[b[0]]
        self._data['range'] = b[1:2].decode('ASCII')
        self._data['display'] = b[2:9].decode('ASCII').replace(' ', '')
        self._data['overload'] = self._data['display'] in self._OVERLOAD
        self._data['ncv'] = self._data['display'] in self._NCV
        if self._data['overload']:
            self._data['display_decimal'] = decimal.Overflow()
        elif self._data['ncv']:
            switch={
                'EF': 0,
                '-': 1,
                '--': 2,
                '---': 3,
                '----': 4,
                '-----': 5
            }
            self._data['display_decimal'] = switch.get(self._data['display'],-1)
        else:
            self._data['display_decimal'] = decimal.Decimal(self.display)
            
        self._data['display_unit'] = self._UNITS[ self._data['mode'] ].get(self._data['range'])
        
        self._data['unit'] = self._data['display_unit']

        self._data['decimal'] = self.display_decimal
        if self._data['unit'][0] in self._EXPONENTS and not self._data['overload']:
            self._data['decimal'] = self._data['decimal'].rotate(self._EXPONENTS[self.unit[0]])
            self._data['unit'] = self._data['unit'][1:] # remove first char

        self._data['progres'] = b[9] * 10 + b[10]
        self._data['max'] = b[11] & 8 > 0
        self._data['min'] = b[11] & 4 > 0
        self._data['hold'] = b[11] & 2 > 0
        self._data['rel'] = b[11] & 1 > 0
        self._data['auto'] = b[12] & 4 == 0
        self._data['battery'] = b[12] & 2 > 0
        self._data['hvwarning'] = b[12] & 1 > 0
        self._data['dc'] = b[13] & 8 > 0
        self._data['peak_max'] = b[13] & 4 > 0
        self._data['peak_min'] = b[13] & 2 > 0
        self._data['bar_pol'] = b[13] & 1 > 0  # meaning not clear

    def __str__(self):
        res = '\n'
        res += 'binary={}\n'.format(self.binary.hex(' '))  # :byte
        res += f'mode={self.mode}\n'  # :str
        res += f'range={self.range}\n'  # :str
        res += f'display={self.display}\n'  # :str
        res += f'display_decimal={self.display_decimal}\n'  # :decimal|str
        res += f'display_unit={self.display_unit}\n'  # :str
        res += f'overload={self.overload}\n'  # :bool
        res += f'value={self.value}\n'  # :decimal|str
        res += f'unit={self.unit}\n'  # :str
        res += f'progress={self.progress}\n'  # :int
        res += f'isMax={self.isMax}\n'  # :bool
        res += f'ismin={self.isMin}\n'  # :bool
        res += f'isHold={self.isHold}\n'  # :bool
        res += f'isRel={self.isRel}\n'  # :bool
        res += f'isAuto={self.isAuto}\n'  # :bool
        res += f'hasBatteryWarning={self.hasBatteryWarning}\n'  # :bool
        res += f'hashasHVWarning={self.hasHVWarning}\n'  # :bool
        res += f'isDC={self.isDC}\n'  # :bool
        res += f'isMaxPeak={self.isMaxPeak}\n'  # :bool
        res += f'isMinPeak={self.isMinPeak}\n'  # :bool
        res += f'isBarPol={self.isBarPol}\n'  # :bool, meaning not clear
        return res

        # pylint: disable=unreachable
        for b in self.binary:
            l = '{:02x} {}\n'.format(b, chr(b))
            res += l
        return res


class UT61EPLUS:

    _VID = 0x1A86  # WWW.WCH.CN
    _PID = 0xE429  # HID Device

    _SEQUENCE_GET_NAME = bytes.fromhex('AB CD 03 5F 01 DA')  # There are 2 responses, 1st:confirm, 2nd:'UT61E+'
    _SEQUENCE_GET_SERIAL = bytes.fromhex('AB CD 03 5D 01 D8')  # unknown command, ref from: https://github.com/Aleks-nik-a/unit_ut61eplus	
    _SEQUENCE_SEND_DATA = bytes.fromhex('AB CD 03 5E 01 D9')
    _SEQUENCE_SEND_CMD = bytes.fromhex('AB CD 03')
    '''
    ref from: https://github.com/LordRafa/UT61E-_Communication_Protocol/blob/main/Reverse%20Engienering%20UT61E%2B%20Notes
    CMD List:
    Read Info    -> ab cd 03 5e 01 d9
    Butons: (There is 1 response, confirm: AB CD 04 FF 00 02)
    Max/Min      -> ab cd 03 41 01 bc
    Max/Min Off  -> ab cd 03 42 01 bd
    Manual(Range)-> ab cd 03 46 01 c1
    Auto         -> ab cd 03 47 01 c2
    REL          -> ab cd 03 48 01 c3
    Hz %         -> ab cd 03 49 01 c4
    Hold         -> ab cd 03 4a 01 c5
    Light On/Off -> ab cd 03 4b 01 c6
    Select       -> ab cd 03 4c 01 c7
    Peak Max/Min -> ab cd 03 4d 01 c8
    Peak Off     -> ab cd 03 4e 01 c9
    '''
    _COMMANDS = {
        'min_max': 65,
        'not_min_max': 66,
        'range': 70, 
        'auto': 71,
        'rel': 72, 
        'select2': 73, # Hz/USB
        'hold': 74,
        'lamp': 75,
        'select1': 76, # orange
        'p_min_max': 77,
        'not_peak': 78,
    }

    _hDevice = None
    _hReport = None
    _REC_X64 = [0x00]*64


    def __init__(self, vid: int=_VID, pid: int=_PID, device_id=0):

        self._VID = vid
        self._PID = pid
        log.info("[1-1] Device initial, vid:%04X pid:%04X", self._VID, self._PID)

        '''
        initial for UT-D09A cable (CH9329)
        '''
        filter = hid.HidDeviceFilter(vendor_id = self._VID, product_id = self._PID)
        hid_devices = filter.get_devices()
        if hid_devices:
            log.info("[1-2] HID devices found: {0} \n {1}".format(len(hid_devices), hid_devices))
            if len(hid_devices) > device_id:
                self._hDevice = hid_devices[device_id]  # found and set the correct id
            else:
                log.error("[1-3] The device_id parameter({0}) must be less than the number of devices found({1})".format(device_id, len(hid_devices)))
                log.warning("[1-3-1] The device_id parameter({0}) temporarily set to(0)".format(device_id))
                device_id = 0  # set device_id to first device 0
                self._hDevice = hid_devices[device_id]  # temporarily set replacement id
            log.debug("[1-2-1] HID device_id: {}".format(device_id)) 
            log.debug("[1-2-2] vendor_id: {:02X}".format(self._hDevice.vendor_id))
            log.debug("[1-2-3] product_id: {:02X}".format(self._hDevice.product_id))
            log.debug("[1-2-4] vendor_name: {}".format(self._hDevice.vendor_name))
            log.debug("[1-2-5] product_name: {}".format(self._hDevice.product_name))
            log.debug("[1-2-6] version_number: {}".format(self._hDevice.version_number))
            log.debug("[1-2-7] serial_number: {}".format(self._hDevice.serial_number))
            log.debug("[1-2-8] device_path: {}".format(self._hDevice.device_path))
            self.open(report_id=0)  # The report_id of CH9329 is fixed to 0
        else:
            log.critical("[1-4] Can not setup, HID device not found, vid:%04X pid:%04X", self._VID, self._PID)
            self.list_all_device()

    def __del__(self):
        log.debug("[10-1] UT61EPLUS class destruct")
        if self._hDevice:
            self.close()

    def list_all_device(self):
        all_hids = hid.find_all_hid_devices()
        log.info("[9-1] Find all hid devices")
        ##log.debug(all_hids)
        i = 0
        if all_hids:
            for hid_info in all_hids:
                log.info("[9-1-{0}] Hid info: \n {1}".format(i, hid_info))
                i += 1
        else:
            log.critical("[9-2] No HID devices found")

    def open(self, report_id=0):
        def _cb_receive(data):  # Callback function when Receive from HID
            log.info("[2-2-1] HID response, receive report from HID")
            log.debug("[2-2-2] receive report data: {0} \n {1}".format(len(data), data))
            '''
            i = 0
            for bi in data:
                print("%02X" % bi, end="\t")
                if i % 16 == 0:
                    print("")
                i += 1
            '''
            self._REC_X64 = [0x02]*64
            self._REC_X64 = data[1:]  # skip report_id , data[0]
            log.debug("[2-2-3] store report data to _REC_X64: {0} \n {1}".format(len(self._REC_X64), self._REC_X64))


        log.info("[2-1] HID device open")
        self._hDevice.open()

        log.debug("[2-2] Callback function setting for Receive from HID")
        self._hDevice.set_raw_data_handler(_cb_receive)  # set Callback function

        hReports = self._hDevice.find_output_reports()
        if hReports:
            log.debug("[2-3] HID reports found: {0} \n {1}".format(len(hReports), hReports))
            if len(hReports) > report_id:
                self._hReport = hReports[report_id]
            else:
                log.error("[2-4] The report_id parameter({0}) must be less than the number of reports found({1})".format(report_id, len(hReports)))
        else:
            log.critical("[2-5] Can not setup, No HID report interface found")

    def close(self):
        if self._hDevice:
            log.info("[4-1] HID device close")
            self._hDevice.close()
            self._hDevice = None
        else:
            log.critical("[4-2] Can not close, No HID devices found")

    def _read(self):
        log.info("[6-1] HID report data getting")
        log.debug("[6-1-1] read from _REC_X64: {0} \n {1}".format(len(self._REC_X64), list("{:02X}".format(bi) for bi in self._REC_X64)))
        return self._REC_X64

    def _write(self, b: bytes):
        buf = [0x20]*65
        log.info("[3-1] HID report writing and sending")
        log.debug("[3-2] Initialize (clear) data buffer: {0} \n {1}".format(len(buf), list("{:02X}".format(bi) for bi in buf)))
        log.debug("[3-2-1] write data to buffer: {0} \n {1}".format(len(b), list("{:02X}".format(bi) for bi in b)))
        '''
        i = 0
        for bi in b:
            print("%02X" % bi, end="\t")
            if i % 16 == 0:
                print("")
            i += 1
        '''
        buf[0] = 0  # 1st byte is report_id, The report_id of CH9329 is fixed to 0
        len_b = len(b)
        buf[1] = len_b  # 2nd byte is data length
        buf[2:(len_b+2)] = b[:]  # Copy the data to follow
        log.debug("[3-2-2] send data buffer: {0} \n {1}".format(len(buf), list("{:02X}".format(bi) for bi in buf)))
        if self._hReport:
            self._hReport.set_raw_data(buf)
            self._hReport.send()
            time.sleep(0.2)  # wait callback function response, confirm and DMM_Name
            log.debug("[3-3] HID report writing completed")
        else:
            log.critical("[3-4] Can not write and send, No HID report interface found")

    def _readResponse(self) -> bytes:
        # pylint: disable=unsupported-assignment-operation,unsubscriptable-object
        state = 0  # 0=init 1=0xAB received 2=0xCD received 3=we have length
        buf: bytes = None
        index: int = None
        sum: int = 0

        log.info("[5-1] Extract data from receive report")
        while True:
            log.debug("[5-2] HID report reading")
            x = self._read()
            log.debug("[5-3] HID report reading completed")
            b: int
            for b in x[1:]:  # skip first byte - length from HID
                if state < 3 or index + 2 < len(buf):  # sum all bytes except last 2
                    sum += b
                    log.debug('[5-3-1] sum all bytes except last 2, b:{0:02X}, checksum:{1:04X}'.format(b, sum))
                if state == 0 and b == 0xAB:
                    state = 1
                    log.debug('[5-3-2] state 0 -> 1')
                elif state == 1 and b == 0xCD:
                    state = 2
                    log.debug('[5-3-2] state 1 -> 2')
                elif state == 2:
                    buf = bytearray(b)  # length of data , if (b + 2) != x[0]: log.error('length error')
                    if b < 3 or b > 60:
                        log.error('[5-3-4] data length less than 3')
                        return None
                    index = 0
                    state = 3
                    log.debug('[5-3-5] state 2 -> 3')
                elif state == 3:
                    buf[index] = b  # data
                    index += 1
                    if index >= len(buf):
                        recevied_sum = (buf[-2] << 8) + buf[-1]
                        log.debug('[5-3-6] calculated sum=%04X expected sum=%04X', sum, recevied_sum)
                        if sum != recevied_sum:
                            log.warning('[5-3-7] checksum mismatch')
                            return None
                        return buf[:-2]  # drop last 2 bytes at end with checksum
                else:
                    log.error('[5-4] Unexpected byte (0x%02X) in state (%i)', b, state)
                    return None

    def getName(self):
        # pylint: disable=unused-variable
        """get name of multimeter"""
        log.info('[7-1] Get name of DMM (Digital Multimeter)')
        self._write(self._SEQUENCE_GET_NAME)
        confirm = self._readResponse()  # 1st response, confirm : 07 AB CD 04 FF 00 02 7B
        log.debug('[7-2] DMM response, confirm: {}'.format(confirm))
        time.sleep(0.2)  # wait 2nd response from DMM
        name = self._readResponse()  # 2nd response, name : 0B AB CD 08 55 54 36 31 45 2B 03 00
        log.debug('[7-3] DMM response, name: {}'.format(name))
        if isinstance(name, bytearray):
            return name.decode('ASCII')  # name: "UT61E+" (55 54 36 31 45 2B)
        else:
            log.error('[7-4] DMM no response, name type error !')
            return None

    def takeMeasurement(self):
        """read measurement from screen"""
        self._write(self._SEQUENCE_SEND_DATA)
        b = self._readResponse()
        if b is None:
            return None
        return Measurement(b)

    def sendCommand(self, cmd)->None:
        """send command to device"""
        log.info('[8-1] Send Command: {}'.format(cmd))
        if cmd in self._COMMANDS:
            cmd = self._COMMANDS[cmd]
        if not type(cmd) is int:
            raise Exception(f'bad argument {cmd}')
        log.debug('[8-1-1] Command code: {:02X}'.format(cmd))
        ##seq = self._SEQUENCE_SEND_CMD
        cmd_bytes = bytearray(3)
        cmd_bytes[0] = cmd & 0xff
        cmd = cmd + 379 # don't ask it's from the java source
        cmd_bytes[1] = cmd >> 8
        cmd_bytes[2] = cmd & 0xff
        seq = self._SEQUENCE_SEND_CMD + cmd_bytes
        '''
        for bi in seq:
            log.debug(bi)
        '''
        log.debug('[8-1-2] Command data: {}'.format(list("{:02X}".format(bi) for bi in seq)))
        ##log.debug(seq)
        self._write(seq)
        # pylint: disable=unused-variable
        confirm = self._readResponse()  # response, confirm : 07 AB CD 04 FF 00 02 7B
        log.debug('[8-2] DMM response, confirm: {}'.format(confirm))
        time.sleep(0.2)  # wait other response from DMM
        log.debug('[8-3] Send Command completed')

    def _test(self):
        self._write(self._SEQUENCE_GET_NAME)

        while True:
            x = self._hDevice.read()
            for i in range(1, len(x)):  # skip first byte - length
                hex: str = binascii.hexlify(x[i:i+1]).decode('ASCII')
                c: str = x[i:i+1].decode(encoding='ASCII', errors='ignore')
                if c.isprintable and len(c) == 1:
                    pass
                else:
                    c = '.'
                print(f'{hex} {c}')

