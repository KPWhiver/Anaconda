"""
    Uses Androguard to find usages of sensitive methods, getDeviceId in this case, and analyses the context where these
    methods are called. It finds the register where the information from the method call is stored, and looks for other
    usages of that register. Does not check whether or not the register has been rewritten.
"""

from androlyze import *
import sys

#a, d, dx = AnalyzeAPK("nl.peperzaken.android.nu-1.apk", decompiler="dad")
a, d, dx = AnalyzeAPK("LeakTest1.apk", decompiler="dad")

# Find method usage and details
sensitive_methods = dx.tainted_packages.search_methods('Landroid/telephony/TelephonyManager;', "getDeviceId", ".")
for idx, sensitive_method in enumerate(sensitive_methods):
    print("\nUsage " + str(idx))
    method_details = sensitive_method.get_dst(d.get_class_manager())
    print(method_details)
    location = sensitive_method.get_src(d.get_class_manager())

    # Retrieve method that calls the sensitive method
    tainted_method = d.get_method_descriptor(location[0], location[1], location[2])
    tainted_method.get_code().show()
    print('\n')

    # Find the instruction where the call is made
    instructions = tainted_method.get_instructions()
    for instruction in instructions:
        if method_details[0] in instruction.get_output() and method_details[1] in instruction.get_output():
            print("Found instruction performing getDeviceId call")
            break

    # Find which register the string is stored in in the next instruction
    instruction = next(instructions)
    register = instruction.get_output()
    print("Register used to store deviceId: " + register)

    # Find all usages of the register
    print("Usages of register:")
    for instruction in instructions:
        if register in instruction.get_output():
            instruction.show(-1)
            print
