# -*- coding: utf-8 -*-

import time
import logging
from ut61eplus import UT61EPLUS


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s,%(msecs)03d [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log.info(__file__)

dmm = UT61EPLUS(vid=0x1A86, pid=0xE429, device_id=0) # set index for first device

log.info('--- Get DMM name : %s ---', dmm.getName())
time.sleep(0.3)

log.info('--- Light switch On/Off ---')
dmm.sendCommand('lamp')
time.sleep(0.3)

log.info('--- Get DMM data ---')
m = dmm.takeMeasurement()
log.info('measurent=%s', m)
time.sleep(0.3)

log.info('--- Close ---')
dmm.close()

