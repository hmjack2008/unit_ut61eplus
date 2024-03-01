# -*- coding: utf-8 -*-

#
#  https://github.com/raknahs2/Python_USB_HID/blob/master/hid_write_raw.py
#
#
# pywinusb使用 
#  https://blog.csdn.net/lilijianqun/article/details/80547514
#
# USB 调试工具（python2.7 + Tkinter + pyusb/pywinusb）
#  https://www.cnblogs.com/jakeyChen/p/4463530.html
#  https://gitee.com/jakey.chen/USB-HID-TEST
#
#

import time
import pywinusb.hid as hid


def sample_handler(data):
    print("---sample_handler---")
    print("Raw data: {0}".format(data))
    i = 0
    for bt in data:
        print("%02X" % bt, end="\t")
        if i % 16 == 0:
            print("")
        i += 1


all_hids = hid.find_all_hid_devices()
print("---find_all_hid_devices---")
print(all_hids)
if all_hids:
    for hid_info in all_hids:
        print("---hid_info---")
        print(hid_info)


# VID and PID customization changes here...
filter = hid.HidDeviceFilter(vendor_id = 0x1A86, product_id = 0xE429)
hid_device = filter.get_devices()

if hid_device:
    print("---hid_device---")
    print(hid_device)
    device = hid_device[0]
    print("---success--- : device found")
    print("vendor_id: {:02X}".format(device.vendor_id))
    print("product_id: {:02X}".format(device.product_id))
    print("vendor_name: {}".format(device.vendor_name))
    print("product_name: {}".format(device.product_name))
    print("version_number: {}".format(device.version_number))
    print("serial_number: {}".format(device.serial_number))
    print("device_path: {}".format(device.device_path))
else:
    print("---error--- : device not found")

print("---set_raw_data_handler---")
device.set_raw_data_handler(sample_handler)

#target_usage = hid.get_full_usage_id(0x00, 0x3f)
#print("---target_usage---")
#print(target_usage)

print("---device.open---")
device.open()

report = device.find_output_reports()
print("---report---")
print(report)
print(report[0])

buffer = [0xFF]*65
buffer[0] = 0  # report_ID : 0

# data to be transmitted from HID to UART
# [0x06, 0xab, 0xcd, 0x03, 0x4b, 0x01, 0xc6])  # 06ABCD034B01C6
#
#
#    _SEQUENCE_GET_NAME = bytes.fromhex('AB CD 03 5F 01 DA')
#    _SEQUENCE_SEND_DATA = bytes.fromhex('AB CD 03 5E 01 D9')
#    _SEQUENCE_GET_SERIAL = bytes.fromhex('AB CD 03 5D 01 D8')
#    _SEQUENCE_SEND_CMD = bytes.fromhex('AB CD 03')
#
#

buffer[1] = 6  # data length;   Range->1 to 9
buffer[2] = 0xab # data 1
buffer[3] = 0xcd # data 2
buffer[4] = 0x03 # data 3
buffer[5] = 0x5f # data 4
buffer[6] = 0x01 # data 5
buffer[7] = 0xda # data 6 , buffer[7] = buffer[5] + 379
print("---send CMD (AB CD 03 5F 01 DA) : get DMM_Name---")
print(buffer)
report[0].set_raw_data(buffer)
report[0].send()
time.sleep(1)  # wait response, confirm and DMM_Name


buffer[1] = 6  # data length;   Range->1 to 9
buffer[2] = 0xab # data 1
buffer[3] = 0xcd # data 2
buffer[4] = 0x03 # data 3
buffer[5] = 0x4b # data 4
buffer[6] = 0x01 # data 5
buffer[7] = 0xc6 # data 6 , buffer[7] = buffer[5] + 379
print("---send CMD (AB CD 03 4B 01 C6) : Ligh---")
print(buffer)
report[0].set_raw_data(buffer)
report[0].send()
time.sleep(1)  # wait response, confirm from DMM


for i in range(5):
    # data to be transmitted from HID to UART
    # [0x06, 0xab, 0xcd, 0x03, 0x5e, 0x01, 0xd9])  # 06abcd035e01d9
    buffer[1] = 6  # data length;   Range->1 to 9
    buffer[2] = 0xab # data 1
    buffer[3] = 0xcd # data 2
    buffer[4] = 0x03 # data 3
    buffer[5] = 0x5e # data 4
    buffer[6] = 0x01 # data 5
    buffer[7] = 0xd9 # data 6
    print("---buffer : Take Measurement---")
    print(buffer)
    report[0].set_raw_data(buffer)
    report[0].send()
    time.sleep(1)  # wait response, receive from DMM

print("---device.close---")
device.close()

