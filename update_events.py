# Copyright (C) 2023 Intel Corporation
#
# This software and the related documents are Intel copyrighted materials, and your use of them is governed by the
# express license under which they were provided to you ("License"). Unless the License provides otherwise, you may
# not use, modify, copy, publish, distribute, disclose or transmit this software or the related documents without
# Intel's prior written permission.
#
# This software and the related documents are provided as is, with no express or implied warranties, other than those
# that are expressly stated in the License.

import os
import re
import sys

from util import TEST_RESULT_INVALID_EVENT

# update [    4850.623583] /dev/input/event3: 0003 003a 00000000
# to     [    4850.623583] /dev/input/{new_channel}: 0003 003a 00000000


def update_events(event_channel_dict, swap_x_y, events_file, new_events_file):
    # only if we need to swap x/y, we need tmp file, or, we update to new_events_file directly
    tmp_file = "events.tmp" if swap_x_y else new_events_file
    with open(events_file, 'r') as f:
        content = f.read()
        for old_channel, new_channel in event_channel_dict.items():
            content = re.sub(f'/dev/input/{old_channel}:', rf'/dev/input/{new_channel}_new:', content, flags=re.M)
        content = re.sub(f'/dev/input/(.*)_new:', rf'/dev/input/\1:', content, flags=re.M)
        with open(tmp_file, 'w') as new_f:
            ret = new_f.write(content)
    if swap_x_y:
        ret = swap_35_36_events(tmp_file, new_events_file)
        os.remove(tmp_file)
    return ret


# swap x,y from Pad to AoW
def swap_35_36_events(input_events, output_events):
    with open(input_events) as f:
        with open(output_events, 'w') as new_f:
            lines = f.readlines()
            idx = 0
            while idx < len(lines):
                if "0003 0035" in lines[idx]:
                    # print("0035 " + str(idx) + "," + lines[idx].split()[-1])
                    line_0035 = lines[idx]
                    old_x = line_0035.split()[-1]
                    idx += 1
                    # print("0036 " + str(idx) + "," + lines[idx].split()[-1])
                    line_0036 = lines[idx]
                    old_y = line_0036.split()[-1]
                    new_x = old_y
                    # TODO path max_0035 to replace 1199(0x4fa)
                    if 1199 <= int(old_x, 16):
                        print("input (x, y) is out of screen range, quit!")
                        return TEST_RESULT_INVALID_EVENT   # events invalid
                    new_y = '{:08x}'.format(1199 - int(old_x, 16))
                    new_line_0035 = re.sub(f'0003 0035 {old_x}', rf'0003 0035 {new_x}', line_0035, flags=re.M)
                    new_line_0036 = re.sub(f'0003 0036 {old_y}', rf'0003 0036 {new_y}', line_0036, flags=re.M)
                    new_f.write(new_line_0035)
                    new_f.write(new_line_0036)
                else:
                    new_f.write(lines[idx])
                idx += 1
    return


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} events_in.txt events_out.txt.")
        exit(1)

    events_in = sys.argv[1]
    events_out = sys.argv[2]
    event_channel_dict = dict();
    event_channel_dict.update({"event3":"event14"})
    event_channel_dict.update({"event14": "event99"})
    update_events(event_channel_dict, False, events_in, events_out)
