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
import xml.etree.ElementTree as ET
import sys
import re

level = 0


def check_NAF(node):
    if node.get("NAF") == 'true':
        # refer to https://stackoverflow.com/questions/25435878/uiautomatorviewer-what-does-naf-stand-for
        print("NAF node is found, we skip checking it.")
        return True
    return False


def compare_node(root1, root2, display_id="0"):
    global level
    level += 1
    # 1. getclass of each node & compare

    node_list_1 = list(root1)
    node_list_2 = list(root2)

    # node list length check
    if len(node_list_1) != len(node_list_2):
        print("\t"*level + "length of 2 node list not same: " + str(len(node_list_1)) + ',' + str(len(node_list_2)))
        return False
    # classname check
    classname1 = []
    for node in list(root1):  # .find('node'):
        if check_NAF(node):
            return True
        classname1.append(node.get('class'))
    # root1_class = root1.get('class')
    # print("\t"*level + "node[" + str(root1_class) +"]")
    # print("\t"*level + "node("+").subnode.classes: "+str(classname1))
    classname2 = []
    for node in list(root2):  # .find('node'):
        if check_NAF(node):
            return True
        classname2.append(node.get('class'))
    # root2_class = root1.get('class')
    # print("\t"*level + "node[" + str(root2_class) +"]")
    # print("\t"*level + "node("+").subnode.classes: "+str(classname2))
    if classname1 != classname2:
        print("\t"*level + "classname of 2 node not same: " + str(classname1) + ',' + str(classname2))
        return False
    # recursion check
    i = 0
    for node in node_list_1:
        # print("\t"*level + "i: ", i, node.get('class'))
        # TODO: need logic upgrade here:
        if node.tag == 'display' and node.attrib['id'] != display_id:
            print(f"skip display {node.attrib['id']}")
            i += 1
            continue
        b_scrollable = node.get('scrollable')  # skip scrollable class check for temp
        if len(list(node)) and b_scrollable != 'true':  # node is not scrollable
            # print("\t"*level + "node has subnode:")
            ret = compare_node(node, node_list_2[i], display_id)
            
            if not ret:
                #print("\t"*level + "compare_node return false")
                return False
        i += 1
    level -= 1
    return True


def compare_xml(xml_file1, xml_file2, display_id="0"):
    if os.path.getsize(xml_file1) == 0 or os.path.getsize(xml_file2) == 0:
        print(f"WARNING: you have 0 size xml file({xml_file1}). We skip checking it.")
        return True
    root1 = ET.parse(xml_file1).getroot()
    root2 = ET.parse(xml_file2).getroot()
    
    ret = compare_node(root1, root2, display_id)
    
    if not ret:
        ret = compare_xml_v2(xml_file1, xml_file2)
    return ret


# check if classes of short xml_file is part of long xml_file
# this is to work around the wrapper case
def compare_xml_v2(xml_file1, xml_file2):
    pattern = re.compile('class="(\S*)"')
    with open(xml_file1, 'r', encoding='UTF-8') as f1, open(xml_file2, 'r', encoding='UTF-8') as f2:
        content1 = f1.read()
        class_list1 = pattern.findall(content1)
        content2 = f2.read()
        class_list2 = pattern.findall(content2)
        list_len1 = len(class_list1)
        list_len2 = len(class_list2)
        # sometime, dumped xml has little classes, which may be checked as True by mistake.
        # add this check to avoid such case.
        if max(list_len1, list_len2) > 2 * min(list_len1, list_len2):
            return False
        short_list = class_list1 if list_len1 <= list_len2 else class_list2
        long_list = class_list2 if class_list1 == short_list else class_list1
        idx_long = 0
        for idx_short, class_name in enumerate(short_list):
            try:
                # print(idx_short, class_name)
                if long_list[idx_long] == short_list[idx_short]:
                    idx_long += 1
                    continue
                else:
                    # print(f"to search {short_list[idx_short]} in {long_list[idx_long:]}")
                    if short_list[idx_short] not in long_list[idx_long:]:
                        return False  # there is a class not found in long xml
                    new_idx_long = long_list.index(short_list[idx_short], idx_long)
                    # usually, the acceptable case is a wrapper class in long_list contains one+ class of short_list
                    # inside. so the index step should not bigger than 1. If it is, we think XMLs are different.
                    if new_idx_long > idx_long + 1:
                        return False
                    # we can assert the number of classes in short_list equals the number in long_list, if necessary
                    idx_long = new_idx_long + 1
                    # print("found in later part. " + f"idx_short: {idx_short}; idx_long: {idx_long}")
            except IndexError:
                return False
    # all classes in short xml are found in long xml
    return True


def main():
    if len(sys.argv) != 3:
        print(f"usage: {sys.argv[0]} window_dump1.xml window_dump2.xml.")
        return

    xml_file1 = sys.argv[1]
    xml_file2 = sys.argv[2]

    ret = compare_xml(xml_file1, xml_file2)

    print(f'{xml_file1} ?= {xml_file2} : {ret}')
    return


if __name__ == "__main__":
    main()
