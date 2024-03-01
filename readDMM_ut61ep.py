# -*- coding: utf-8 -*-
#
# version date : 2024/3/1
#

import time
import logging
from ut61eplus import UT61EPLUS


log = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s,%(msecs)03d %(levelname)-8s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

log.info(__file__)

dmm = UT61EPLUS(vid=0x1A86, pid=0xE429, device_id=0) # set index for first device

'''
UT61EPLUS.sendCommand( CMD )

CMD list :
	'min_max'           # Max/Min
	'not_min_max'       # Max/Min Off
	'range'             # Manual(Range)
	'auto'              # Auto
	'rel'               # REL
	'select2'           # Hz %
	'hold'              # Hold
	'lamp'              # Light On/Off
	'select1'           # Select (orange)
	'p_min_max'         # Peak Max/Min
	'not_peak'          # Peak Off
'''

log.info('--- Get DMM (Digital Multimeter) Name ---')
n = dmm.getName()
log.info('DMM name : %s', n)
##time.sleep(0.3)

log.info('--- Light switch On/Off ---')
dmm.sendCommand('lamp')
##time.sleep(0.3)

log.info('--- Get DMM data ---')
m = dmm.takeMeasurement()
log.info('measurent : %s', m)
##time.sleep(0.3)

log.info('--- Close ---')
dmm.close()

